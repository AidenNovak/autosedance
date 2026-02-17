"""AutoSedance 交互式视频生成工作流

工作流程:
1. 生成完整剧本
2. 生成片段0的剧本和视频prompt
3. [暂停] 用户根据剧本制作/上传视频到 output/input_videos/segment_000.mp4
4. 用户输入 'continue' 继续
5. 系统分析视频，截取最后一帧
6. 生成片段1的剧本
7. [暂停] 用户上传视频
8. ... 循环直到所有片段完成
9. 自动拼接所有视频
"""

import asyncio
import sys
import os
import json
from pathlib import Path
from typing import Optional

sys.path.insert(0, "/Users/lijixiang/autosedance/src")

from autosedance.state.schema import GraphState, SegmentRecord
from autosedance.nodes.scriptwriter import scriptwriter_node
from autosedance.nodes.segmenter import segmenter_node
from autosedance.nodes.analyzer import analyzer_node
from autosedance.nodes.assembler import assembler_node
from autosedance.utils.video import extract_last_frame


class InteractiveWorkflow:
    """交互式视频生成工作流"""

    def __init__(self, video_input_dir: str = "output/input_videos"):
        self.video_input_dir = Path(video_input_dir)
        self.video_input_dir.mkdir(parents=True, exist_ok=True)
        self.state: GraphState = None

    async def initialize(self, prompt: str, duration: int = 60, segment_duration: int = 15):
        """初始化工作流"""
        num_segments = duration // segment_duration

        print("=" * 60)
        print("AutoSedance - 交互式视频生成工作流")
        print("=" * 60)
        print(f"总时长: {duration}秒")
        print(f"片段数: {num_segments}")
        print(f"片段时长: {segment_duration}秒")
        print(f"视频上传目录: {self.video_input_dir}")
        print("=" * 60)

        self.state = {
            "user_prompt": prompt,
            "total_duration_seconds": duration,
            "segment_duration": segment_duration,
            "full_script": None,
            "segments": [],
            "current_segment_index": 0,
            "canon_summaries": "",
            "last_frame_path": None,
            "final_video_path": None,
            "error": None,
            "mode": "interactive",
            "video_input_dir": str(self.video_input_dir),
        }

    async def run_full_workflow(self):
        """运行完整工作流"""
        # Step 1: 生成完整剧本
        print("\n[Step 1] 生成完整剧本...")
        result = await scriptwriter_node(self.state)
        self.state.update(result)
        print(f"✅ 剧本生成完成: {len(self.state['full_script'])} 字")

        # 保存剧本到文件
        script_file = Path("output/full_script.txt")
        script_file.parent.mkdir(parents=True, exist_ok=True)
        script_file.write_text(self.state["full_script"], encoding="utf-8")
        print(f"📄 剧本已保存到: {script_file}")

        # 循环处理每个片段
        num_segments = self.state["total_duration_seconds"] // self.state["segment_duration"]

        for segment_idx in range(num_segments):
            print(f"\n{'='*60}")
            print(f"处理片段 {segment_idx + 1}/{num_segments}")
            print("=" * 60)

            # Step 2: 生成分片剧本
            print(f"\n[Step 2.{segment_idx}] 生成片段{segment_idx}的剧本...")
            result = await segmenter_node(self.state)
            self.state.update(result)
            self.state["current_segment_index"] = segment_idx

            # 获取当前片段
            current_segment = None
            for seg in self.state["segments"]:
                if seg.index == segment_idx:
                    current_segment = seg
                    break

            if current_segment:
                print(f"✅ 片段剧本: {len(current_segment.segment_script)} 字")
                print(f"✅ 视频Prompt: {len(current_segment.video_prompt)} 字")

                # 保存片段信息
                self._save_segment_info(segment_idx, current_segment)

                # Step 3: 等待用户上传视频
                print(f"\n[Step 3.{segment_idx}] 等待视频上传...")
                print("-" * 40)
                print(f"📁 请将视频文件放到: {self.video_input_dir}")
                print(f"   文件名: segment_{segment_idx:03d}.mp4")
                print("-" * 40)
                print(f"📝 视频Prompt参考:")
                print(f"   {current_segment.video_prompt[:200]}...")
                print("-" * 40)

                # 等待视频上传
                video_path = await self._wait_for_video(segment_idx)

                if video_path:
                    # Step 4: 分析视频
                    print(f"\n[Step 4.{segment_idx}] 分析视频内容...")
                    # 更新片段的视频路径
                    for i, seg in enumerate(self.state["segments"]):
                        if seg.index == segment_idx:
                            data = seg.model_dump()
                            data["video_path"] = str(video_path)
                            self.state["segments"][i] = SegmentRecord(**data)
                            break

                    result = await analyzer_node(self.state)
                    self.state.update(result)
                    print(f"✅ 视频分析完成")
                    print(f"   总结长度: {len(self.state['canon_summaries'])} 字")
                else:
                    print(f"❌ 视频未上传，跳过片段{segment_idx}")
                    self.state["current_segment_index"] = segment_idx + 1
                    continue

            # 递增索引
            self.state["current_segment_index"] = segment_idx + 1

        # Step 5: 拼接视频
        print(f"\n[Step 5] 拼接所有视频...")
        video_paths = [
            seg.video_path for seg in sorted(self.state["segments"], key=lambda s: s.index)
            if seg.video_path and Path(seg.video_path).exists()
        ]

        if video_paths:
            result = await assembler_node(self.state)
            self.state.update(result)
            if self.state.get("final_video_path"):
                print(f"✅ 视频拼接完成: {self.state['final_video_path']}")
        else:
            print("⚠️ 没有可拼接的视频")

        print("\n" + "=" * 60)
        print("🎉 工作流完成!")
        print("=" * 60)

        # 生成报告
        self._generate_report()

    def _save_segment_info(self, idx: int, segment: SegmentRecord):
        """保存片段信息到文件"""
        info_dir = Path("output/segments")
        info_dir.mkdir(parents=True, exist_ok=True)

        info_file = info_dir / f"segment_{idx:03d}.txt"
        content = f"""# 片段 {idx}

## 时间范围
{(idx * 15)}s - {min((idx + 1) * 15, self.state['total_duration_seconds'])}s

## 剧本（给人看）
{segment.segment_script}

## 视频Prompt（给视频生成模型）
{segment.video_prompt}

---
生成时间: {__import__('datetime').datetime.now().isoformat()}
"""
        info_file.write_text(content, encoding="utf-8")
        print(f"📄 片段信息已保存: {info_file}")

    async def _wait_for_video(self, idx: int) -> Optional[Path]:
        """等待用户上传视频"""
        expected_names = [
            f"segment_{idx:03d}.mp4",
            f"segment_{idx:03d}.mov",
            f"segment_{idx:03d}.avi",
            f"seg_{idx:03d}.mp4",
            f"{idx:03d}.mp4",
        ]

        while True:
            # 检查是否有视频
            for name in expected_names:
                video_path = self.video_input_dir / name
                if video_path.exists():
                    print(f"✅ 检测到视频: {video_path}")
                    return video_path

            # 等待用户输入
            print(f"\n⏳ 等待视频上传... (输入 'check' 检查, 'skip' 跳过, 'quit' 退出)")
            try:
                user_input = input("> ").strip().lower()

                if user_input == "check":
                    continue
                elif user_input == "skip":
                    return None
                elif user_input == "quit":
                    print("退出工作流")
                    sys.exit(0)
                else:
                    # 可能是直接输入了文件路径
                    if Path(user_input).exists():
                        # 复制到目标位置
                        import shutil
                        target = self.video_input_dir / f"segment_{idx:03d}.mp4"
                        shutil.copy(user_input, target)
                        print(f"✅ 视频已复制到: {target}")
                        return target
            except EOFError:
                # 非交互模式，直接返回None
                return None

    def _generate_report(self):
        """生成最终报告"""
        report_file = Path("output/report.json")
        report = {
            "total_duration": self.state["total_duration_seconds"],
            "segment_duration": self.state["segment_duration"],
            "num_segments": len(self.state["segments"]),
            "segments": [
                {
                    "index": seg.index,
                    "status": seg.status,
                    "video_path": seg.video_path,
                    "has_description": bool(seg.video_description),
                }
                for seg in self.state["segments"]
            ],
            "final_video": self.state.get("final_video_path"),
        }
        report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"📊 报告已生成: {report_file}")


