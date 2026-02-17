"""视频拼接节点"""

from pathlib import Path

from ..config import get_settings
from ..state.schema import GraphState
from ..utils.video import concatenate_videos


async def assembler_node(state: GraphState) -> dict:
    """
    视频拼接节点

    输入: segments[].video_path
    输出: final_video_path
    """
    settings = get_settings()
    output_dir = Path(settings.output_dir)

    # 收集所有视频路径（按index排序）
    segments = sorted(state["segments"], key=lambda s: s.index)
    video_paths = [s.video_path for s in segments if s.video_path]

    if not video_paths:
        return {"error": "No videos to assemble"}

    # 准备输出路径
    output_path = output_dir / "final" / "output.mp4"

    try:
        # 拼接视频
        final_path = await concatenate_videos(video_paths, output_path)
        return {"final_video_path": str(final_path)}

    except Exception as e:
        return {"error": f"Video assembly failed: {str(e)}"}
