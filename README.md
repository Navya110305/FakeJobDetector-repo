# JobShield - Intelligent Student Job & Internship Scam Detector

![JobShield Banner](static/jobshield_banner.png)

**JobShield** is an advanced, student-focused web application designed to detect and flag fraudulent job and internship postings. With the rise of sophisticated recruitment scams targeting university students and fresh graduates, JobShield provides a multi-layered security scanner that combines Machine Learning (ML) text classification, live web page extraction, domain security analysis, and a structured behavioral self-assessment quiz.

---

## 🎯 Key Features

JobShield uses a **multi-layered hybrid detection engine** to evaluate the legitimacy of job listings.

```
                  ┌───────────────────────────────┐
                  │      Incoming Job Listing      │
                  └───────────────┬───────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  ML Text Scan   │      │    URL / TLD    │      │  Behavior Quiz  │
│  (Naive Bayes)  │      │   Reputation    │      │  (Interactive)  │
└────────┬────────┘      └────────┬────────┘      └────────┬────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  ▼
                     ┌─────────────────────────┐
                     │   Legitimacy Engine     │
                     │  (Weights & Penalties)  │
                     └────────────┬────────────┘
                                  ▼
                     ┌─────────────────────────┐
                     │    Scan Report Card     │
                     └─────────────────────────┘
```

1. **Machine Learning Classifier (`/predict`)**
   - Natural Language Processing (NLP) text classifier utilizing `TfidfVectorizer` (with bigrams) and a `MultinomialNB` (Naive Bayes) model.
   - Custom feature engineering pre-processor that injects weighted context tokens (`FAKE_IND_*` and `GENUINE_IND_*`) based on behavioral patterns.

2. **Dynamic URL & Web Scanner (`/scan-url`)**
   - Fetches and parses live job postings using robust scraping and HTML content parsing.
   - Extracts structured schema metadata (`JobPosting` and `Organization` JSON-LD or OpenGraph headers) to identify candidate-facing data.
   - **Domain Check**: Cross-references the hosting domain against known high-trust job boards and warns on suspicious top-level domains (TLDs like `.xyz`, `.top`, `.click`, `.tk`) or free-email hosts.
   - **Company Verification**: Looks for corporate trust signals (e.g., founding year, headquarters, privacy policies, leadership teams) versus recruitment red flags (upfront fees, chat-only communication, artificial urgency).

3. **Interactive Behavioral Quiz (`/quiz`)**
   - A client-side questionnaire assessing soft/process signals.
   - Weights responses based on risk factors (e.g., upfront payment requested, bank information asked before an interview, messaging-only recruiters) to return a diagnostic risk rating.

4. **Account-Based Access Control**
   - User signup and login routes secure the dashboard scanner using SQLite and Werkzeug password hashing.
   - Enforces protected routes (`/detector`) and secure cookie configurations.

---

## 🛠️ Technology Stack

- **Backend**: Python 3, Flask, SQLAlchemy (SQLite), BeautifulSoup4
- **Machine Learning**: Scikit-Learn, Joblib, Pandas
- **Frontend**: HTML5, Vanilla CSS3 (Modern Glassmorphism Design System), Javascript (ES6)
- **Testing & Tooling**: Pytest, Ruff

---

## ⚡ Quick Start

### 1. Installation

Clone the repository and set up a virtual environment:

```bash
# Clone the repository
git clone https://github.com/Prudhvi2206/FakeJobPostDetector.git
cd FakeJobPostDetector

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows (PowerShell):
venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Train the ML Model

Generate the classifier and vectorizer artifacts:

```bash
python model.py
```
*This updates `model.pkl` and `vectorizer.pkl` based on the balanced dataset in `data/job_posts.csv`.*

### 3. Run the Flask Web Application

Start the development server:

```bash
python backend/app.py
```
Open your browser and navigate to `http://127.0.0.1:5000`.

---

## ⚙️ Environment Configuration

JobShield reads the following environment variables from your session:

| Variable | Description | Default | Mode |
|----------|-------------|---------|------|
| `JOBSHIELD_ENV` | App mode (`development` or `production`) | `development` | All |
| `JOBSHIELD_DEBUG` | Enables debug logging and interactive reload | `0` (False) | Dev |
| `JOBSHIELD_SECRET` | Secret key used for session cryptographic signatures | (Required in prod) | Prod |
| `JOBSHIELD_CORS_ORIGINS` | Comma-separated list of allowed origins | (Disables CORS if empty) | Prod |
| `JOBSHIELD_MAX_BODY_BYTES` | Maximum allowed request payload body in bytes | `65536` | All |

