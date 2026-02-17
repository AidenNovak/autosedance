"""状态定义 - 人工视频上传版本"""

from typing import TypedDict, Annotated, Literal, Optional, List

from pydantic import BaseModel


class SegmentRecord(BaseModel):
    """单个片段的完整记录"""

    index: int  # 片段索引 (0, 1, 2, ...)
    segment_script: str  # 15秒片段剧本（给人看）
    video_prompt: str = ""  # 视频生成prompt（给视频模型/人工参考）
    video_path: Optional[str] = None  # 用户上传的视频路径
    video_description: Optional[str] = None  # 视频理解结果
    last_frame_path: Optional[str] = None  # 最后一帧
    status: Literal["pending", "script_ready", "waiting_video", "analyzing", "completed", "failed"] = "pending"


def merge_segments(left: List, right: List) -> List:
    """自定义片段合并逻辑：按index更新"""
    result = {s.index: s for s in left}
    for s in right:
        result[s.index] = s  # 覆盖相同index
    return sorted(result.values(), key=lambda x: x.index)


class GraphState(TypedDict):
    """LangGraph 工作流状态 - 人工视频上传版本"""

    # 输入
    user_prompt: str  # 用户初始需求
    total_duration_seconds: int  # 目标总时长（秒）
    segment_duration: int  # 每片段时长（秒）

    # 剧本
    full_script: Optional[str]  # 完整剧本

    # 片段管理
    segments: Annotated[List[SegmentRecord], merge_segments]  # 所有片段记录
    current_segment_index: int  # 当前处理的片段索引

    # 上下文传递
    canon_summaries: str  # 已生成内容的累积总结
    last_frame_path: Optional[str]  # 最后一帧图像路径

    # 输出
    final_video_path: Optional[str]  # 最终拼接视频路径

    # 控制
    error: Optional[str]  # 错误信息

    # 工作模式
    mode: Literal["auto", "interactive"]  # auto=自动等待, interactive=人工确认
    video_input_dir: str  # 用户上传视频的目录
