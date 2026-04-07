import logging
import os
import re
import secrets
from datetime import datetime
from functools import wraps
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import joblib
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = INSTANCE_DIR / "jobshield.db"

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
    static_url_path="/static",
)
APP_ENV = os.environ.get("JOBSHIELD_ENV", "development").strip().lower()
DEBUG_MODE = os.environ.get("JOBSHIELD_DEBUG", "0").strip().lower() in {"1", "true", "yes", "on"}
secret_key = os.environ.get("JOBSHIELD_SECRET", "").strip()
if not secret_key:
    if APP_ENV == "development":
        secret_key = "dev-change-me-in-production"
    else:
        raise RuntimeError("Missing JOBSHIELD_SECRET. Set a strong random secret in environment.")

app.config["SECRET_KEY"] = secret_key
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + str(DB_PATH.resolve()).replace("\\", "/")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("JOBSHIELD_MAX_BODY_BYTES", "65536"))
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = APP_ENV != "development"

db = SQLAlchemy(app)
cors_origins = os.environ.get("JOBSHIELD_CORS_ORIGINS", "").strip()
if cors_origins:
    allowed_origins = [x.strip() for x in cors_origins.split(",") if x.strip()]
    CORS(app, resources={r"/*": {"origins": allowed_origins}})

MODEL_PATH = BASE_DIR / "model.pkl"
VECTORIZER_PATH = BASE_DIR / "vectorizer.pkl"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

QUIZ_WEIGHTS = {
    "upfront_fee": 28,
    "telegram_whatsapp_only": 22,
    "unrealistic_pay": 18,
    "bank_details_early": 26,
    "no_company_identity": 16,
    "urgent_pressure": 12,
}

SUSPICIOUS_TLDS = frozenset({".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top", ".click"})

logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("jobshield")


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


def get_csrf_token() -> str:
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    session.modified = True
    return session["csrf_token"]


def validate_csrf() -> bool:
    return request.form.get("csrf_token") == session.get("csrf_token")


@app.context_processor
def inject_csrf():
    return dict(csrf_token=get_csrf_token)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access the scanner.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def json_error(message: str, status_code: int = 400, details: str | None = None):
    payload = {"error": message}
    if details:
        payload["details"] = details
    return jsonify(payload), status_code


@app.errorhandler(413)
def payload_too_large(_):
    return json_error("Payload too large. Please submit a smaller request body.", 413)


@app.errorhandler(500)
def internal_error(exc):
    logger.exception("Unhandled server error: %s", exc)
    return json_error("Internal server error. Please try again later.", 500)


def load_artifacts():
    if not MODEL_PATH.exists() or not VECTORIZER_PATH.exists():
        raise FileNotFoundError(
            "Model artifacts not found. Run `python model.py` first to generate "
            "model.pkl and vectorizer.pkl."
        )
    model_obj = joblib.load(MODEL_PATH)
    vectorizer_obj = joblib.load(VECTORIZER_PATH)
    return model_obj, vectorizer_obj


try:
    model, vectorizer = load_artifacts()
except FileNotFoundError as exc:
    model, vectorizer = None, None
    MODEL_LOAD_ERROR = str(exc)
else:
    MODEL_LOAD_ERROR = None


def predict_from_text(text: str) -> dict:
    vector = vectorizer.transform([text])
    prediction = int(model.predict(vector)[0])

    confidence = None
    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(vector)[0]
        confidence = float(max(probabilities))

    result = "FAKE" if prediction == 1 else "GENUINE"
    risk_score = int(round((confidence or 0.5) * 100))
    if result == "GENUINE":
        risk_score = 100 - risk_score

    return {
        "result": result,
        "risk_score": risk_score,
        "confidence": confidence,
    }


def fetch_html_text(url: str) -> tuple[str, str | None]:
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
        with urlopen(req, timeout=12) as resp:
            raw = resp.read()
    except (URLError, HTTPError, ValueError, OSError) as exc:
        return "", str(exc)

    try:
        html = raw.decode("utf-8", errors="ignore")
    except Exception:
        html = raw.decode("latin-1", errors="ignore")

    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.I)
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 20000:
        text = text[:20000]
    return text, None


def analyze_domain(hostname: str) -> dict:
    host = (hostname or "").lower().strip()
    signals = []
    risk_boost = 0

    if not host:
        return {"hostname": "", "signals": ["Could not resolve domain."], "risk_boost": 10}

    if host.startswith("www."):
        host = host[4:]

    tld = "." + host.split(".")[-1] if "." in host else ""
    if any(host.endswith(s) for s in SUSPICIOUS_TLDS):
        signals.append(f"Uses a commonly abused TLD ({tld}).")
        risk_boost += 12

    free_keywords = ("gmail", "yahoo", "hotmail", "outlook", "protonmail", "icloud")
    if any(k in host for k in free_keywords):
        signals.append("Domain looks like a free-email style host (unusual for official careers).")
        risk_boost += 15

    if not signals:
        signals.append("Domain looks standard; still verify company + careers page.")

    return {"hostname": host, "signals": signals, "risk_boost": risk_boost}


@app.get("/")
def home():
    return render_template("home.html")


