"""视频处理工具"""

import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Union, List, Optional, Tuple, Dict, Any


def extract_last_frame(
    video_path: Union[str, Path], output_path: Union[str, Path]
) -> Path:
    """
    精确提取视频最后一帧

    Args:
        video_path: 视频文件路径
        output_path: 输出图片路径

    Returns:
        输出图片路径
    """
    video_path = Path(video_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Fast path: seek from EOF (usually faster than probing duration).
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-sseof",
                "-0.5",
                "-i",
                str(video_path),
                "-vframes",
                "1",
                "-y",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )
        return output_path
    except Exception:
        # Fall back to probing duration + timestamp seek for compatibility.
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        duration = float(probe.stdout.strip())

        timestamp = max(0, duration - 0.5)
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-ss",
                str(timestamp),
                "-i",
                str(video_path),
                "-vframes",
                "1",
                "-y",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )

    return output_path


def _truncate_bytes(data: bytes, max_len: int = 4096) -> bytes:
    if len(data) <= max_len:
        return data
    return data[:max_len] + b"...<truncated>"


def _run(cmd: List[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        stdout = _truncate_bytes(e.stdout or b"")
        stderr = _truncate_bytes(e.stderr or b"")
        raise RuntimeError(
            f"Command failed (exit {e.returncode}): {' '.join(cmd)}\n"
            f"stdout: {stdout.decode(errors='replace')}\n"
            f"stderr: {stderr.decode(errors='replace')}"
        ) from e


def _probe(path: Path) -> Dict[str, Any]:
    proc = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-of",
            "json",
            "-show_entries",
            "format=duration:stream=index,codec_type,codec_name,duration,width,height,sample_rate,channels",
            str(path),
        ]
    )
    try:
        return json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except Exception as e:
        raise RuntimeError(f"ffprobe returned invalid JSON for {path}: {e}") from e


def _durations_from_probe(probe: Dict[str, Any]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    fmt_dur: Optional[float] = None
    v_dur: Optional[float] = None
    a_dur: Optional[float] = None

    fmt = probe.get("format") or {}
    try:
        if fmt.get("duration") is not None:
            fmt_dur = float(fmt.get("duration"))
    except Exception:
        fmt_dur = None

    for st in probe.get("streams") or []:
        if st.get("codec_type") == "video" and v_dur is None:
            try:
                if st.get("duration") is not None:
                    v_dur = float(st.get("duration"))
            except Exception:
                v_dur = None
        if st.get("codec_type") == "audio" and a_dur is None:
            try:
                if st.get("duration") is not None:
                    a_dur = float(st.get("duration"))
            except Exception:
                a_dur = None

    return fmt_dur, v_dur, a_dur


def _effective_segment_duration(probe: Dict[str, Any]) -> Optional[float]:
    fmt_dur, v_dur, a_dur = _durations_from_probe(probe)
    # Prefer video duration for "total length" expectations (format duration is often driven by audio).
    for d in (v_dur, fmt_dur, a_dur):
        if d is not None and d > 0:
            return d
    return None


def _validate_concat(
    output_path: Path,
    expected_total: float,
    *,
    tol_abs: float = 1.0,
    tol_ratio: float = 0.03,
    av_desync_tol: float = 0.5,
) -> Optional[str]:
    if not output_path.exists():
        return "missing_output"
    try:
        if output_path.stat().st_size <= 0:
            return "empty_output"
    except Exception:
        return "unstatable_output"

    probe = _probe(output_path)
    fmt_dur, v_dur, a_dur = _durations_from_probe(probe)
    primary = v_dur if (v_dur is not None and v_dur > 0) else fmt_dur
    if primary is None or primary <= 0:
        return "invalid_duration"

    tol = max(tol_abs, expected_total * tol_ratio)
    if abs(primary - expected_total) > tol:
        return f"duration_mismatch out={primary:.3f} expected={expected_total:.3f} tol={tol:.3f}"

    if v_dur is not None and a_dur is not None and v_dur > 0 and a_dur > 0:
        if abs(v_dur - a_dur) > av_desync_tol:
            return f"av_desync v={v_dur:.3f} a={a_dur:.3f} tol={av_desync_tol:.3f}"

    return None


def _escape_ffconcat_path(p: str) -> str:
    # ffconcat supports quoting; escape single quotes inside.
    return p.replace("'", "\\'")


def _write_ffconcat(list_file: Path, video_paths: List[Path]) -> None:
    with open(list_file, "w", encoding="utf-8") as f:
        f.write("ffconcat version 1.0\n")
        for p in video_paths:
            f.write(f"file '{_escape_ffconcat_path(str(p))}'\n")


def _probe_video_codec(probe: Dict[str, Any]) -> Optional[str]:
    for st in probe.get("streams") or []:
        if st.get("codec_type") == "video":
            c = st.get("codec_name")
            return str(c) if c else None
    return None


def _first_audio_params(probe: Dict[str, Any]) -> Tuple[int, int]:
    # sample_rate, channels
    for st in probe.get("streams") or []:
        if st.get("codec_type") == "audio":
            sr = st.get("sample_rate")
            ch = st.get("channels")
            try:
                sr_i = int(sr) if sr is not None else 44100
            except Exception:
                sr_i = 44100
            try:
                ch_i = int(ch) if ch is not None else 2
            except Exception:
                ch_i = 2
            return sr_i, ch_i
    return 44100, 2


def _segment_has_audio(probe: Dict[str, Any]) -> bool:
    for st in probe.get("streams") or []:
        if st.get("codec_type") == "audio":
            return True
    return False


def _strategy_copy_concat(list_file: Path, output_path: Path) -> None:
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            "-y",
            str(output_path),
        ]
    )


