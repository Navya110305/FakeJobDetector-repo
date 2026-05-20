import logging
import os
import re
import json
import secrets
from bs4 import BeautifulSoup
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Optional, Tuple
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

KNOWN_FAKE_DOMAINS = frozenset({"cognifyz.com", "codesoft.com", "codsoft.com", "apex.com"})
KNOWN_FAKE_COMPANY_NAMES = frozenset({"cognifyz", "codesoft", "codsoft", "apex", "quickhirepro", "instantjobgate", "earnmorenow"})

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


def json_error(message, status_code=400, details=None):
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


def extract_features(text: str) -> str:
    """Extract additional features indicating fake jobs."""
    text_lower = text.lower()
    features = text
    
    # Add explicit fake job indicators with high weight
    fake_indicators = [
        r'\b(cognifyz|codesoft|apex|quickhirepro|instantjobgate|earnmorenow)\b',  # Known fake company names
        r'\b(whatsapp|telegram|viber|signal)\b',  # Suspicious communication
        r'\b(payment|fee|charge|rupee|deposit|bitcoin|crypto)\b',  # Payment required
        r'\b(urgent|limited\s+seats?|immediate|fast\s+hiring)\b',  # Pressure tactics
        r'\b(guarantee|guaranteed|100%)\b',  # Unrealistic promises
        r'\b(registration|signup|join|enroll)\s*(fee|payment|charge)\b',  # Registration fee
    ]
    
    for indicator in fake_indicators:
        if re.search(indicator, text_lower):
            features += " FAKE_INDICATOR " + indicator.replace("\\b", "").replace("\\s", " ")
    
    # Add explicit genuine job indicators
    genuine_indicators = [
        r'\b(official|careers?\s*page|careers?\.?com|linkedin|verified)\b',  # Official channels
        r'\b(no\s+fee|free|no\s+payment|no\s+charge|no\s+cost)\b',  # No fees
        r'\b(apply\s+(directly|online|here)|send\s+resume|send\s+cv)\b',  # Direct application
        r'\b(hr@|careers@|jobs@|recruiting@|contact@)\b',  # Official email
    ]
    
    for indicator in genuine_indicators:
        if re.search(indicator, text_lower):
            features += " GENUINE_INDICATOR " + indicator.replace("\\b", "").replace("\\s", " ")
    
    return features


def predict_from_text(text, url=None):
    text_lower = text.lower()
    if any(name in text_lower for name in KNOWN_FAKE_COMPANY_NAMES):
        return {
            "result": "FAKE",
            "risk_score": 0,
            "confidence": 1.0,
        }

    if url:
        parsed = urlparse(url)
        if parsed.netloc in KNOWN_FAKE_DOMAINS:
            return {
                "result": "FAKE",
                "risk_score": 0,
                "confidence": 1.0,
            }

    # Apply feature extraction like training, including URL content if available
    combined_text = text.strip()
    if url:
        combined_text += " " + url.strip()
    enhanced_text = extract_features(combined_text)
    vector = vectorizer.transform([enhanced_text])
    prediction = int(model.predict(vector)[0])

    confidence = None
    prob_fake = None
    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(vector)[0]
        # probabilities[0] = P(genuine), probabilities[1] = P(fake)
        prob_genuine = float(probabilities[0])
        prob_fake = float(probabilities[1])
        confidence = float(max(probabilities))

    result = "FAKE" if prediction == 1 else "GENUINE"
    
    # Display score as classification confidence percent.
    if prob_fake is not None:
        score = int(round(max(prob_genuine, prob_fake) * 100))
    else:
        score = 100 if prediction == 0 else 100

    if score == 100:
        confidence = 1.0

    return {
        "result": result,
        "risk_score": score,
        "confidence": confidence,
    }


def fetch_html_text(url):
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
        with urlopen(req, timeout=12) as resp:
            raw = resp.read()
    except (URLError, HTTPError, ValueError, OSError) as exc:
        return "", {}, str(exc)

    try:
        html = raw.decode("utf-8", errors="ignore")
    except Exception:
        html = raw.decode("latin-1", errors="ignore")

    soup = BeautifulSoup(html, "html.parser")
    company_info = {}

    # Extract company name from structured data
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                graph = item.get("@graph", [item])
                for g in graph:
                    atype = g.get("@type", "")
                    if "JobPosting" in atype:
                        hiring_org = g.get("hiringOrganization", {})
                        if isinstance(hiring_org, dict) and hiring_org.get("name"):
                            company_info["name"] = hiring_org.get("name")
                        if g.get("title"):
                            company_info["job_title"] = g.get("title")
                    elif "Organization" in atype:
                        if g.get("name") and not company_info.get("name"):
                            company_info["name"] = g.get("name")
        except Exception:
            pass

    # Extract company name from meta tags
    if not company_info.get("name"):
        og_site_name = soup.find("meta", property="og:site_name")
        if og_site_name and og_site_name.get("content"):
            company_info["name"] = og_site_name["content"]

    # Extract page title and description
    company_info["title"] = soup.title.string.strip() if soup.title and soup.title.string else ""
    
    desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", property="og:description")
    if desc_tag and desc_tag.get("content"):
        company_info["description"] = desc_tag["content"].strip()

    # Extract all text more thoroughly
    # Remove script and style tags
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.I)
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.I)
    
    # Extract text from all elements
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    
    # Limit to first 20000 chars
    if len(text) > 20000:
        text = text[:20000]
    
    return text, company_info, None


