import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List


def _probe_payload(*, fmt_dur: float, v_dur: Optional[float], a_dur: Optional[float]) -> Dict[str, Any]:
    streams: list[dict] = []
    if v_dur is not None:
        streams.append({"codec_type": "video", "codec_name": "h264", "duration": str(v_dur)})
    if a_dur is not None:
        streams.append(
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "duration": str(a_dur),
                "sample_rate": "44100",
                "channels": 2,
            }
        )
    return {"format": {"duration": str(fmt_dur)}, "streams": streams}


def test_validate_concat_detects_duration_mismatch(tmp_path, monkeypatch):
    from autosedance.utils import video as v

    out = tmp_path / "out.mp4"
    out.write_bytes(b"x")

    def fake_probe(path: Path) -> dict:
        assert path == out
        # Broken output: video duration inflated.
        return _probe_payload(fmt_dur=86.6, v_dur=86.56, a_dur=60.33)

    monkeypatch.setattr(v, "_probe", fake_probe)

    reason = v._validate_concat(out, expected_total=60.0)
    assert reason is not None
    assert "duration_mismatch" in reason or "av_desync" in reason


def test_validate_concat_passes_when_close(tmp_path, monkeypatch):
    from autosedance.utils import video as v

    out = tmp_path / "out.mp4"
    out.write_bytes(b"x")

    def fake_probe(path: Path) -> dict:
        assert path == out
        return _probe_payload(fmt_dur=60.21, v_dur=60.13, a_dur=60.21)

    monkeypatch.setattr(v, "_probe", fake_probe)

    reason = v._validate_concat(out, expected_total=60.0)
    assert reason is None


def test_concatenate_videos_falls_back_when_copy_produces_bad_timestamps(tmp_path, monkeypatch):
    from autosedance.utils import video as v

    # Create fake inputs (files only need to exist).
    in0 = tmp_path / "seg0.mp4"
    in1 = tmp_path / "seg1.mp4"
    in0.write_bytes(b"0")
    in1.write_bytes(b"1")
    out = tmp_path / "out.mp4"

    # Track which strategy was used.
    used: list[str] = []

    def fake_probe(path: Path) -> dict:
        # Inputs: 15s each.
        if path in (in0, in1):
            return _probe_payload(fmt_dur=15.05, v_dur=15.0, a_dur=15.05)
        # Output: first attempt (copy) is broken; reencode is good.
        if path == out:
            if "reencode" in used:
                return _probe_payload(fmt_dur=30.05, v_dur=30.0, a_dur=30.05)
            return _probe_payload(fmt_dur=43.0, v_dur=43.0, a_dur=30.1)
        raise AssertionError(f"unexpected probe path: {path}")

    def fake_copy_concat(list_file: Path, output_path: Path) -> None:
        used.append("copy")
        output_path.write_bytes(b"copy")

    def fake_ts_concat(video_paths: List[Path], output_path: Path, codec: str, tmpdir: Path) -> None:
        used.append("ts")
        raise RuntimeError("ts disabled in unit test")

    def fake_reencode_concat(
        video_paths: List[Path],
        output_path: Path,
        probes: List[dict],
        *,
        default_sample_rate: int,
        default_channels: int,
    ) -> float:
        used.append("reencode")
        output_path.write_bytes(b"reencode")
        return 30.0

    monkeypatch.setenv("VIDEO_CONCAT_MODE", "auto")
    monkeypatch.setattr(v, "_probe", fake_probe)
    monkeypatch.setattr(v, "_strategy_copy_concat", fake_copy_concat)
    monkeypatch.setattr(v, "_strategy_ts_concat", fake_ts_concat)
    monkeypatch.setattr(v, "_strategy_reencode_concat", fake_reencode_concat)

    final = asyncio.run(v.concatenate_videos([in0, in1], out))
    assert final == out
    assert out.read_bytes() == b"reencode"
    assert "copy" in used
    assert "reencode" in used