### Windows PowerShell Example:
```powershell
$env:JOBSHIELD_ENV="development"
$env:JOBSHIELD_DEBUG="1"
$env:JOBSHIELD_SECRET="a-very-long-secure-random-secret-key"
python backend/app.py
```

---

## 🔬 Machine Learning Features

The model categorizes listings by searching for linguistic indicators prior to Naive Bayes probability matching:

### FAKE Job Indicators:
- **Known Fake/Clone Names**: `codesoft`, `cognifyz`, `apex`, etc.
- **Messaging-Only Contacts**: Only Telegram or WhatsApp hiring channels.
- **Upfront Fees**: Join fees, training kit deposits, or device investments.
- **Urgency/Scarcity**: Urging candidates to pay or enroll due to "limited seats".
- **Unrealistic Promises**: "100% placement guarantees" or "easy income".

### GENUINE Job Indicators:
- **Verified Domains**: Official corporate careers paths or standard job boards.
- **Legitimate Email Formats**: Application portals requesting resumes sent to `@company.com`.
- **Corporate Transparency**: Mentions of company founding dates, headquarters, team descriptions, and privacy policies.

---

## 🧪 Testing & Verification

Ensure your environment complies with code standards and all tests pass:

### 1. Run Unit Tests (Pytest)
```bash
python -m pytest
```
*This validates API schemas, session security baselines, and quiz logic.*

### 2. Run URL Scanner Validation
Execute the pre-defined target verification script:
```bash
python test_cognifyz.py
```
*This script tests real-world URL behaviors against the local backend server (requires Flask running).*

### 3. Lint Codebase
Validate style conventions:
```bash
python -m ruff check .
```

---

## 🔌 API Reference (JSON)

### 1. Health Status Check
- **Endpoint**: `GET /api/health`
- **Response**:
```json
{
  "service": "JobShield API",
  "version": "1.0.0",
  "status": "ready"
}
```

### 2. Predict Text Content Risk
- **Endpoint**: `POST /predict`
- **Body**: `{ "text": "Urgent recruitment! Pay 500 Rupees registration fee for WhatsApp work from home typing job. 100% guaranteed income!" }`
- **Response**:
```json
{
  "result": "FAKE",
  "risk_score": 0,
  "confidence": 1.0
}
```

### 3. Scan Webpage / URL
- **Endpoint**: `POST /scan-url`
- **Body**: `{ "url": "https://careers.google.com/" }`
- **Response**:
```json
{
  "mode": "url_scan",
  "url": "https://careers.google.com/",
  "result": "GENUINE",
  "risk_score": 100,
  "confidence": 1.0,
  "company_verification": {
    "name": "Google",
    "is_verified": true,
    "legitimate_indicators": 5,
    "scam_indicators": 0,
    "signals": [
      "Company background information provided",
      "Physical office location mentioned",
      "Company name appears in page text",
      "Domain name matches company name"
    ]
  },
  "domain": {
    "hostname": "careers.google.com",
    "is_trusted": true,
    "signals": [
      "Verified top-tier company or trusted applicant tracking system."
    ]
  },
  "note": "Deep analysis: ML score + domain analysis + company legitimacy verification. Always verify on official career sites."
}
```

### 4. Behavioral Quiz Evaluate
- **Endpoint**: `POST /quiz`
- **Body**:
```json
{
  "answers": {
    "upfront_fee": true,
    "telegram_whatsapp_only": true,
    "unrealistic_pay": false
  }
}
```
- **Response**:
```json
{
  "mode": "quiz",
  "risk_score": 50,
  "label": "SUSPICIOUS",
  "triggered_flags": [
    "upfront_fee",
    "telegram_whatsapp_only"
  ],
  "max_possible": 100
}
```

---

## 🔒 Production Guidelines

- **Always turn off debug mode** (`JOBSHIELD_DEBUG=0`).
- Ensure `JOBSHIELD_SECRET` is set to a cryptographically strong, random string.
- Restrict `JOBSHIELD_CORS_ORIGINS` to your production frontend URLs.
- Run the server behind a secure WSGI server (such as `gunicorn` or `waitress`) and use an Nginx/Apache reverse proxy to handle HTTPS/SSL termination.
