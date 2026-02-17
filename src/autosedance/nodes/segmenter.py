"""分片剧本生成节点"""

import json
import re

from ..clients.doubao import DoubaoClient
from ..prompts.loader import get_segmenter_prompts
from ..state.schema import GraphState, SegmentRecord
from ..utils.canon import canon_recent


def extract_json(text: str) -> dict:
    """从文本中提取JSON"""
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取JSON代码块
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试提取花括号内容
    brace_match = re.search(r"\{[\s\S]*\}", text)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    # 返回默认结构
    return {
        "script": text,
        "video_prompt": text[:200],
        "continuity": "",
    }


async def segmenter_node(state: GraphState) -> dict:
    """
    分片剧本生成节点

    输入: full_script, current_segment_index, canon_summaries, segment_duration
    输出: segments[i] 更新
    """
    client = DoubaoClient()
    idx = state["current_segment_index"]

    # 计算时间范围（使用动态片段时长）
    seg_duration = state.get("segment_duration", 15)
    start_time = idx * seg_duration
    end_time = min((idx + 1) * seg_duration, state["total_duration_seconds"])

    # 获取已有片段的总结（使用滑动窗口，只保留最近3个）
    canon_recent_text = canon_recent(state.get("canon_summaries", "") or "", keep=3)

    prompts = get_segmenter_prompts(state.get("locale"))
    response = await client.chat(
        system_prompt=prompts.system.format(
            segment_index=idx + 1,
            time_range=f"{start_time}s-{end_time}s",
        ),
        user_message=prompts.user.format(
            full_script=state["full_script"],
            canon_summaries=canon_recent_text,
            current_time=end_time,
            feedback=(state.get("feedback") or "").strip(),
        ),
    )

    # 解析JSON响应
    data = extract_json(response)

    new_segment = SegmentRecord(
        index=idx,
        segment_script=data.get("script", response),
        video_prompt=data.get("video_prompt", response[:200]),
        # Status source of truth is SegmentRecord.status in schema.py
        status="script_ready",
    )

    return {"segments": [new_segment]}