def analyze_domain(hostname: str) -> dict:
    host = (hostname or "").lower().strip()
    signals = []
    risk_boost = 0
    is_trusted = False

    if not host:
        return {"hostname": "", "signals": ["Could not resolve domain."], "risk_boost": 10, "is_trusted": False}

    if host.startswith("www."):
        host = host[4:]

    TRUSTED_DOMAINS = {
        "google.com", "microsoft.com", "apple.com", "amazon.jobs", 
        "meta.com", "netflix.com", "linkedin.com", "lever.co", 
        "greenhouse.io", "workday.com", "myworkdayjobs.com", 
        "icims.com", "careers.google.com"
    }

    for td in TRUSTED_DOMAINS:
        if host == td or host.endswith("." + td):
            is_trusted = True
            break
            
    if is_trusted:
        signals.append("Verified top-tier company or trusted applicant tracking system.")
        risk_boost -= 20
    else:
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

    return {"hostname": host, "signals": signals, "risk_boost": risk_boost, "is_trusted": is_trusted}


def verify_company_legitimacy(company_name: str, domain: str, page_text: str) -> dict:
    """Verify if a company is legitimate based on name, domain, and page content."""
    company_lower = (company_name or "").lower().strip()
    domain_clean = domain.lower().replace("www.", "").replace("https://", "").replace("http://", "")
    domain_base = domain_clean.split("/")[0].split(".")[0]  # Get main domain name
    
    signals = []
    risk_boost = 0
    is_verified = False
    
    if not company_name:
        signals.append("Could not identify company name from page.")
        risk_boost += 15
        return {"company_name": company_name, "signals": signals, "risk_boost": risk_boost, "is_verified": is_verified}
    
    # Check company legitimacy indicators
    page_text_lower = page_text.lower()
    
    # Strong legitimacy signals
    legitimate_signals = [
        (r'\bfounded\s+in\s+\d{4}', "Company founding year mentioned"),
        (r'\b(ceo|founder|leadership|team|about\s+us)\b', "Company background information provided"),
        (r'\b(headquarters?|office\s+location|address)\b', "Physical office location mentioned"),
        (r'\b(awards?|certifications?|recognized|accredited)\b', "Awards or certifications listed"),
        (r'\b(employees?|staff|team\s+member)\b', "Employee information present"),
        (r'\b(client|partner|customers?)\b', "Client/customer references found"),
        (r'\b(privacy\s+policy|terms\s+of\s+service|contact\s+us)\b', "Legal pages available"),
    ]
    
    legitimate_count = 0
    for pattern, signal_text in legitimate_signals:
        if re.search(pattern, page_text_lower):
            legitimate_count += 1
            signals.append(signal_text)
    
    # Scam red flags
    scam_patterns = [
        (r'\b(whatsapp|telegram|viber|wechat)\s*(only|contact|number)\b', "Communication only through messaging apps"),
        (r'(payment|fee|charges?|deposit|investment)\s*(required|needed|payment)\b', "Payment required upfront"),
        (r'\b(guarantee|100%|assured)\s*(job|income|earning)\b', "Unrealistic guarantees"),
        (r'\b(urgently?|immediately|last\s+(minute|moment))\b', "Artificial urgency"),
        (r'\b(work\s+from\s+home|wfh|remote)\s+(no\s+)?(investment|fee)\b', "Work from home with investment"),
        (r'\b(no\s+experience|no\s+qualification|no\s+education)\s*(required|needed)\b', "Unrealistic job requirements"),
    ]
    
    scam_count = 0
    for pattern, signal_text in scam_patterns:
        if re.search(pattern, page_text_lower):
            scam_count += 1
            signals.append(signal_text)

    company_mentioned = company_lower in page_text_lower
    if company_mentioned:
        signals.append("Company name appears in page text")
    else:
        signals.append("Company name not clearly present in page text")
        risk_boost += 5

    # Check domain-company name match
    domain_match = domain_base in company_lower or company_lower in domain_base
    if domain_match:
        signals.append("Domain name matches company name")
        risk_boost -= 5
    else:
        signals.append(f"Domain '{domain_base}' doesn't match company '{company_lower}'")
        risk_boost += 8

    # Suspicious domain keywords in URL
    suspicious_domain_tokens = {
        "job", "career", "apply", "hiring", "intern", "placement", "earn", "money", "pay", "recruit", "staff"
    }
    if any(token in domain_clean for token in suspicious_domain_tokens):
        signals.append("Domain contains suspicious job-related keywords")
        risk_boost += 8

    known_fake_names = {"cognifyz", "codesoft", "apex", "quickhirepro", "instantjobgate", "earnmorenow"}
    if company_lower in known_fake_names:
        signals.append("Company name matches known suspicious fake company patterns")
        risk_boost += 20

    # Assess overall legitimacy
    if scam_count >= 1:
        signals.append("Scam indicator present; company should not be trusted")
        risk_boost += 20
        is_verified = False
    elif legitimate_count >= 3 and domain_match and company_mentioned:
        signals.append("Multiple legitimacy indicators found and company/domain match confirmed")
        is_verified = True
        risk_boost -= 15
    elif legitimate_count >= 4:
        signals.append("Many legitimacy indicators found")
        is_verified = True
        risk_boost -= 10
    elif legitimate_count >= 2 and (domain_match or company_mentioned):
        signals.append("Some legitimacy indicators found; treat company as unverified until more evidence appears")
        risk_boost -= 5
    else:
        if not domain_match:
            signals.append("Company/domain match is weak, treat as unverified")
        if not company_mentioned:
            signals.append("Company name is not verified on the page")
        risk_boost += scam_count * 8
    
    return {
        "company_name": company_name,
        "signals": signals,
        "risk_boost": risk_boost,
        "is_verified": is_verified,
        "legitimate_indicators": legitimate_count,
        "scam_indicators": scam_count
    }



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
    page_text, company_info, fetch_error = fetch_html_text(raw_url)

    response = {
        "mode": "url_scan",
        "url": raw_url,
        "domain": domain_info,
        "company_info": company_info,
        "fetch_error": fetch_error,
        "text_preview": "",
    }

    if fetch_error or len(page_text) < 80:
        response["result"] = "FAKE"
        response["risk_score"] = 0
        response["confidence"] = 1.0
        if parsed.netloc in KNOWN_FAKE_DOMAINS:
            response["note"] = (
                "Known fake domain detected. This site is flagged as fraudulent even if content is not readable."
            )
        else:
            response["note"] = (
                "Could not read enough text from this page (login wall, blocked, or PDF). "
                "Unknown or unreadable pages are treated as fake to avoid false trust."
            )
        return jsonify(response)

    enhanced_text = page_text
    extracted_company = company_info.get("name", "")
    
    if extracted_company:
        enhanced_text += f"\nCompany: {extracted_company} {company_info.get('job_title', '')} {company_info.get('description', '')}"

    ml = predict_from_text(enhanced_text, raw_url)

    if parsed.netloc in KNOWN_FAKE_DOMAINS:
        ml["result"] = "FAKE"
        ml["risk_score"] = 0
        ml["confidence"] = 1.0

    # Verify company legitimacy
    company_verification = verify_company_legitimacy(
        extracted_company,
        parsed.netloc,
        page_text
    )
    
    # Combine all signals
    base_risk_score = ml["risk_score"]
    domain_risk = domain_info.get("risk_boost", 0)
    company_risk = company_verification.get("risk_boost", 0)
    
    combined = base_risk_score
    
    if domain_info.get("is_trusted"):
        combined = min(100, combined + 15)

    combined = max(0, combined - abs(domain_risk))
    combined = max(0, combined - abs(company_risk))

    if company_verification.get("is_verified"):
        combined = min(100, combined + 10)

    if company_verification.get("scam_indicators", 0) >= 1 and not company_verification.get("is_verified"):
        ml["result"] = "FAKE"
        combined = 0

    if ml["result"] == "GENUINE":
        combined = 100
        ml["confidence"] = 1.0
    elif ml["result"] == "FAKE":
        combined = 0
        ml["confidence"] = 1.0

    # Add company verification details to response
    response["text_preview"] = page_text[:400] + ("..." if len(page_text) > 400 else "")
    response["result"] = ml["result"]
    response["risk_score"] = combined
    response["confidence"] = ml["confidence"]
    response["company_verification"] = {
        "name": company_verification.get("company_name", "Unknown"),
        "is_verified": company_verification.get("is_verified"),
        "signals": company_verification.get("signals", []),
        "legitimate_indicators": company_verification.get("legitimate_indicators", 0),
        "scam_indicators": company_verification.get("scam_indicators", 0),
    }
    response["note"] = (
        "Deep analysis: ML score + domain analysis + company legitimacy verification. "
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

    trust_total = 100 - min(total, 100)
    if trust_total <= 45:
        label = "HIGH RISK"
    elif trust_total <= 70:
        label = "SUSPICIOUS"
    else:
        label = "LOWER RISK (still verify)"

    return jsonify(
        {
            "mode": "quiz",
            "risk_score": trust_total,
            "label": label,
            "triggered_flags": triggered,
            "max_possible": 100,
        }
    )


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=DEBUG_MODE)
