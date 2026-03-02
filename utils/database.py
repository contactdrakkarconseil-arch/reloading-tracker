"""SQLite / LibSQL database management – multi-tenant."""

import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

# ── Driver selection: libsql on Vercel, sqlite3 locally ──────
try:
    import libsql

    def _connect(db_path_or_url, auth_token=None):
        if auth_token:
            return libsql.connect(db_path_or_url, auth_token=auth_token)
        return libsql.connect(db_path_or_url)

    _DRIVER = "libsql"
except ImportError:
    import sqlite3

    def _connect(db_path_or_url, auth_token=None):
        conn = sqlite3.connect(db_path_or_url)
        conn.row_factory = sqlite3.Row
        return conn

    _DRIVER = "sqlite3"


def get_db_path() -> str:
    """Get the database file path in user's app data directory."""
    app_dir = Path.home() / ".reloading_tracker"
    app_dir.mkdir(exist_ok=True)
    return str(app_dir / "reloading.db")


def _row_to_dict(cursor, row) -> Dict:
    """Convert a row tuple to dict using cursor.description."""
    if isinstance(row, dict):
        return row
    if hasattr(row, "keys"):
        return dict(row)
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


def _rows_to_dicts(cursor, rows) -> List[Dict]:
    return [_row_to_dict(cursor, r) for r in rows]


