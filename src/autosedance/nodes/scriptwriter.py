"""剧本生成节点"""

import json

from ..clients.doubao import DoubaoClient
from ..prompts.scriptwriter import SCRIPTWRITER_SYSTEM, SCRIPTWRITER_USER
from ..state.schema import GraphState


async def scriptwriter_node(state: GraphState) -> dict:
    """
    剧本生成节点

    输入: user_prompt, total_duration_seconds, segment_duration
    输出: full_script
    """
    client = DoubaoClient()

    total_duration = state["total_duration_seconds"]
    segment_duration = state.get("segment_duration", 15)
    num_segments = (total_duration + segment_duration - 1) // segment_duration

    script = await client.chat(
        system_prompt=SCRIPTWRITER_SYSTEM.format(
            total_duration=total_duration,
            num_segments=num_segments,
            segment_duration=segment_duration,
            segment_duration_mul2=segment_duration * 2,
        ),
        user_message=SCRIPTWRITER_USER.format(user_prompt=state["user_prompt"]),
    )

    return {"full_script": script}
