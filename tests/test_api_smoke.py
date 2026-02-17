from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    out_dir = tmp_path / "out"
    db_path = tmp_path / "autosedance_test.sqlite3"

    monkeypatch.setenv("OUTPUT_DIR", str(out_dir))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DISABLE_WORKER", "1")

    from autosedance.config.settings import get_settings

    get_settings.cache_clear()

    from autosedance.server.db import reset_engine_for_tests

    reset_engine_for_tests()

    from autosedance.server.app import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c


def test_api_happy_path_manual_upload(client, monkeypatch, tmp_path):
    # Patch LLM calls (scriptwriter + segmenter share DoubaoClient.chat)
    from autosedance.clients.doubao import DoubaoClient

    async def fake_chat(self, system_prompt: str, user_message: str) -> str:
        if "输出格式（JSON）" in system_prompt:
            return '{"script":"SEG_SCRIPT","video_prompt":"VIDEO_PROMPT"}'
        return "FULL_SCRIPT"

    async def fake_chat_with_image(self, system_prompt: str, user_message: str, image_path: str) -> str:
        return "ANALYSIS"

    monkeypatch.setattr(DoubaoClient, "chat", fake_chat)
    monkeypatch.setattr(DoubaoClient, "chat_with_image", fake_chat_with_image)

    # Patch ffmpeg frame extraction
    import autosedance.server.routes.segments as seg_routes

    def fake_extract_last_frame(video_path, output_path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fakejpg")
        return output_path

    monkeypatch.setattr(seg_routes, "extract_last_frame", fake_extract_last_frame)

    # Patch video assembly
    import autosedance.server.routes.projects as proj_routes

    async def fake_concatenate_videos(video_paths, output_path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fakemp4")
        return output_path

    monkeypatch.setattr(proj_routes, "concatenate_videos", fake_concatenate_videos)

    # Create project
    r = client.post(
        "/api/projects",
        json={
            "user_prompt": "test prompt",
            "total_duration_seconds": 30,
            "segment_duration": 15,
            "pacing": "normal",
        },
    )
    assert r.status_code == 200, r.text
    project = r.json()
    pid = project["id"]

    # Generate full script
    r = client.post(f"/api/projects/{pid}/full_script/generate", json={"feedback": None})
    assert r.status_code == 200, r.text
    project = r.json()
    assert project["full_script"] == "FULL_SCRIPT"

    # Generate segment 0
    r = client.post(f"/api/projects/{pid}/segments/0/generate", json={"feedback": None})
    assert r.status_code == 200, r.text
    project = r.json()
    seg0 = next(s for s in project["segments"] if s["index"] == 0)
    assert seg0["status"] == "script_ready"

    # Upload video 0
    r = client.post(
        f"/api/projects/{pid}/segments/0/video",
        files={"file": ("segment_000.mp4", b"fakevideo", "video/mp4")},
    )
    assert r.status_code == 200, r.text
    seg = r.json()
    assert seg.get("warnings") == []
    assert seg.get("frame_url")

    # Analyze 0
    r = client.post(f"/api/projects/{pid}/segments/0/analyze")
    assert r.status_code == 200, r.text
    project = r.json()
    seg0 = next(s for s in project["segments"] if s["index"] == 0)
    assert seg0["status"] == "completed"
    assert project["canon_summaries"]

    # Segment 1
    r = client.post(f"/api/projects/{pid}/segments/1/generate", json={"feedback": None})
    assert r.status_code == 200, r.text
    r = client.post(
        f"/api/projects/{pid}/segments/1/video",
        files={"file": ("segment_001.mp4", b"fakevideo2", "video/mp4")},
    )
    assert r.status_code == 200, r.text
    seg = r.json()
    assert seg.get("warnings") == []
    assert seg.get("frame_url")
    r = client.post(f"/api/projects/{pid}/segments/1/analyze")
    assert r.status_code == 200, r.text

    # Assemble
    r = client.post(f"/api/projects/{pid}/assemble")
    assert r.status_code == 200, r.text
    project = r.json()
    assert project["final_video_path"]


def test_jobs_include_ui_message_key(client):
    # Create a project first.
    r = client.post(
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

    # Create a queued job (worker is disabled in the fixture).
    r = client.post(f"/api/projects/{pid}/jobs", json={"type": "full_script", "locale": "en"})
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["status"] == "queued"
    assert job["result"]["ui_message"]["key"] == "jobmsg.queued"
