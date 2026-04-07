# JobShield - Student Job Scam Detector

JobShield is a Flask web application that helps students detect risky internship/job postings using:
- ML text classification (`/predict`)
- URL/domain-assisted scan (`/scan-url`)
- Red-flag behavior quiz (`/quiz`)

It also includes account-based access (signup/login/logout) and a protected scanner page.

## Core Features

- **Authentication flow** with hashed passwords (SQLite + Werkzeug)
- **Protected scanner UI** at `/detector`
- **Three detection modes**: full-text ML, URL scan, red-flag quiz
- **Health endpoint** at `/api/health` for environment checks
- **Professionalized defaults**: request-size limit, production secret enforcement, CSRF on logout, robust frontend API handling

## Quick Start

```bash
py -m pip install -r requirements.txt
py model.py
py backend/app.py
```

Open `http://127.0.0.1:5000`.

## Environment Configuration

Copy `.env.example` values into your shell/session before running:

- `JOBSHIELD_ENV` - `development` or `production`
- `JOBSHIELD_DEBUG` - `1`/`0`
- `JOBSHIELD_SECRET` - required in production
- `JOBSHIELD_CORS_ORIGINS` - comma-separated allowed origins (empty disables CORS)
- `JOBSHIELD_MAX_BODY_BYTES` - max incoming request size

Example on Windows PowerShell:

```powershell
$env:JOBSHIELD_ENV="development"
$env:JOBSHIELD_DEBUG="1"
$env:JOBSHIELD_SECRET="your-long-random-secret"
```

## API Reference (JSON)

- `GET /api/health`
  - Returns service/version/status (`ready` or `missing_model`).
- `POST /predict`
  - Body: `{ "text": "..." }`
  - Returns: `{ "result", "risk_score", "confidence" }`
- `POST /scan-url`
  - Body: `{ "url": "https://..." }`
  - Returns URL scan result with domain signals and note.
- `POST /quiz`
  - Body: `{ "answers": { "question_id": true/false, ... } }`
  - Returns quiz-based risk score and label.

All API errors follow:

```json
{ "error": "message", "details": "optional" }
```

## Project Structure

```text
fake_job_detector/
  backend/app.py
  templates/
  static/
  data/job_posts.csv
  model.py
  tests/
  .env.example
  pyproject.toml
```

## Development Quality Baseline

- Run tests: `py -m pytest`
- Lint/check style: `py -m ruff check .`
- Legacy static-only frontend in `frontend/` is kept for reference; Flask-served `templates/` + `static/` is the primary app path.

## Production Readiness Notes

- Do not run with `debug=True` in production.
- Set a strong `JOBSHIELD_SECRET`.
- Keep CORS restricted to trusted origins.
- Serve behind HTTPS + production WSGI server (for example, gunicorn/waitress).
