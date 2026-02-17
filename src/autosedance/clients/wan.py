"""阿里云通义万相 Wan2.6 视频生成客户端"""

import asyncio
from pathlib import Path

import httpx

from ..config import get_settings


class WanClient:
    """通义万相 Wan2.6 视频生成客户端"""

    BASE_URL = "https://dashscope.aliyuncs.com/api/v1"

    def __init__(self):
        self.settings = get_settings()
        self.headers = {
            "Authorization": f"Bearer {self.settings.dashscope_api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }

    async def create_video_task(
        self,
        prompt: str,
        duration: int = 15,
        size: str = "1280*720",
        audio: bool = True,
        shot_type: str = "multi",
        prompt_extend: bool = True,
    ) -> str:
        """
        创建视频生成任务，返回 task_id

        Args:
            prompt: 视频描述
            duration: 视频时长（秒），支持5-15秒
            size: 分辨率，如 "1280*720"
            audio: 是否生成音频
            shot_type: 镜头类型 "single" 或 "multi"
            prompt_extend: 是否扩展prompt
        """
        # Wan模型时长支持5-15秒
        duration = min(max(duration, 5), 15)

        payload = {
            "model": "wan2.6-t2v",
            "input": {
                "prompt": prompt,
            },
            "parameters": {
                "size": size,
                "prompt_extend": prompt_extend,
                "duration": duration,
                "audio": audio,
                "shot_type": shot_type,
            },
        }

        async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
            response = await client.post(
                f"{self.BASE_URL}/services/aigc/video-generation/video-synthesis",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["output"]["task_id"]

    async def get_task_status(self, task_id: str) -> dict:
        """获取任务状态"""
        # 查询任务不需要 X-DashScope-Async header
        query_headers = {
            "Authorization": f"Bearer {self.settings.dashscope_api_key}",
        }

        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            response = await client.get(
                f"{self.BASE_URL}/tasks/{task_id}",
                headers=query_headers,
            )
            response.raise_for_status()
            return response.json()

    async def wait_for_video(self, task_id: str, timeout: int = 600) -> str:
        """
        等待视频生成完成，返回视频URL

        Args:
            task_id: 任务ID
            timeout: 超时时间（秒）
        """
        wait_time = 10
        total_waited = 0

        # 查询任务不需要 X-DashScope-Async header
        query_headers = {
            "Authorization": f"Bearer {self.settings.dashscope_api_key}",
        }

        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            while total_waited < timeout:
                response = await client.get(
                    f"{self.BASE_URL}/tasks/{task_id}",
                    headers=query_headers,
                )
                response.raise_for_status()
                data = response.json()

                task_status = data.get("output", {}).get("task_status")

                if task_status == "SUCCEEDED":
                    # 获取视频URL
                    video_url = data.get("output", {}).get("video_url")
                    if video_url:
                        return video_url
                    raise Exception("Video URL not found in response")

                elif task_status == "FAILED":
                    error_msg = data.get("output", {}).get(
                        "message", "Unknown error"
                    )
                    raise Exception(f"Video generation failed: {error_msg}")

                elif task_status in ["PENDING", "RUNNING"]:
                    await asyncio.sleep(wait_time)
                    total_waited += wait_time
                    wait_time = min(wait_time * 1.2, 30)  # 指数退避
                else:
                    await asyncio.sleep(wait_time)
                    total_waited += wait_time

        raise TimeoutError("Video generation timeout")

    async def download_video(self, video_url: str, save_path: Path) -> Path:
        """下载生成的视频"""
        save_path.parent.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(timeout=120.0, verify=False) as client:
            response = await client.get(video_url)
            response.raise_for_status()
            save_path.write_bytes(response.content)

        return save_path

    async def generate_video(
        self,
        prompt: str,
        save_path: Path,
        duration: int = 15,
        timeout: int = 600,
    ) -> Path:
        """
        完整的视频生成流程：创建任务 -> 等待 -> 下载

        Args:
            prompt: 视频描述
            save_path: 保存路径
            duration: 视频时长（秒），支持5-15秒
            timeout: 超时时间（秒）
        """
        task_id = await self.create_video_task(
            prompt=prompt,
            duration=duration,
        )

        video_url = await self.wait_for_video(task_id, timeout=timeout)
        return await self.download_video(video_url, save_path)