class Database:
    def __init__(self, db_path: Optional[str] = None):
        turso_url = (os.environ.get("TURSO_DATABASE_URL") or "").strip()
        turso_token = (os.environ.get("TURSO_AUTH_TOKEN") or "").strip()

        if turso_url and turso_token:
            # Convert libsql:// to https:// for the Python driver
            if turso_url.startswith("libsql://"):
                turso_url = turso_url.replace("libsql://", "https://", 1)
            self.conn = _connect(turso_url, auth_token=turso_token)
            self._is_turso = True
        else:
            self.db_path = db_path or get_db_path()
            self.conn = _connect(self.db_path)
            self._is_turso = False
            self.conn.execute("PRAGMA journal_mode=WAL")

        self.conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()
        self._migrate()

    def _create_tables(self):
        cursor = self.conn.cursor()
        statements = [
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                password_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS setups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id),
                nom TEXT NOT NULL,
                calibre TEXT NOT NULL,
                longueur_canon_mm REAL,
                twist TEXT,
                suppresseur TEXT,
                lunette TEXT,
                chrono TEXT,
                cbto_lands_mm REAL,
                oal_ref_mm REAL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS composants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setup_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                marque TEXT,
                modele TEXT,
                details_json TEXT DEFAULT '{}',
                FOREIGN KEY (setup_id) REFERENCES setups(id) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setup_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                lieu TEXT,
                meteo_json TEXT DEFAULT '{}',
                phase TEXT DEFAULT 'Phase 1',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (setup_id) REFERENCES setups(id) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                charge_gr REAL NOT NULL,
                oal_mm REAL,
                cbto_mm REAL,
                jump_mm REAL,
                nb_coups INTEGER DEFAULT 5,
                vitesses_json TEXT DEFAULT '[]',
                es REAL,
                sd REAL,
                v_moy REAL,
                groupement_mm REAL,
                distance_m REAL DEFAULT 100,
                signes_pression_json TEXT DEFAULT '[]',
                observations TEXT,
                charge_retenue INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )""",
        ]
        for stmt in statements:
            cursor.execute(stmt)
        self.conn.commit()

    def _migrate(self):
        """Run incremental migrations."""
        cursor = self.conn.cursor()
        # Add user_id to setups if missing (legacy DB)
        cursor.execute("PRAGMA table_info(setups)")
        cols = [r[1] if isinstance(r, tuple) else r["name"] for r in cursor.fetchall()]
        if "user_id" not in cols:
            cursor.execute("ALTER TABLE setups ADD COLUMN user_id INTEGER REFERENCES users(id)")
            self.conn.commit()

    # ── Users ────────────────────────────────────────────────

    def create_user(self, data: Dict[str, Any]) -> int:
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO users (email, name, password_hash)
            VALUES (?, ?, ?)
        """, (
            data["email"],
            data["name"],
            data.get("password_hash"),
        ))
        self.conn.commit()
        return cursor.lastrowid

    def get_user(self, user_id: int) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return _row_to_dict(cursor, row) if row else None

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        return _row_to_dict(cursor, row) if row else None

    # ── Setups ───────────────────────────────────────────────

    def create_setup(self, data: Dict[str, Any], user_id: Optional[int] = None) -> int:
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO setups (user_id, nom, calibre, longueur_canon_mm, twist,
                                suppresseur, lunette, chrono, cbto_lands_mm,
                                oal_ref_mm, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            data.get("nom", ""),
            data.get("calibre", ""),
            data.get("longueur_canon_mm"),
            data.get("twist"),
            data.get("suppresseur"),
            data.get("lunette"),
            data.get("chrono"),
            data.get("cbto_lands_mm"),
            data.get("oal_ref_mm"),
            data.get("notes"),
        ))
        self.conn.commit()
        return cursor.lastrowid

    def get_setups(self, user_id: Optional[int] = None) -> List[Dict]:
        cursor = self.conn.cursor()
        if user_id is not None:
            cursor.execute(
                "SELECT * FROM setups WHERE user_id = ? ORDER BY nom", (user_id,)
            )
        else:
            cursor.execute("SELECT * FROM setups ORDER BY nom")
        return _rows_to_dicts(cursor, cursor.fetchall())

    def get_setup(self, setup_id: int, user_id: Optional[int] = None) -> Optional[Dict]:
        cursor = self.conn.cursor()
        if user_id is not None:
            cursor.execute(
                "SELECT * FROM setups WHERE id = ? AND user_id = ?",
                (setup_id, user_id),
            )
        else:
            cursor.execute("SELECT * FROM setups WHERE id = ?", (setup_id,))
        row = cursor.fetchone()
        return _row_to_dict(cursor, row) if row else None

    def update_setup(self, setup_id: int, data: Dict[str, Any], user_id: Optional[int] = None):
        cursor = self.conn.cursor()
        if user_id is not None:
            cursor.execute("""
                UPDATE setups SET nom=?, calibre=?, longueur_canon_mm=?, twist=?,
                                 suppresseur=?, lunette=?, chrono=?, cbto_lands_mm=?,
                                 oal_ref_mm=?, notes=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=? AND user_id=?
            """, (
                data.get("nom", ""), data.get("calibre", ""),
                data.get("longueur_canon_mm"), data.get("twist"),
                data.get("suppresseur"), data.get("lunette"),
                data.get("chrono"), data.get("cbto_lands_mm"),
                data.get("oal_ref_mm"), data.get("notes"),
                setup_id, user_id,
            ))
        else:
            cursor.execute("""
                UPDATE setups SET nom=?, calibre=?, longueur_canon_mm=?, twist=?,
                                 suppresseur=?, lunette=?, chrono=?, cbto_lands_mm=?,
                                 oal_ref_mm=?, notes=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            """, (
                data.get("nom", ""), data.get("calibre", ""),
                data.get("longueur_canon_mm"), data.get("twist"),
                data.get("suppresseur"), data.get("lunette"),
                data.get("chrono"), data.get("cbto_lands_mm"),
                data.get("oal_ref_mm"), data.get("notes"),
                setup_id,
            ))
        self.conn.commit()

    def delete_setup(self, setup_id: int, user_id: Optional[int] = None):
        if user_id is not None:
            self.conn.execute(
                "DELETE FROM setups WHERE id = ? AND user_id = ?",
                (setup_id, user_id),
            )
        else:
            self.conn.execute("DELETE FROM setups WHERE id = ?", (setup_id,))
        self.conn.commit()

    # ── Composants ───────────────────────────────────────────

    def add_composant(self, setup_id: int, data: Dict[str, Any]) -> int:
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO composants (setup_id, type, marque, modele, details_json)
            VALUES (?, ?, ?, ?, ?)
        """, (
            setup_id,
            data.get("type", ""),
            data.get("marque", ""),
            data.get("modele", ""),
            json.dumps(data.get("details", {}), ensure_ascii=False),
        ))
        self.conn.commit()
        return cursor.lastrowid

    def get_composants(self, setup_id: int) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM composants WHERE setup_id = ? ORDER BY type",
            (setup_id,),
        )
        rows = _rows_to_dicts(cursor, cursor.fetchall())
        for row in rows:
            row["details"] = json.loads(row.get("details_json") or "{}")
        return rows

    def update_composant(self, composant_id: int, data: Dict[str, Any]):
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE composants SET type=?, marque=?, modele=?, details_json=?
            WHERE id=?
        """, (
            data.get("type", ""),
            data.get("marque", ""),
            data.get("modele", ""),
            json.dumps(data.get("details", {}), ensure_ascii=False),
            composant_id,
        ))
        self.conn.commit()

    def delete_composant(self, composant_id: int):
        self.conn.execute("DELETE FROM composants WHERE id = ?", (composant_id,))
        self.conn.commit()

    def delete_composants_by_setup(self, setup_id: int):
        self.conn.execute("DELETE FROM composants WHERE setup_id = ?", (setup_id,))
        self.conn.commit()

    # ── Sessions ─────────────────────────────────────────────

    def create_session(self, data: Dict[str, Any]) -> int:
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO sessions (setup_id, date, lieu, meteo_json, phase, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            data.get("setup_id"),
            data.get("date", ""),
            data.get("lieu", ""),
            json.dumps(data.get("meteo", {}), ensure_ascii=False),
            data.get("phase", "Phase 1"),
            data.get("notes", ""),
        ))
        self.conn.commit()
        return cursor.lastrowid

    def get_sessions(self, setup_id: Optional[int] = None, user_id: Optional[int] = None) -> List[Dict]:
        cursor = self.conn.cursor()
        if setup_id:
            cursor.execute("""
                SELECT s.*, st.nom as setup_nom
                FROM sessions s
                JOIN setups st ON s.setup_id = st.id
                WHERE s.setup_id = ?
                ORDER BY s.date DESC
            """, (setup_id,))
        elif user_id is not None:
            cursor.execute("""
                SELECT s.*, st.nom as setup_nom
                FROM sessions s
                JOIN setups st ON s.setup_id = st.id
                WHERE st.user_id = ?
                ORDER BY s.date DESC
            """, (user_id,))
        else:
            cursor.execute("""
                SELECT s.*, st.nom as setup_nom
                FROM sessions s
                JOIN setups st ON s.setup_id = st.id
                ORDER BY s.date DESC
            """)
        rows = _rows_to_dicts(cursor, cursor.fetchall())
        for row in rows:
            row["meteo"] = json.loads(row.get("meteo_json") or "{}")
        return rows

    def get_session(self, session_id: int) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT s.*, st.nom as setup_nom
            FROM sessions s
            JOIN setups st ON s.setup_id = st.id
            WHERE s.id = ?
        """, (session_id,))
        row = cursor.fetchone()
        if row:
            d = _row_to_dict(cursor, row)
            d["meteo"] = json.loads(d.get("meteo_json") or "{}")
            return d
        return None

    def delete_session(self, session_id: int):
        self.conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self.conn.commit()

    # ── Séries ───────────────────────────────────────────────

    def create_serie(self, data: Dict[str, Any]) -> int:
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO series (session_id, charge_gr, oal_mm, cbto_mm, jump_mm,
                               nb_coups, vitesses_json, es, sd, v_moy,
                               groupement_mm, distance_m, signes_pression_json,
                               observations, charge_retenue)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("session_id"),
            data.get("charge_gr"),
            data.get("oal_mm"),
            data.get("cbto_mm"),
            data.get("jump_mm"),
            data.get("nb_coups", 5),
            json.dumps(data.get("vitesses", []), ensure_ascii=False),
            data.get("es"),
            data.get("sd"),
            data.get("v_moy"),
            data.get("groupement_mm"),
            data.get("distance_m", 100),
            json.dumps(data.get("signes_pression", []), ensure_ascii=False),
            data.get("observations", ""),
            data.get("charge_retenue", 0),
        ))
        self.conn.commit()
        return cursor.lastrowid

    def get_series(self, session_id: int) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM series WHERE session_id = ? ORDER BY charge_gr",
            (session_id,),
        )
        rows = _rows_to_dicts(cursor, cursor.fetchall())
        for row in rows:
            row["vitesses"] = json.loads(row.get("vitesses_json") or "[]")
            row["signes_pression"] = json.loads(row.get("signes_pression_json") or "[]")
        return rows

    def get_all_series(self, setup_id: Optional[int] = None, user_id: Optional[int] = None) -> List[Dict]:
        cursor = self.conn.cursor()
        if setup_id:
            cursor.execute("""
                SELECT sr.*, s.date, s.phase, s.lieu
                FROM series sr
                JOIN sessions s ON sr.session_id = s.id
                WHERE s.setup_id = ?
                ORDER BY s.date, sr.charge_gr
            """, (setup_id,))
        elif user_id is not None:
            cursor.execute("""
                SELECT sr.*, s.date, s.phase, s.lieu
                FROM series sr
                JOIN sessions s ON sr.session_id = s.id
                JOIN setups st ON s.setup_id = st.id
                WHERE st.user_id = ?
                ORDER BY s.date, sr.charge_gr
            """, (user_id,))
        else:
            cursor.execute("""
                SELECT sr.*, s.date, s.phase, s.lieu
                FROM series sr
                JOIN sessions s ON sr.session_id = s.id
                ORDER BY s.date, sr.charge_gr
            """)
        rows = _rows_to_dicts(cursor, cursor.fetchall())
        for row in rows:
            row["vitesses"] = json.loads(row.get("vitesses_json") or "[]")
            row["signes_pression"] = json.loads(row.get("signes_pression_json") or "[]")
        return rows

    def update_serie_charge_retenue(self, serie_id: int, retenue: bool):
        self.conn.execute(
            "UPDATE series SET charge_retenue = ? WHERE id = ?",
            (1 if retenue else 0, serie_id),
        )
        self.conn.commit()

    def delete_serie(self, serie_id: int):
        self.conn.execute("DELETE FROM series WHERE id = ?", (serie_id,))
        self.conn.commit()

    def get_best_series(self, setup_id: int) -> Dict:
        """Get summary stats: best ES, best group, etc."""
        series = self.get_all_series(setup_id)
        if not series:
            return {}
        valid_es = [s for s in series if s.get("es") is not None and s["es"] > 0]
        valid_grp = [
            s for s in series
            if s.get("groupement_mm") is not None and s["groupement_mm"] > 0
        ]
        result = {}
        if valid_es:
            best = min(valid_es, key=lambda x: x["es"])
            result["best_es"] = best["es"]
            result["best_es_charge"] = best["charge_gr"]
        if valid_grp:
            best = min(valid_grp, key=lambda x: x["groupement_mm"])
            result["best_group_mm"] = best["groupement_mm"]
            result["best_group_charge"] = best["charge_gr"]
        retained = [s for s in series if s.get("charge_retenue")]
        if retained:
            result["charge_retenue"] = retained[-1]["charge_gr"]
        return result

    def close(self):
        self.conn.close()

    def seed_default_setup(self, user_id: Optional[int] = None):
        """Pre-fill with Victrix setup if no setups exist for user."""
        if self.get_setups(user_id):
            return
        setup_id = self.create_setup({
            "nom": "Victrix Armaments Orb",
            "calibre": "6.5 Creedmoor",
            "longueur_canon_mm": 762.0,
            "twist": "1:7.5\"",
            "suppresseur": "A-TEC PRS",
            "lunette": "",
            "chrono": "MagnetoSpeed",
            "cbto_lands_mm": 58.57,
            "oal_ref_mm": 73.73,
            "notes": "Référence VI15003 – Canon fileté 30 pouces",
        }, user_id=user_id)
        self.add_composant(setup_id, {
            "type": "Ogive", "marque": "Hornady", "modele": "140gr ELD-Match",
            "details": {"poids_gr": 140,
                        "bc_g7": {"2.25": 0.326, "2.0": 0.320, "1.75": 0.310},
                        "bc_g1": {"2.25": 0.646, "2.0": 0.637, "1.75": 0.616}},
        })
        self.add_composant(setup_id, {
            "type": "Poudre", "marque": "Winchester", "modele": "StaBALL 6.5",
            "details": {"charge_min_gr": 35.0, "charge_max_gr": 41.5,
                        "pression_max_psi": 62000},
        })
        self.add_composant(setup_id, {
            "type": "Amorce", "marque": "CCI", "modele": "#400 Small Rifle",
            "details": {},
        })
        self.add_composant(setup_id, {
            "type": "Étuis", "marque": "Sako", "modele": "6.5 CM Small Rifle Primer",
            "details": {},
        })
