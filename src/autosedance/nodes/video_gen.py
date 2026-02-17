"""视频生成节点"""

from pathlib import Path

from ..clients.seedance import SeedanceClient
from ..clients.wan import WanClient
from ..config import get_settings
from ..state.schema import GraphState, SegmentRecord


async def video_gen_node(state: GraphState) -> dict:
    """
    视频生成节点

    输入: segments[-1].video_prompt, last_frame_path
    输出: segments[-1].video_path

    支持两种视频模型：
    - seedance: 火山引擎Seedance，支持15秒，支持参考图片
    - wan: 阿里云通义万相Wan2.6，支持5-15秒，支持音频生成
    """
    settings = get_settings()
    idx = state["current_segment_index"]

    # 获取当前片段
    segments = state["segments"]
    current_segment = None
    for seg in segments:
        if seg.index == idx:
            current_segment = seg
            break

    if current_segment is None:
        return {"error": f"Segment {idx} not found"}

    # 准备输出路径
    output_dir = Path(settings.output_dir)
    save_path = output_dir / "videos" / f"segment_{idx:03d}.mp4"

    try:
        # 根据配置选择视频生成客户端
        if settings.video_model == "wan":
            client = WanClient()
            # Wan模型支持5-15秒
            video_path = await client.generate_video(
                prompt=current_segment.video_prompt,
                save_path=save_path,
                duration=15,
                timeout=600,
            )
        else:
            # 默认使用 Seedance
            client = SeedanceClient()
            # 获取参考图片（上一帧）- Seedance支持
            reference_image = state.get("last_frame_path")
            if reference_image and Path(reference_image).exists():
                reference_image = reference_image
            else:
                reference_image = None

            video_path = await client.generate_video(
                prompt=current_segment.video_prompt,
                save_path=save_path,
                reference_image=reference_image,
                duration=15,
                timeout=300,
            )

        # 更新片段记录
        data = current_segment.model_dump()
        data["video_path"] = str(video_path)
        updated_segment = SegmentRecord(**data)

        return {"segments": [updated_segment]}

    except Exception as e:
        data = current_segment.model_dump()
        data["status"] = "failed"
        return {
            "error": f"Video generation failed: {str(e)}",
            "segments": [SegmentRecord(**data)],
        }