def _strategy_ts_concat(video_paths: List[Path], output_path: Path, codec: str, tmpdir: Path) -> None:
    # Only safe for h264/hevc when we can do mp4->annexb->ts and then concat.
    if codec not in ("h264", "hevc"):
        raise RuntimeError(f"ts_concat unsupported codec: {codec}")

    v_bsf = "h264_mp4toannexb" if codec == "h264" else "hevc_mp4toannexb"
    ts_paths: List[Path] = []
    for i, p in enumerate(video_paths):
        ts = tmpdir / f"seg_{i:04d}.ts"
        _run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-i",
                str(p),
                "-c",
                "copy",
                "-bsf:v",
                v_bsf,
                "-f",
                "mpegts",
                "-y",
                str(ts),
            ]
        )
        ts_paths.append(ts)

    concat_url = "concat:" + "|".join(str(p) for p in ts_paths)
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-i",
            concat_url,
            "-c",
            "copy",
            "-bsf:a",
            "aac_adtstoasc",
            "-movflags",
            "+faststart",
            "-y",
            str(output_path),
        ]
    )


def _strategy_reencode_concat(
    video_paths: List[Path],
    output_path: Path,
    probes: List[Dict[str, Any]],
    *,
    default_sample_rate: int,
    default_channels: int,
) -> float:
    # Returns expected_total used for validation (after per-segment trimming).
    has_any_audio = any(_segment_has_audio(p) for p in probes)

    seg_durs: List[float] = []
    for pr in probes:
        fmt_dur, v_dur, a_dur = _durations_from_probe(pr)
        candidates = [d for d in (v_dur, a_dur, fmt_dur) if d is not None and d > 0]
        seg_dur = min(candidates) if candidates else 0.0
        seg_durs.append(seg_dur)

    expected_total = sum(seg_durs)

    parts: List[str] = []
    v_labels: List[str] = []
    a_labels: List[str] = []

    for i, seg_dur in enumerate(seg_durs):
        # Video: reset timestamps and trim to segment duration (avoids drift/mismatch).
        if seg_dur > 0:
            parts.append(f"[{i}:v]trim=duration={seg_dur:.6f},setpts=PTS-STARTPTS[v{i}]")
        else:
            parts.append(f"[{i}:v]setpts=PTS-STARTPTS[v{i}]")
        v_labels.append(f"[v{i}]")

        if has_any_audio:
            if _segment_has_audio(probes[i]):
                if seg_dur > 0:
                    parts.append(f"[{i}:a]atrim=duration={seg_dur:.6f},asetpts=PTS-STARTPTS[a{i}]")
                else:
                    parts.append(f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]")
            else:
                # Fill missing audio with silence for exactly this segment.
                sr = default_sample_rate or 44100
                ch = default_channels or 2
                if ch == 1:
                    layout = "mono"
                elif ch == 2:
                    layout = "stereo"
                else:
                    layout = "stereo"
                # anullsrc is infinite, so trim it.
                if seg_dur <= 0:
                    raise RuntimeError("Cannot synthesize audio: unknown segment duration")
                parts.append(
                    f"anullsrc=channel_layout={layout}:sample_rate={sr},"
                    f"atrim=duration={seg_dur:.6f},asetpts=PTS-STARTPTS[a{i}]"
                )
            a_labels.append(f"[a{i}]")

    if has_any_audio:
        concat = "".join(v_labels + a_labels) + f"concat=n={len(video_paths)}:v=1:a=1[v][a]"
    else:
        concat = "".join(v_labels) + f"concat=n={len(video_paths)}:v=1:a=0[v]"
    filter_complex = ";".join(parts + [concat])

    cmd: List[str] = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin"]
    for p in video_paths:
        cmd += ["-i", str(p)]

    cmd += ["-filter_complex", filter_complex, "-map", "[v]"]
    if has_any_audio:
        cmd += ["-map", "[a]"]

    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
    ]
    if has_any_audio:
        cmd += ["-c:a", "aac", "-b:a", "128k"]

    cmd += ["-movflags", "+faststart", "-y", str(output_path)]

    _run(cmd)

    return expected_total


