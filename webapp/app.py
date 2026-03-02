"""Flask webapp for Reloading Tracker – mobile-first interface."""

import sys
import os
import json
from pathlib import Path
from datetime import date

# Add parent dir so we can import utils
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, render_template, request, jsonify, redirect, url_for, g
from utils.database import Database, get_db_path
from utils.ballistics import calculate_es, calculate_sd, calculate_mean, es_color
from utils.conversions import mm_to_moa, mm_to_thou

app = Flask(__name__)


def _db_path():
    """Get DB path – uses env var on Vercel (/tmp), default locally."""
    return os.environ.get("RELOADING_DB_PATH") or get_db_path()


def get_db():
    """Get a per-request database connection."""
    if "db" not in g:
        db_path = _db_path()
        g.db = Database(db_path)
        # On Vercel, seed default data if DB is fresh
        if os.environ.get("VERCEL"):
            g.db.seed_default_setup()
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ── Helpers ──────────────────────────────────────────────────

def _get_powder_info(setup_id):
    """Get powder component details for a setup."""
    composants = get_db().get_composants(setup_id)
    for c in composants:
        if c["type"] == "Poudre":
            return c
    return None


# ── Pages ────────────────────────────────────────────────────

@app.route("/")
def index():
    db = get_db()
    setups = db.get_setups()
    sessions = db.get_sessions()
    total_sessions = len(sessions)

    # Last 5 sessions with series info
    recent = []
    for s in sessions[:5]:
        series = db.get_series(s["id"])
        s["series"] = series
        recent.append(s)

    # Best ES per setup
    best_stats = {}
    for setup in setups:
        best_stats[setup["id"]] = db.get_best_series(setup["id"])

    return render_template(
        "index.html",
        setups=setups,
        recent=recent,
        total_sessions=total_sessions,
        best_stats=best_stats,
        es_color=es_color,
    )


@app.route("/new")
def new_session():
    setups = get_db().get_setups()
    today = date.today().isoformat()
    return render_template("new_session.html", setups=setups, today=today)


@app.route("/history")
def history():
    db = get_db()
    setup_id = request.args.get("setup_id", type=int)
    sessions = db.get_sessions(setup_id)
    for s in sessions:
        series = db.get_series(s["id"])
        s["series"] = series
    setups = db.get_setups()
    return render_template(
        "historique.html",
        sessions=sessions,
        setups=setups,
        selected_setup=setup_id,
        es_color=es_color,
        mm_to_moa=mm_to_moa,
    )


@app.route("/setups")
def setups_page():
    db = get_db()
    setups = db.get_setups()
    setups_data = []
    for s in setups:
        composants = db.get_composants(s["id"])
        best = db.get_best_series(s["id"])
        setups_data.append({"setup": s, "composants": composants, "best": best})
    return render_template("setups.html", setups_data=setups_data, mm_to_thou=mm_to_thou)


# ── API ──────────────────────────────────────────────────────

@app.route("/api/session", methods=["POST"])
def api_create_session():
    db = get_db()
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400

    # Create session
    session_data = {
        "setup_id": data.get("setup_id"),
        "date": data.get("date", date.today().isoformat()),
        "lieu": data.get("lieu", ""),
        "meteo": data.get("meteo", {}),
        "phase": data.get("phase", "Phase 1"),
        "notes": data.get("notes", ""),
    }
    session_id = db.create_session(session_data)

    # Create serie
    vitesses = [v for v in data.get("vitesses", []) if v is not None]
    es = calculate_es(vitesses)
    sd = calculate_sd(vitesses)
    v_moy = calculate_mean(vitesses)

    serie_data = {
        "session_id": session_id,
        "charge_gr": data.get("charge_gr"),
        "oal_mm": data.get("oal_mm"),
        "cbto_mm": data.get("cbto_mm"),
        "jump_mm": data.get("jump_mm"),
        "nb_coups": data.get("nb_coups", 5),
        "vitesses": vitesses,
        "es": es,
        "sd": sd,
        "v_moy": v_moy,
        "groupement_mm": data.get("groupement_mm"),
        "distance_m": data.get("distance_m", 100),
        "signes_pression": data.get("signes_pression", []),
        "observations": data.get("observations", ""),
        "charge_retenue": data.get("charge_retenue", 0),
    }
    serie_id = db.create_serie(serie_data)

    return jsonify({"ok": True, "session_id": session_id, "serie_id": serie_id})


@app.route("/api/sessions/<int:session_id>")
def api_session_detail(session_id):
    db = get_db()
    session = db.get_session(session_id)
    if not session:
        return jsonify({"error": "Not found"}), 404
    series = db.get_series(session_id)
    session["series"] = series
    return jsonify(session)


@app.route("/api/setups")
def api_setups():
    setups = get_db().get_setups()
    return jsonify(setups)


@app.route("/api/setup/<int:setup_id>/powder")
def api_powder_info(setup_id):
    setup = get_db().get_setup(setup_id)
    if not setup:
        return jsonify({"error": "Not found"}), 404
    powder = _get_powder_info(setup_id)
    result = {
        "cbto_lands_mm": setup.get("cbto_lands_mm"),
        "oal_ref_mm": setup.get("oal_ref_mm"),
    }
    if powder:
        details = powder.get("details", {})
        result["powder_name"] = f"{powder.get('marque', '')} {powder.get('modele', '')}"
        result["charge_min_gr"] = details.get("charge_min_gr")
        result["charge_max_gr"] = details.get("charge_max_gr")
        result["pression_max_psi"] = details.get("pression_max_psi")
    return jsonify(result)


if __name__ == "__main__":
    print("Reloading Tracker Webapp")
    print("Access: http://0.0.0.0:5050")
    app.run(host="0.0.0.0", port=5050, debug=True)
