# 🛡️ JobShield — Student Job & Internship Scam Detector

**JobShield** is a modern Flask-based web application designed to protect students and job seekers from fraudulent postings. It implements a multi-layered verification system that leverages Machine Learning text classification, live website scraping, domain reputation checks, and candidate-facing behavioral quizzes.

---

## 🎯 Key Features

1. **Secure Authentication Flow**  
   - Complete signup, login, and logout flow using SQLite for database storage.
   - Hashed password management via `werkzeug.security` (SHA256).
   - Session protection using CSRF tokens and secure, HTTP-only, SameSite cookies.
   
2. **Protected Scanner Dashboard (`/detector`)**  
   - Accessible only to logged-in users.
   - Provides a unified web interface for scanning job posting texts, validating URLs, and taking the Red-Flag Quiz.

3. **Three-Layered Detection Engine**  
   - **ML Text Predictor (`/predict`)**: Scans job description text to detect vocabulary patterns characteristic of job scams.
   - **URL Scan & Live Scraper (`/scan-url`)**: Scrapes the live HTML contents of job links, extracts company metadata (via JSON-LD & OpenGraph), performs a domain safety assessment, and evaluates company legitimacy.
   - **Red-Flag Behavioral Quiz (`/quiz`)**: A weighted self-assessment quiz that evaluates job posting attributes (such as upfront fees, messaging-only recruiters, and bank details requested early).

4. **Production-Ready Security Standards**  
   - Enforced request-size limits (`JOBSHIELD_MAX_BODY_BYTES`).
   - Production mode requires a strong secret key.
   - Strict CORS policy controls.
   - Health monitoring endpoint (`/api/health`) reporting system readiness.

---

## 🏗️ System Architecture & Logic Flow

When a user runs a URL scan, JobShield performs the following deep analysis:

```
                  ┌──────────────────────────────┐
                  │      Submit Job Post URL     │
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                     Live Webpage HTML Scraper
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
    Domain Check            Company Info            Page Content
 ─────────────────      ───────────────────      ─────────────────
  • TLD Checks           • Parse Meta tags        • Regex Feature
  • Free-email keyword   • JSON-LD schemas          Engineering
  • Trust lists          • Legitimacy vs.         • TF-IDF Vectorizer
                           Scam Indicators        • Naive Bayes Model
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                                 ▼
                     Weighted Scoring & Penalties
                                 │
                                 ▼
                 ┌──────────────────────────────┐
                 │    Final Verdict:            │
                 │    GENUINE or FAKE Job       │
                 └──────────────────────────────┘
```

---

## 🧠 Machine Learning & Feature Engineering

JobShield uses a **Multinomial Naive Bayes** classifier trained on a custom-curated dataset of 63 representative job posts (32 fake and 31 genuine).

### Feature Engineering
Before TF-IDF vectorization, text is enriched using custom regex rules to inject semantic indicator tags:

*   **Scam Flags (`FAKE_IND_...`):**
    - `whatsapp_contact`: Recruiters demanding only Whatsapp/Telegram communication.
    - `registration_fee`/`payment_required`: Requests for application fees or security deposits.
    - `urgency_tactic`: Artificially compressed deadlines (e.g., "urgent hiring", "apply immediately").
    - `unrealistic_promise`: Guarantees of employment or unusually high payouts for low-skilled tasks.
*   **Trust Flags (`GENUINE_IND_...`):**
    - `official_channel`: Citations of official career portals or trusted platforms (LinkedIn, Indeed).
    - `no_fees`: Explicit statements that application/joining is free.
    - `official_email`: HR contact addresses hosted on dedicated corporate domains (e.g., `careers@company.com`).
    - `company_founded`/`company_location`: Standard corporate information like founding year or physical address.

### Model Parameters
*   **Vectorizer:** `TfidfVectorizer` (N-gram range: 1 to 2, lowercase, English stop words removed, capped at 500 features).
*   **Model:** `MultinomialNB(alpha=0.1)` (with lower alpha smoothing for improved discrimination on small datasets).

---

## 📁 Project Structure

```text
fake_job_detector/
├── backend/
│   ├── app.py                # Flask Backend & Routing (Auth + APIs)
│   ├── model.pkl             # Model artifact copy (backend folder)
│   └── vectorizer.pkl        # Vectorizer artifact copy (backend folder)
├── data/
│   └── job_posts.csv         # Core training dataset (63 samples)
├── frontend/                 # Legacy static-only frontend (kept for reference)
├── instance/
│   └── jobshield.db          # SQLite User DB (created dynamically)
├── static/                   # Static CSS & JS for Flask app
│   ├── script.js             # API request handling & UI updates
│   └── styles.css            # Responsive layout & custom styling
├── templates/                # Jinja2 HTML templates
│   ├── base.html             # Common navbar, footer, layout
│   ├── home.html             # Landing page
│   ├── login.html            # User login form
│   ├── signup.html           # User signup form
│   └── detector.html         # Protected scanner dashboard
├── tests/
│   └── test_api_basics.py    # Pytest test suite for basic API behavior
├── model.py                  # ML Model Training & Saving Script
├── test_cognifyz.py          # Integration test runner for URL scans
├── pyproject.toml            # Project & formatting settings
├── requirements.txt          # Python dependencies
└── README.md                 # Project Documentation
```

---

## ⚙️ Environment Configuration

JobShield can be configured via environment variables. Copy `.env.example` configurations before running:

| Variable | Description | Allowed Values | Default |
| :--- | :--- | :--- | :--- |
| `JOBSHIELD_ENV` | Running environment | `development`, `production` | `development` |
| `JOBSHIELD_DEBUG` | Flask debug logging | `1` (True), `0` (False) | `0` |
| `JOBSHIELD_SECRET` | Flask Session secret key | Strong random string (Required in production) | Dev fallback |
| `JOBSHIELD_CORS_ORIGINS` | Permitted API origins | Comma-separated domains | Disabled |
| `JOBSHIELD_MAX_BODY_BYTES` | Maximum payload size | Bytes (e.g., `65536` for 64KB) | `65536` |

### Setting Environment Variables (Example)

**Windows PowerShell:**
```powershell
$env:JOBSHIELD_ENV="development"
$env:JOBSHIELD_DEBUG="1"
$env:JOBSHIELD_SECRET="your-long-random-cryptographic-secret"
```

**Linux / macOS:**
```bash
export JOBSHIELD_ENV="development"
export JOBSHIELD_DEBUG="1"
export JOBSHIELD_SECRET="your-long-random-cryptographic-secret"
```

---

## 🚀 Getting Started

### 1. Prerequisites
Ensure you have Python 3.8+ installed.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Train the ML Model
Generate the model and vectorizer binary files (`model.pkl` and `vectorizer.pkl`) by running the training pipeline:
```bash
python model.py
```

### 4. Run the Flask Web Application
```bash
python backend/app.py
```
Open `http://127.0.0.1:5000` in your web browser.

---

## 🧪 Testing & Verification

### Automated Unit & Integration Tests
Run pytest to verify baseline API endpoints (health checks, quiz schema errors, etc.):
```bash
python -m pytest
```

### Live URL Scanning Integration Tests
To run live scanner integration tests against known domains (Cognifyz, Google, LinkedIn):
1. In one terminal, start the backend app:
   ```bash
   python backend/app.py
   ```
2. In a second terminal, execute the test script:
   ```bash
   python test_cognifyz.py
   ```

---

## 📡 API Reference (JSON)

### 1. Health Status Check
*   **Endpoint:** `GET /api/health`
*   **Description:** Returns API status and model initialization indicators.
*   **Response (`200 OK`):**
    ```json
    {
      "service": "JobShield API",
      "version": "1.0.0",
      "status": "ready"
    }
    ```

### 2. ML Text Classification
*   **Endpoint:** `POST /predict`
*   **Request Body:**
    ```json
    {
      "text": "Urgent hiring! Apply now on WhatsApp +91-XXXXX. 100% selection guarantee. Registration fee of Rs. 500 mandatory."
    }
    ```
*   **Response (`200 OK`):**
    ```json
    {
      "result": "FAKE",
      "risk_score": 0,
      "confidence": 1.0
    }
    ```

### 3. URL Scanning & Company Verification
*   **Endpoint:** `POST /scan-url`
*   **Request Body:**
    ```json
    {
      "url": "https://cognifyz.com/internships/"
    }
    ```
*   **Response (`200 OK`):**
    ```json
    {
      "mode": "url_scan",
      "url": "https://cognifyz.com/internships/",
      "result": "FAKE",
      "risk_score": 0,
      "confidence": 1.0,
      "company_info": {
        "name": "Cognifyz Technologies",
        "title": "Cognifyz Internships & Careers",
        "description": "Information on roles..."
      },
      "company_verification": {
        "name": "Cognifyz Technologies",
        "is_verified": false,
        "signals": [
          "Company name matches known suspicious fake company patterns",
          "Scam indicator present; company should not be trusted"
        ],
        "legitimate_indicators": 1,
        "scam_indicators": 1
      },
      "domain": {
        "hostname": "cognifyz.com",
        "is_trusted": false,
        "signals": [
          "Domain looks standard; still verify company + careers page."
        ],
        "risk_boost": 0
      },
      "text_preview": "Welcome to Cognifyz Technologies Internships page...",
      "note": "Deep analysis: ML score + domain analysis + company legitimacy verification. Always verify on official career sites."
    }
    ```

### 4. Interactive Behavioral Quiz
*   **Endpoint:** `POST /quiz`
*   **Request Body:**
    ```json
    {
      "answers": {
        "upfront_fee": true,
        "telegram_whatsapp_only": true,
        "unrealistic_pay": false,
        "bank_details_early": false,
        "no_company_identity": false,
        "urgent_pressure": true
      }
    }
    ```
*   **Response (`200 OK`):**
    ```json
    {
      "mode": "quiz",
      "risk_score": 38,
      "label": "HIGH RISK",
      "triggered_flags": [
        "upfront_fee",
        "telegram_whatsapp_only",
        "urgent_pressure"
      ],
      "max_possible": 100
    }
    ```

---

## 🛡️ Production Checklist

- [ ] Disable Flask debug mode (`JOBSHIELD_DEBUG=0`).
- [ ] Set `JOBSHIELD_ENV=production`.
- [ ] Change standard database storage path to a backed-up persistent filesystem location.
- [ ] Enforce a strong, random, and persistent `JOBSHIELD_SECRET` key.
- [ ] Configure `JOBSHIELD_CORS_ORIGINS` to allow requests only from specific frontend domains.
- [ ] Deploy the app behind a reverse proxy (e.g., NGINX) using a WSGI server (such as `gunicorn` or `waitress`).
