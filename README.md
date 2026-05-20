# 🛡️ JobShield — Intelligent Student Job & Internship Scam Detector

JobShield is a professional, multi-layered security web application designed to protect students and job seekers from fraudulent job offers and internship scams. By combining **machine learning text classification**, **live webpage scraping**, **domain reputation analysis**, and a **weighted red-flag diagnostic quiz**, JobShield provides a highly accurate risk assessment for job postings.

---

## 🎯 The Problem & Our Solution

Employment scams targeting students are at an all-time high, often tricking victims into paying "registration fees" or revealing sensitive banking details. Standard ML classifiers can fail if the scammer writes a polished job description. 

**JobShield** addresses this with a **hybrid, multi-layered verification system**:
1. **Machine Learning Classifier**: Analyzes job description text for subtle lexical scam patterns.
2. **Domain Reputation Analyzer**: Evaluates the safety, suspicious TLDs, and keyword abuse of the hosting domain.
3. **Company Legitimacy Verifier**: Checks for verified corporate markers (founding year, leadership, legal policies) vs. scam indicators (WhatsApp/Telegram-only contact, upfront payment demands).
4. **Behavioral Red-Flag Quiz**: A user-facing interactive diagnostic quiz that scores risk based on candidate experiences.

---

## 🏗️ System Architecture & Workflow

```
                        +----------------------------+
                        |      User Input (URL)      |
                        +--------------+-------------+
                                       |
                                       v
                        +--------------+-------------+
                        |   Fetch Live Page Content  |
                        +--------------+-------------+
                                       |
           +---------------------------+---------------------------+
           |                           |                           |
           v                           v                           v
+----------+----------+     +----------+----------+     +----------+----------+
|  Domain Analysis    |     |  Company Legitimacy |     |   ML Text Classifier |
|  - TLD validation   |     |  - Scam flags       |     |   - Naive Bayes      |
|  - Email check      |     |  - Legitimacy flags |     |   - Feature tags     |
+----------+----------+     +----------+----------+     +----------+----------+
           |                           |                           |
           +---------------------------+---------------------------+
                                       |
                                       v
                        +--------------+-------------+
                        |   Hybrid Risk-Scoring Engine|
                        |   - Penalty/Boost logic    |
                        +--------------+-------------+
                                       |
                                       v
                        +--------------+-------------+
                        |   Verification Report      |
                        |   (Result: FAKE/GENUINE)   |
                        +----------------------------+
```

---

## ✨ Core Features

*   **🔒 Account-Based Access**: Complete registration, login, and session management system using SQLite, SQLAlchemy, and password hashing (via `Werkzeug`).
*   **📊 Integrated Job Scanner Dashboard**: A protected workspace where authenticated users can inspect raw text or live URLs.
*   **🌐 Live URL Scraping**: Automatically extracts metadata (such as Schema.org `JobPosting` and `Organization` JSON-LD structures) and cleans webpage body text for analysis.
*   **🧠 Advanced Text Feature Engineering**: Infuses the Naive Bayes model with customized indicators (e.g., WhatsApp hiring, upfront payment, domain match, and verified office location).
*   **📝 Diagnostic Risk Quiz**: A weighted questionnaire scoring indicators like upfront payment, messaging-app communication, and early bank details requests.
*   **⚡ Production-Ready Security Defaults**: Includes CSRF validation on forms, security-hardened session cookies, HTTPOnly flags, and strict request payload sizing limits.

---

## 🛠️ Technology Stack

*   **Backend**: Python, Flask, Flask-SQLAlchemy, Flask-CORS
*   **Machine Learning**: Scikit-Learn (Multinomial Naive Bayes, TF-IDF Vectorizer with bigrams), Pandas, Joblib
*   **Web Scraping**: BeautifulSoup4, urllib
*   **Database**: SQLite (SQLAlchemy ORM)
*   **Frontend**: HTML5, Vanilla CSS3 (curated dark mode and premium glassmorphism), Vanilla Javascript (ES6+)

---

## ⚙️ Environment Configuration

JobShield uses environment variables for secure and flexible configuration. Copy the following keys to your shell session or define them in a `.env` file (see `.env.example`):

| Variable | Description | Default (Dev) |
| :--- | :--- | :--- |
| `JOBSHIELD_ENV` | Application environment (`development` or `production`) | `development` |
| `JOBSHIELD_DEBUG` | Enables debug logging and interactive debugger (`1` or `0`) | `0` |
| `JOBSHIELD_SECRET` | Required Flask session secret key (generate a strong random string) | *Dev fallback* |
| `JOBSHIELD_CORS_ORIGINS` | Comma-separated list of allowed origins | `*` (if empty, CORS disabled) |
| `JOBSHIELD_MAX_BODY_BYTES` | Maximum allowed request body size in bytes | `65536` (64KB) |