async def main():
    # 配置
    prompt = """# OpenClaw智能体宣传视频 - "牛马AI：人类的数字伙伴"

## 主题
探讨人类与AI的关系，展现AI如何成为人类的得力助手，像忠诚的牛马一样任劳任怨地工作。

## 核心角色
1. **数字驴（牛马AI）**：驴身由蓝色发光电路构成，头部是智能显示屏，能显示各种表情
2. **人类角色（程序员）**：穿着休闲的年轻人，从焦虑忙碌到轻松满足的转变

## 故事线（60秒，4个片段）

### 片段1【相遇】(0-15秒)
- 昏暗办公室，程序员面对堆积如山的任务
- 数字驴从虚空中诞生，发光的电路身躯逐渐成形
- 数字驴屏幕显示微笑，走向程序员

### 片段2【协作】(15-30秒)
- 数字驴飞快敲击虚拟键盘，代码飞速生成
- 程序员惊讶地看着，走到数字驴旁边
- 能量槽开始发光

### 片段3【羁绊】(30-45秒)
- 程序员触摸数字驴，温暖光芒流转
- 数字驴更加卖力工作
- 任务完成，能量槽充满金色光芒

### 片段4【新生】(45-60秒)
- 金色光芒照亮办公室
- 程序员拥抱数字驴
- 城市上空浮现无数数字驴，OpenClaw Logo出现

## 视觉风格
赛博朋克风格，深蓝和青色为主，配以暖金色点缀
"""

    workflow = InteractiveWorkflow()
    await workflow.initialize(prompt, duration=60, segment_duration=15)
    await workflow.run_full_workflow()


if __name__ == "__main__":
    asyncio.run(main())