@app.get("/login")
def login():
    if "user_id" in session:
        return redirect(url_for("detector"))
    next_url = request.args.get("next") or ""
    return render_template("login.html", next_url=next_url)


@app.post("/login")
def login_post():
    if not validate_csrf():
        flash("Invalid session. Please try again.", "error")
        return redirect(url_for("login"))

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    next_url = (request.form.get("next") or request.args.get("next") or "").strip()

    if not email or not password:
        flash("Email and password are required.", "error")
        return redirect(url_for("login"))

    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        flash("Invalid email or password.", "error")
        return redirect(url_for("login"))

    session["user_id"] = user.id
    session["user_email"] = user.email
    session["user_name"] = user.full_name or user.email.split("@")[0]
    session.pop("csrf_token", None)
    flash("Welcome back.", "success")

    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect(url_for("detector"))


@app.get("/signup")
def signup():
    if "user_id" in session:
        return redirect(url_for("detector"))
    return render_template("signup.html")


@app.post("/signup")
def signup_post():
    if not validate_csrf():
        flash("Invalid session. Please try again.", "error")
        return redirect(url_for("signup"))

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    password2 = request.form.get("password_confirm") or ""
    full_name = (request.form.get("full_name") or "").strip()

    if not email or not password:
        flash("Email and password are required.", "error")
        return redirect(url_for("signup"))

    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        flash("Please enter a valid email address.", "error")
        return redirect(url_for("signup"))

    if len(password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return redirect(url_for("signup"))

    if password != password2:
        flash("Passwords do not match.", "error")
        return redirect(url_for("signup"))

    if User.query.filter_by(email=email).first():
        flash("An account with this email already exists.", "error")
        return redirect(url_for("signup"))

    user = User(email=email, full_name=full_name or None)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    session["user_id"] = user.id
    session["user_email"] = user.email
    session["user_name"] = user.full_name or user.email.split("@")[0]
    session.pop("csrf_token", None)
    flash("Account created. You can start scanning.", "success")
    return redirect(url_for("detector"))


@app.get("/logout")
def logout_redirect():
    return redirect(url_for("home"))


@app.post("/logout")
def logout():
    if not validate_csrf():
        flash("Invalid session. Please try again.", "error")
        return redirect(url_for("home"))
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.get("/detector")
@login_required
def detector():
    return render_template("detector.html")


@app.get("/api/health")
def api_health():
    status = "ready" if model and vectorizer else "missing_model"
    return jsonify(
        {
            "service": "JobShield API",
            "version": "1.0.0",
            "status": status,
        }
    )


@app.post("/predict")
def predict():
    if model is None or vectorizer is None:
        return json_error("Model not available", 500, MODEL_LOAD_ERROR)

    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()

    if not text:
        return json_error("Please provide non-empty `text` field.")

    return jsonify(predict_from_text(text))


@app.post("/scan-url")
def scan_url():
    if model is None or vectorizer is None:
        return json_error("Model not available", 500, MODEL_LOAD_ERROR)

    data = request.get_json(silent=True) or {}
    raw_url = (data.get("url") or "").strip()
    if not raw_url:
        return json_error("Please provide `url`.")

    if not raw_url.startswith(("http://", "https://")):
        raw_url = "https://" + raw_url

    parsed = urlparse(raw_url)
    if not parsed.netloc:
        return json_error("Invalid URL.")

    domain_info = analyze_domain(parsed.netloc)
    page_text, fetch_error = fetch_html_text(raw_url)

    response = {
        "mode": "url_scan",
        "url": raw_url,
        "domain": domain_info,
        "fetch_error": fetch_error,
        "text_preview": "",
    }

    if fetch_error or len(page_text) < 80:
        response["result"] = "UNKNOWN"
        response["risk_score"] = min(50 + domain_info["risk_boost"], 95)
        response["confidence"] = None
        response["note"] = (
            "Could not read enough text from this page (login wall, blocked, or PDF). "
            "Domain checks still apply; try pasting text or use the Red-Flag Quiz."
        )
        return jsonify(response)

    ml = predict_from_text(page_text)
    combined = min(100, ml["risk_score"] + domain_info["risk_boost"] // 2)

    response["text_preview"] = page_text[:400] + ("..." if len(page_text) > 400 else "")
    response["result"] = ml["result"]
    response["risk_score"] = combined
    response["confidence"] = ml["confidence"]
    response["note"] = (
        "Combined ML score on fetched page text + domain signals. "
        "Always verify on official career sites."
    )
    return jsonify(response)


@app.post("/quiz")
def quiz_score():
    data = request.get_json(silent=True) or {}
    answers = data.get("answers") or {}

    if not isinstance(answers, dict):
        return json_error("Provide `answers` as an object of question_id: true/false.")

    total = 0
    triggered = []
    for qid, weight in QUIZ_WEIGHTS.items():
        if answers.get(qid) is True:
            total += weight
            triggered.append(qid)

    total = min(total, 100)
    if total >= 55:
        label = "HIGH RISK"
    elif total >= 28:
        label = "SUSPICIOUS"
    else:
        label = "LOWER RISK (still verify)"

    return jsonify(
        {
            "mode": "quiz",
            "risk_score": total,
            "label": label,
            "triggered_flags": triggered,
            "max_possible": 100,
        }
    )


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=DEBUG_MODE)
