import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client_auth(tmp_path, monkeypatch):
    out_dir = tmp_path / "out"
    db_path = tmp_path / "autosedance_test.sqlite3"

    monkeypatch.setenv("OUTPUT_DIR", str(out_dir))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DISABLE_WORKER", "1")

    monkeypatch.setenv("AUTH_ENABLED", "1")
    monkeypatch.setenv("AUTH_REQUIRE_FOR_READS", "1")
    monkeypatch.setenv("AUTH_REQUIRE_FOR_WRITES", "1")
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret")

    from autosedance.config.settings import get_settings

    get_settings.cache_clear()

    from autosedance.server.db import reset_engine_for_tests

    reset_engine_for_tests()

    # Patch email sending for OTP
    import autosedance.server.routes.auth as auth_routes

    sent = {}

    def fake_send_otp_email(to_email: str, code: str, *, ttl_minutes: int) -> None:
        sent["to"] = to_email
        sent["code"] = code
        sent["ttl"] = ttl_minutes

    monkeypatch.setattr(auth_routes, "send_otp_email", fake_send_otp_email)

    from autosedance.server.app import create_app

    app = create_app()
    with TestClient(app) as c:
        c._sent = sent  # type: ignore[attr-defined]
        yield c


def test_auth_otp_flow_and_project_gating(client_auth):
    email = "test@example.com"

    # Not logged in: projects are gated
    r = client_auth.get("/api/projects")
    assert r.status_code == 401, r.text

    # Request code
    r = client_auth.post("/api/auth/request_code", json={"email": email})
    assert r.status_code == 200, r.text
    sent = client_auth._sent  # type: ignore[attr-defined]
    assert sent.get("to") == email
    code = sent.get("code")
    assert code and len(code) == 6

    # Verify code (sets cookie)
    r = client_auth.post("/api/auth/verify_code", json={"email": email, "code": code})
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["authenticated"] is True
    assert me["email"] == email

    # Create project now succeeds (and is owned by this email)
    r = client_auth.post(
        "/api/projects",
        json={
            "user_prompt": "test prompt",
            "total_duration_seconds": 30,
            "segment_duration": 15,
            "pacing": "normal",
        },
    )
    assert r.status_code == 200, r.text
    pid = r.json()["id"]

    # List projects includes it
    r = client_auth.get("/api/projects")
    assert r.status_code == 200, r.text
    ids = [p["id"] for p in r.json()]
    assert pid in ids

    # Logout revokes session cookie
    r = client_auth.post("/api/auth/logout")
    assert r.status_code == 200, r.text
    r = client_auth.get("/api/projects")
    assert r.status_code == 401, r.text
