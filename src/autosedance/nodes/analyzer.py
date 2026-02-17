"""视频理解节点"""

from pathlib import Path

from ..clients.doubao import DoubaoClient
from ..config import get_settings
from ..prompts.analyzer import ANALYZER_SYSTEM, ANALYZER_USER
from ..state.schema import GraphState, SegmentRecord
from ..utils.video import extract_last_frame


async def analyzer_node(state: GraphState) -> dict:
    """
    视频理解节点

    输入: segments[-1].video_path
    输出: video_description, last_frame_path, canon_summaries
    """
    client = DoubaoClient()
    settings = get_settings()
    idx = state["current_segment_index"]

    # 获取当前片段
    segments = state["segments"]
    current_segment = None
    for seg in segments:
        if seg.index == idx:
            current_segment = seg
            break

    if current_segment is None or current_segment.video_path is None:
        return {"error": f"Segment {idx} or video not found"}

    # 准备输出路径
    output_dir = Path(settings.output_dir)
    frame_path = output_dir / "frames" / f"frame_{idx:03d}.jpg"

    # 截取最后一帧
    try:
        last_frame_path = extract_last_frame(current_segment.video_path, frame_path)
    except Exception as e:
        return {"error": f"Failed to extract frame: {str(e)}"}

    # 计算时间范围（使用动态片段时长）
    seg_duration = state.get("segment_duration", 15)
    start_time = idx * seg_duration
    end_time = min((idx + 1) * seg_duration, state["total_duration_seconds"])

    # 视频理解（使用最后一帧）
    try:
        description = await client.chat_with_image(
            system_prompt=ANALYZER_SYSTEM,
            user_message=ANALYZER_USER.format(
                segment_script=current_segment.segment_script,
                time_range=f"{start_time}s-{end_time}s",
            ),
            image_path=str(last_frame_path),
        )
    except Exception as e:
        return {"error": f"Video analysis failed: {str(e)}"}

    # 更新总结（添加分隔符便于滑动窗口处理）
    new_summary = f"片段{idx}({start_time}s-{end_time}s): {description}"
    prior = state.get("canon_summaries") or ""
    updated_canon = f"{prior}\n---\n{new_summary}" if prior else new_summary

    # 更新片段记录
    data = current_segment.model_dump()
    data["video_description"] = description
    data["last_frame_path"] = str(last_frame_path)
    data["status"] = "completed"
    updated_segment = SegmentRecord(**data)

    return {
        "segments": [updated_segment],
        "canon_summaries": updated_canon,
        "last_frame_path": str(last_frame_path),
    }
