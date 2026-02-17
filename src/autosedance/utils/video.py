"""视频处理工具"""

import asyncio
import subprocess
from pathlib import Path
from typing import Union, List


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

    # 创建文件列表
    list_file = output_path.parent / "concat_list.txt"
    with open(list_file, "w") as f:
        for path in video_paths:
            # 使用绝对路径
            abs_path = Path(path).resolve()
            f.write(f"file '{abs_path}'\n")

    def run_ffmpeg():
        # Fast path: stream copy (requires compatible codecs across segments).
        try:
            subprocess.run(
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
                ],
                check=True,
                capture_output=True,
            )
            return
        except Exception:
            # Fallback: re-encode for robustness.
            subprocess.run(
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
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "aac",
                    "-y",
                    str(output_path),
                ],
                check=True,
                capture_output=True,
            )

    # 在线程池中运行ffmpeg
    await asyncio.get_event_loop().run_in_executor(None, run_ffmpeg)

    # 清理临时文件
    list_file.unlink(missing_ok=True)

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