Example configuration in Windows PowerShell:
```powershell
$env:JOBSHIELD_ENV="development"
$env:JOBSHIELD_DEBUG="1"
$env:JOBSHIELD_SECRET="a-very-long-secure-random-string-for-flask"
```

---

## 🚀 Getting Started

### 1. Prerequisites
Make sure you have **Python 3.8+** installed on your system.

### 2. Set Up Virtual Environment
Initialize a virtual environment to keep dependencies isolated:
```bash
# Create virtual environment
python -m venv venv

# Activate on Windows (CMD/PowerShell)
.\venv\Scripts\activate

# Activate on Unix/macOS
source venv/bin/activate
```

### 3. Install Dependencies
Install all required libraries and dependencies:
```bash
pip install -r requirements.txt
```

### 4. Train the Machine Learning Model
Train the Multinomial Naive Bayes classifier on the labeled job dataset (`data/job_posts.csv`):
```bash
python model.py
```
*This command outputs the training metrics and exports `model.pkl` and `vectorizer.pkl` to the root directory.*

### 5. Run the Application
Start the Flask backend web server:
```bash
python backend/app.py
```
Navigate to **`http://127.0.0.1:5000`** in your browser.

---

## 🔍 Heuristics & Feature Engineering Details

### 1. ML Feature Enrichment
Before vectorization, raw job descriptions are passed through `extract_features()` which appends markers to the text:
*   **Fake Markers**: `FAKE_IND_whatsapp_contact`, `FAKE_IND_registration_fee`, `FAKE_IND_payment_required`, `FAKE_IND_urgency_tactic`, `FAKE_IND_unrealistic_promise`
*   **Genuine Markers**: `GENUINE_IND_official_channel`, `GENUINE_IND_career_domain`, `GENUINE_IND_no_fees`, `GENUINE_IND_direct_apply`, `GENUINE_IND_official_email`

### 2. Hybrid Scoring Rules
```python
Combined Score = ML_Score - abs(Domain_Penalty) - abs(Company_Penalty) + Trusted_Domain_Bonus + Company_Verified_Bonus
```
*   If a scam indicator (e.g. upfront fee required) is confirmed and the company is unverified, the risk score is automatically set to `0` (identified as **FAKE**).
*   If a domain matches a verified top-tier brand, a positive boost is applied to the confidence level.

---

## 🧪 Testing & Code Quality

### Automated Unit Tests
To run the automated API and unit test suite:
```bash
python -m pytest
```

### URL Scanning Integration Test
To validate live fetching and hybrid score evaluation against specific targets (e.g., Cognifyz, LinkedIn, Google):
```bash
# Ensure Flask server is running in another terminal
python test_cognifyz.py
```

### Linting & Formatting
Ensure strict adherence to Python styling standards:
```bash
python -m ruff check .
```

---

## 📂 Project Directory Structure

```text
fake_job_detector/
├── backend/
│   ├── app.py                # Main Flask application and API routes
│   ├── model.pkl            # Copied model artifact for backend runtime
│   └── vectorizer.pkl       # Copied vectorizer artifact for backend runtime
├── data/
│   └── job_posts.csv        # Stratified dataset (63 samples) for model training
├── templates/
│   ├── base.html            # Core layout template with styling and navigation
│   ├── home.html            # Static landing and presentation page
│   ├── login.html           # Secure user authentication forms
│   ├── signup.html          # Registration form
│   └── detector.html        # Interactive user dashboard
├── static/
│   ├── styles.css           # Global stylesheet and responsive designs
│   └── script.js            # Main dashboard event handlers and API requests
├── frontend/                # Legacy static-only front-end layout (for reference)
│   ├── index.html
│   ├── styles.css
│   └── script.js
├── tests/
│   └── test_api_basics.py   # Basic Flask endpoint integration tests
├── .env.example             # Template for local environment configuration
├── IMPROVEMENTS.md          # Technical documentation of improvements from v1.0 -> v2.0
├── model.py                 # ML pipeline, feature engineering, and model exporter
├── requirements.txt         # Required Python libraries
└── test_cognifyz.py         # Diagnostic URL testing suite
```

---

## 🛡️ Production Security Checklist

*   [ ] Set `JOBSHIELD_ENV` to `production`.
*   [ ] Set `JOBSHIELD_DEBUG` to `0`.
*   [ ] Generate and set a cryptographically secure `JOBSHIELD_SECRET`.
*   [ ] Configure `JOBSHIELD_CORS_ORIGINS` to contain only trusted domains.
*   [ ] Serve the app behind a reverse proxy (e.g., Nginx) and use a WSGI server like `Gunicorn` or `Waitress`.
*   [ ] Ensure HTTPS is enabled to secure transmission of passwords and session tokens.
