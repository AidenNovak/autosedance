"""LangGraph 工作流定义 - 人工视频上传版本"""

import time
from pathlib import Path
from typing import Literal

from langgraph.graph import END, START, StateGraph

from ..nodes import (
    analyzer_node,
    assembler_node,
    segmenter_node,
    scriptwriter_node,
)
from ..state.schema import GraphState


def should_continue(state: GraphState) -> Literal["continue", "assemble"]:
    """判断是否继续生成下一片段"""
    segment_duration = state.get("segment_duration", 15)
    total_segments = (state["total_duration_seconds"] + segment_duration - 1) // segment_duration
    current_idx = state["current_segment_index"]

    if current_idx + 1 >= total_segments:
        return "assemble"
    return "continue"


def increment_index(state: GraphState) -> dict:
    """递增片段索引"""
    return {"current_segment_index": state["current_segment_index"] + 1}


async def wait_for_video(state: GraphState) -> dict:
    """
    等待用户上传视频

    系统会检查 video_input_dir 目录下是否有对应片段的视频文件
    支持的格式: .mp4, .mov, .avi, .mkv
    """
    idx = state["current_segment_index"]
    video_input_dir = Path(state.get("video_input_dir", "output/input_videos"))
    video_input_dir.mkdir(parents=True, exist_ok=True)

    # 期望的视频文件名模式
    expected_names = [
        f"segment_{idx:03d}.mp4",
        f"segment_{idx:03d}.mov",
        f"segment_{idx:03d}.avi",
        f"segment_{idx:03d}.mkv",
        f"seg_{idx:03d}.mp4",
        f"seg_{idx:03d}.mov",
        f"{idx:03d}.mp4",
        f"{idx}.mp4",
    ]

    # 检查是否有匹配的视频文件
    for name in expected_names:
        video_path = video_input_dir / name
        if video_path.exists():
            # 更新片段记录
            segments = state["segments"]
            for seg in segments:
                if seg.index == idx:
                    data = seg.model_dump()
                    data["video_path"] = str(video_path)
                    data["status"] = "analyzing"
                    return {"segments": [type(seg)(**data)]}

    # 如果没有找到视频，返回等待状态
    return {"error": f"等待视频上传: 请将片段{idx}的视频放到 {video_input_dir} 目录"}


def check_video_uploaded(state: GraphState) -> Literal["video_ready", "waiting"]:
    """检查视频是否已上传"""
    idx = state["current_segment_index"]
    segments = state["segments"]

    for seg in segments:
        if seg.index == idx:
            if seg.video_path and Path(seg.video_path).exists():
                return "video_ready"
            break

    return "waiting"


def build_workflow() -> StateGraph:
    """构建视频生成工作流 - 人工视频上传版本

    工作流程:
    1. scriptwriter: 生成完整剧本
    2. segmenter: 生成分片剧本和视频prompt
    3. wait_for_video: 等待用户上传视频
    4. analyzer: 理解视频内容，截取最后一帧
    5. 循环回到步骤2，或结束
    6. assembler: 拼接所有视频

    注意: 这个工作流需要在外部循环中调用，每次循环会检查视频是否上传
    """

    builder = StateGraph(GraphState)

    # 添加节点
    builder.add_node("scriptwriter", scriptwriter_node)
    builder.add_node("segmenter", segmenter_node)
    builder.add_node("wait_for_video", wait_for_video)
    builder.add_node("analyzer", analyzer_node)
    builder.add_node("assembler", assembler_node)
    builder.add_node("increment", increment_index)

    # 定义边
    builder.add_edge(START, "scriptwriter")
    builder.add_edge("scriptwriter", "segmenter")
    builder.add_edge("segmenter", "wait_for_video")

    # 条件边：检查视频是否上传
    builder.add_conditional_edges(
        "wait_for_video",
        check_video_uploaded,
        {
            "video_ready": "analyzer",
            "waiting": END,  # 没有视频时暂停
        },
    )

    builder.add_edge("analyzer", "increment")

    # 条件边：判断是否继续
    builder.add_conditional_edges(
        "increment",
        should_continue,
        {
            "continue": "segmenter",
            "assemble": "assembler",
        },
    )

    builder.add_edge("assembler", END)

    return builder.compile()


def build_single_segment_workflow() -> StateGraph:
    """构建单片段工作流

    用于交互式模式，每次只处理一个片段:
    1. segmenter: 生成分片剧本
    2. END (等待用户上传视频)
    3. 用户调用 analyze_segment 继续处理
    """

    builder = StateGraph(GraphState)

    builder.add_node("segmenter", segmenter_node)
    builder.add_node("analyzer", analyzer_node)
    builder.add_node("increment", increment_index)

    # 如果没有剧本，先生成
    builder.add_conditional_edges(
        START,
        lambda state: "segmenter" if state.get("full_script") else "segmenter",
    )

    builder.add_edge("segmenter", END)  # 生成剧本后暂停，等待视频上传
    builder.add_edge("analyzer", "increment")
    builder.add_edge("increment", END)

    return builder.compile()


# 导出编译后的图
workflow = build_workflow()
single_segment_workflow = build_single_segment_workflow()
