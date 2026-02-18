import pytest
from fastapi.testclient import TestClient


def _get_any_unredeemed_invite_code() -> str:
    # Import lazily so env vars from fixtures are applied before Settings is loaded.
    from sqlmodel import Session, select

    from autosedance.server.db import get_engine
    from autosedance.server.models import InviteCode

    engine = get_engine()
    with Session(engine) as session:
        rec = session.exec(
            select(InviteCode).where(InviteCode.redeemed_at.is_(None), InviteCode.disabled_at.is_(None)).limit(1)
        ).first()
        assert rec is not None, "expected invite seeding to create at least 1 invite code"
        return rec.code


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

    from autosedance.server.app import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def client_auth_rl(tmp_path, monkeypatch):
    out_dir = tmp_path / "out"
    db_path = tmp_path / "autosedance_test.sqlite3"

    monkeypatch.setenv("OUTPUT_DIR", str(out_dir))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DISABLE_WORKER", "1")

    monkeypatch.setenv("AUTH_ENABLED", "1")
    monkeypatch.setenv("AUTH_REQUIRE_FOR_READS", "1")
    monkeypatch.setenv("AUTH_REQUIRE_FOR_WRITES", "1")
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret")
    monkeypatch.setenv("AUTH_RL_REGISTER_PER_EMAIL_PER_HOUR", "1")

    from autosedance.config.settings import get_settings

    get_settings.cache_clear()

    from autosedance.server.db import reset_engine_for_tests

    reset_engine_for_tests()

    from autosedance.server.app import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c


def test_auth_register_flow_and_project_gating(client_auth):
    email = "test@example.com"
    password = "test-password-123"
    invite = _get_any_unredeemed_invite_code()

    # Not logged in: projects are gated
    r = client_auth.get("/api/projects")
    assert r.status_code == 401, r.text

    # Register (sets cookie)
    r = client_auth.post(
        "/api/auth/register",
        json={
            "invite_code": invite,
            "email": email,
            "password": password,
            "country": "US",
            "referral": "x",
            "opinion": "hello",
        },
    )
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["authenticated"] is True
    assert me["user_id"]
    assert me["username"]
    assert me["email"] == email
    assert len(me.get("invites", [])) == 5

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

    # Login succeeds and restores access
    r = client_auth.post("/api/auth/login", json={"username": me["username"], "password": password})
    assert r.status_code == 200, r.text
    me2 = r.json()
    assert me2["authenticated"] is True
    assert me2["username"] == me["username"]

    r = client_auth.get("/api/projects")
    assert r.status_code == 200, r.text
    ids = [p["id"] for p in r.json()]
    assert pid in ids


def test_auth_register_rate_limited(client_auth_rl):
    email = "test@example.com"
    password = "test-password-123"
    invite = _get_any_unredeemed_invite_code()
    r = client_auth_rl.post(
        "/api/auth/register",
        json={
            "invite_code": invite,
            "email": email,
            "password": password,
            "country": "US",
            "referral": "x",
            "opinion": None,
        },
    )
    assert r.status_code == 200, r.text
    r = client_auth_rl.post(
        "/api/auth/register",
        json={
            "invite_code": invite,  # still required by schema; rate limit triggers before invite redemption
            "email": email,
            "password": password,
            "country": "US",
            "referral": "x",
            "opinion": None,
        },
    )
    assert r.status_code == 429, r.text
    assert r.json().get("detail") == "RL_LIMITED"
