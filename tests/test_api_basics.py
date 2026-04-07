from backend.app import app


def test_health_endpoint_returns_service_status():
    client = app.test_client()
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["service"] == "JobShield API"
    assert payload["status"] in {"ready", "missing_model"}


def test_quiz_requires_answers_object():
    client = app.test_client()
    response = client.post("/quiz", json={"answers": [True]})
    assert response.status_code == 400
    payload = response.get_json()
    assert "error" in payload


def test_quiz_returns_scored_payload():
    client = app.test_client()
    response = client.post(
        "/quiz",
        json={
            "answers": {
                "upfront_fee": True,
                "telegram_whatsapp_only": False,
                "unrealistic_pay": True,
                "bank_details_early": False,
                "no_company_identity": False,
                "urgent_pressure": False,
            }
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["mode"] == "quiz"
    assert 0 <= payload["risk_score"] <= 100