async def concatenate_videos(
    video_paths: List[Union[str, Path]], output_path: Union[str, Path]
) -> Path:
    """
    高质量视频拼接

    Args:
        video_paths: 视频文件路径列表
        output_path: 输出视频路径

    Returns:
        输出视频路径
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    paths = [Path(p).resolve() for p in video_paths]
    if not paths:
        raise ValueError("video_paths is empty")

    # Probe inputs once upfront to compute expected duration and detect stream layout.
    input_probes = [_probe(p) for p in paths]
    seg_durs = [_effective_segment_duration(pr) for pr in input_probes]
    if any(d is None for d in seg_durs):
        raise RuntimeError("Unable to determine duration for one or more input videos")
    expected_total = float(sum(d for d in seg_durs if d is not None))

    first_codec = _probe_video_codec(input_probes[0]) or ""
    # Default audio params if we need to synthesize missing audio.
    sr, ch = _first_audio_params(input_probes[0])
    for pr in input_probes:
        if _segment_has_audio(pr):
            sr, ch = _first_audio_params(pr)
            break

    mode = (os.getenv("VIDEO_CONCAT_MODE") or "auto").strip().lower()
    if mode not in ("auto", "copy", "ts", "reencode"):
        raise ValueError(f"Invalid VIDEO_CONCAT_MODE={mode!r}; expected auto|copy|ts|reencode")

    errors: List[str] = []

    def attempt_copy(tmpdir: Path) -> Optional[str]:
        output_path.unlink(missing_ok=True)
        list_file = tmpdir / "concat.ffconcat"
        _write_ffconcat(list_file, paths)
        _strategy_copy_concat(list_file, output_path)
        return _validate_concat(output_path, expected_total)

    def attempt_ts(tmpdir: Path) -> Optional[str]:
        output_path.unlink(missing_ok=True)
        _strategy_ts_concat(paths, output_path, first_codec, tmpdir)
        return _validate_concat(output_path, expected_total)

    def attempt_reencode(tmpdir: Path) -> Optional[str]:
        output_path.unlink(missing_ok=True)
        expected = _strategy_reencode_concat(
            paths,
            output_path,
            input_probes,
            default_sample_rate=sr,
            default_channels=ch,
        )
        return _validate_concat(output_path, expected)

    def run_concat() -> None:
        with tempfile.TemporaryDirectory(prefix="autosedance_concat_") as td:
            tmpdir = Path(td)
            if mode in ("auto", "copy"):
                try:
                    reason = attempt_copy(tmpdir)
                    if reason is None:
                        return
                    raise RuntimeError(reason)
                except Exception as e:
                    errors.append(f"copy_concat: {e}")
                    if mode == "copy":
                        raise

            if mode in ("auto", "ts"):
                try:
                    reason = attempt_ts(tmpdir)
                    if reason is None:
                        return
                    raise RuntimeError(reason)
                except Exception as e:
                    errors.append(f"ts_concat: {e}")
                    if mode == "ts":
                        raise

            if mode in ("auto", "reencode"):
                try:
                    reason = attempt_reencode(tmpdir)
                    if reason is None:
                        return
                    raise RuntimeError(reason)
                except Exception as e:
                    errors.append(f"reencode_concat: {e}")
                    raise

            raise RuntimeError("No concat strategy attempted")

    # 在线程池中运行（避免阻塞 event loop）
    try:
        await asyncio.get_running_loop().run_in_executor(None, run_concat)
    except Exception as e:
        details = "\n".join(f"- {msg}" for msg in errors) if errors else "(no details)"
        raise RuntimeError(f"Video assembly failed: {e}\nAttempts:\n{details}") from e

    if not output_path.exists():
        details = "\n".join(f"- {msg}" for msg in errors) if errors else "(no details)"
        raise RuntimeError(f"Video assembly failed without producing output.\nAttempts:\n{details}")

    return output_path


def get_video_info(video_path: Union[str, Path]) -> dict:
    """
    获取视频信息

    Args:
        video_path: 视频文件路径

    Returns:
        包含duration, width, height等信息的字典
    """
    video_path = Path(video_path)

    # 获取时长
    probe_duration = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
    )
    duration = float(probe_duration.stdout.strip())

    # 获取分辨率
    probe_resolution = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=s=x:p=0",
            str(video_path),
        ],
        capture_output=True,
        text=True,
    )
    width, height = map(int, probe_resolution.stdout.strip().split("x"))

    return {
        "duration": duration,
        "width": width,
        "height": height,
    }
