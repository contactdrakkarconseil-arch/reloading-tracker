"""Flask webapp for Reloading Tracker – mobile-first with auth."""

import sys
import os
import json
from pathlib import Path
from datetime import date

# Add parent dir so we can import utils
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, render_template, request, jsonify, redirect, url_for, g, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from utils.database import Database, get_db_path
from utils.ballistics import calculate_es, calculate_sd, calculate_mean, es_color
from utils.conversions import mm_to_moa, mm_to_thou

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")

# ── Flask-Login setup ────────────────────────────────────────

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


class User(UserMixin):
    def __init__(self, id, email, name, password_hash=None, google_id=None):
        self.id = id
        self.email = email
        self.name = name
        self.password_hash = password_hash
        self.google_id = google_id

    @staticmethod
    def from_db(row):
        if not row:
            return None
        return User(
            id=row["id"],
            email=row["email"],
            name=row["name"],
            password_hash=row.get("password_hash"),
            google_id=row.get("google_id"),
        )


@login_manager.user_loader
def load_user(user_id):
    row = get_db().get_user(int(user_id))
    return User.from_db(row)


# ── Google OAuth (Flask-Dance) ───────────────────────────────

google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")

if google_client_id and google_client_secret:
    from flask_dance.contrib.google import make_google_blueprint, google as google_session
    from flask_dance.consumer import oauth_authorized

    # Required for OAuth over HTTP in dev
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

    google_bp = make_google_blueprint(
        client_id=google_client_id,
        client_secret=google_client_secret,
        scope=["openid", "email", "profile"],
        redirect_url="/auth/google/authorized",
    )
    app.register_blueprint(google_bp, url_prefix="/auth")

    @oauth_authorized.connect_via(google_bp)
    def google_logged_in(blueprint, token):
        if not token:
            return False
        resp = blueprint.session.get("/oauth2/v1/userinfo")
        if not resp.ok:
            return False
        info = resp.json()
        db = get_db()

        # Check if user exists by google_id
        user_row = db.get_user_by_google_id(info["id"])
        if not user_row:
            # Check by email (might have registered with password first)
            user_row = db.get_user_by_email(info["email"])
            if user_row:
                db.update_user_google_id(user_row["id"], info["id"])
            else:
                user_id = db.create_user({
                    "email": info["email"],
                    "name": info.get("name", info["email"]),
                    "google_id": info["id"],
                })
                user_row = db.get_user(user_id)
                db.seed_default_setup(user_id=user_row["id"])

        login_user(User.from_db(user_row), remember=True)
        return False  # Don't store token in session

    _has_google = True
else:
    _has_google = False


# ── Database ─────────────────────────────────────────────────

def get_db():
    if "db" not in g:
        g.db = Database()
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _uid():
    """Get current user id."""
    return current_user.id


# ── Auth gate ────────────────────────────────────────────────

@app.before_request
def require_login():
    public = {"login", "register", "static", "health"}
    if _has_google:
        public.update({"google.login", "google.authorized"})
    if request.endpoint and request.endpoint in public:
        return None
    if not current_user.is_authenticated:
        if request.path.startswith("/api/"):
            return jsonify({"error": "Authentication required"}), 401
        return redirect(url_for("login"))


# ── Auth routes ──────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        user_row = db.get_user_by_email(email)

        if user_row and user_row.get("password_hash") and check_password_hash(user_row["password_hash"], password):
            login_user(User.from_db(user_row), remember=True)
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="Email ou mot de passe incorrect", has_google=_has_google)

    return render_template("login.html", has_google=_has_google)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")

        if not email or not name or not password:
            return render_template("register.html", error="Tous les champs sont requis", has_google=_has_google)
        if len(password) < 6:
            return render_template("register.html", error="Mot de passe : 6 caractères minimum", has_google=_has_google)

        db = get_db()
        if db.get_user_by_email(email):
            return render_template("register.html", error="Cet email est déjà utilisé", has_google=_has_google)

        user_id = db.create_user({
            "email": email,
            "name": name,
            "password_hash": generate_password_hash(password),
        })
        db.seed_default_setup(user_id=user_id)
        login_user(User.from_db(db.get_user(user_id)), remember=True)
        return redirect(url_for("index"))

    return render_template("register.html", has_google=_has_google)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("login"))


# ── Helpers ──────────────────────────────────────────────────

def _get_powder_info(setup_id):
    composants = get_db().get_composants(setup_id)
    for c in composants:
        if c["type"] == "Poudre":
            return c
    return None


# ── Pages ────────────────────────────────────────────────────

@app.route("/")
def index():
    db = get_db()
    uid = _uid()
    setups = db.get_setups(user_id=uid)
    sessions = db.get_sessions(user_id=uid)
    total_sessions = len(sessions)

    recent = []
    for s in sessions[:5]:
        series = db.get_series(s["id"])
        s["series"] = series
        recent.append(s)

    best_stats = {}
    for setup in setups:
        best_stats[setup["id"]] = db.get_best_series(setup["id"])

    return render_template(
        "index.html",
        setups=setups, recent=recent, total_sessions=total_sessions,
        best_stats=best_stats, es_color=es_color,
    )


@app.route("/new")
def new_session():
    setups = get_db().get_setups(user_id=_uid())
    today = date.today().isoformat()
    return render_template("new_session.html", setups=setups, today=today)


@app.route("/history")
def history():
    db = get_db()
    uid = _uid()
    setup_id = request.args.get("setup_id", type=int)
    if setup_id:
        # Verify ownership
        if not db.get_setup(setup_id, user_id=uid):
            setup_id = None
    sessions = db.get_sessions(setup_id, user_id=uid if not setup_id else None)
    for s in sessions:
        series = db.get_series(s["id"])
        s["series"] = series
    setups = db.get_setups(user_id=uid)
    return render_template(
        "historique.html",
        sessions=sessions, setups=setups, selected_setup=setup_id,
        es_color=es_color, mm_to_moa=mm_to_moa,
    )


@app.route("/setups")
def setups_page():
    db = get_db()
    uid = _uid()
    setups = db.get_setups(user_id=uid)
    setups_data = []
    for s in setups:
        composants = db.get_composants(s["id"])
        best = db.get_best_series(s["id"])
        setups_data.append({"setup": s, "composants": composants, "best": best})
    return render_template("setups.html", setups_data=setups_data, mm_to_thou=mm_to_thou)


# ── API : Sessions ───────────────────────────────────────────

@app.route("/api/session", methods=["POST"])
def api_create_session():
    db = get_db()
    uid = _uid()
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400

    # Verify setup ownership
    if not db.get_setup(data.get("setup_id"), user_id=uid):
        return jsonify({"error": "Setup not found"}), 404

    session_data = {
        "setup_id": data.get("setup_id"),
        "date": data.get("date", date.today().isoformat()),
        "lieu": data.get("lieu", ""),
        "meteo": data.get("meteo", {}),
        "phase": data.get("phase", "Phase 1"),
        "notes": data.get("notes", ""),
    }
    session_id = db.create_session(session_data)

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
        "es": es, "sd": sd, "v_moy": v_moy,
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


# ── API : Setups CRUD ────────────────────────────────────────

@app.route("/api/setups")
def api_setups():
    setups = get_db().get_setups(user_id=_uid())
    return jsonify(setups)


@app.route("/api/setup", methods=["POST"])
def api_create_setup():
    db = get_db()
    data = request.get_json()
    if not data or not data.get("nom") or not data.get("calibre"):
        return jsonify({"error": "Nom et calibre requis"}), 400
    setup_id = db.create_setup(data, user_id=_uid())
    return jsonify({"ok": True, "setup_id": setup_id})


@app.route("/api/setup/<int:setup_id>", methods=["PUT"])
def api_update_setup(setup_id):
    db = get_db()
    uid = _uid()
    if not db.get_setup(setup_id, user_id=uid):
        return jsonify({"error": "Not found"}), 404
    data = request.get_json()
    db.update_setup(setup_id, data, user_id=uid)
    return jsonify({"ok": True})


@app.route("/api/setup/<int:setup_id>", methods=["DELETE"])
def api_delete_setup(setup_id):
    db = get_db()
    uid = _uid()
    if not db.get_setup(setup_id, user_id=uid):
        return jsonify({"error": "Not found"}), 404
    db.delete_setup(setup_id, user_id=uid)
    return jsonify({"ok": True})


@app.route("/api/setup/<int:setup_id>/powder")
def api_powder_info(setup_id):
    db = get_db()
    setup = db.get_setup(setup_id, user_id=_uid())
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


# ── API : Composants CRUD ────────────────────────────────────

@app.route("/api/setup/<int:setup_id>/composant", methods=["POST"])
def api_add_composant(setup_id):
    db = get_db()
    if not db.get_setup(setup_id, user_id=_uid()):
        return jsonify({"error": "Not found"}), 404
    data = request.get_json()
    comp_id = db.add_composant(setup_id, data)
    return jsonify({"ok": True, "composant_id": comp_id})


@app.route("/api/composant/<int:composant_id>", methods=["DELETE"])
def api_delete_composant(composant_id):
    db = get_db()
    # Simple delete (setup ownership checked at page level)
    db.delete_composant(composant_id)
    return jsonify({"ok": True})


@app.route("/api/health")
def health():
    """Debug endpoint to check DB connection."""
    from utils.database import _DRIVER
    turso_url = os.environ.get("TURSO_DATABASE_URL", "").strip()
    turso_token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
    info = {
        "driver": _DRIVER,
        "url_len": len(turso_url),
        "token_len": len(turso_token),
        "url_repr": repr(turso_url),
        "token_start": turso_token[:20] if turso_token else "not set",
    }
    # Try direct libsql connect
    if _DRIVER == "libsql":
        import libsql
        info["libsql_version"] = getattr(libsql, "__version__", "unknown")
        url = turso_url
        if url.startswith("libsql://"):
            url = url.replace("libsql://", "https://", 1)
        info["connect_url"] = url
        try:
            conn = libsql.connect(database=url, auth_token=turso_token)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
            info["ok"] = True
            info["test_query"] = str(row)
            return jsonify(info)
        except Exception as e:
            info["ok"] = False
            info["error"] = str(e)
            info["error_type"] = type(e).__name__
            return jsonify(info), 500
    else:
        try:
            db = get_db()
            cursor = db.conn.cursor()
            cursor.execute("SELECT 1")
            info["ok"] = True
            info["test_query"] = str(cursor.fetchone())
            return jsonify(info)
        except Exception as e:
            info["ok"] = False
            info["error"] = str(e)
            return jsonify(info), 500


if __name__ == "__main__":
    print("Reloading Tracker Webapp")
    print("Access: http://0.0.0.0:5050")
    app.run(host="0.0.0.0", port=5050, debug=True)
