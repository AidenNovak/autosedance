"""Seedance 视频生成客户端"""

import asyncio
from pathlib import Path
from typing import Optional

import httpx

from ..config import get_settings


class SeedanceClient:
    """Seedance 视频生成客户端"""

    BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

    def __init__(self):
        self.settings = get_settings()
        self.headers = {
            "Authorization": f"Bearer {self.settings.volcengine_api_key}",
            "Content-Type": "application/json",
        }

    async def create_video_task(
        self,
        prompt: str,
        reference_image: Optional[str] = None,
        duration: int = 15,
    ) -> str:
        """创建视频生成任务，返回 task_id"""
        payload = {
            "model": self.settings.video_model,
            "prompt": prompt,
            "duration": duration,
        }
        if reference_image:
            # 读取参考图片并转为base64
            image_path = Path(reference_image)
            if image_path.exists():
                import base64

                with open(image_path, "rb") as f:
                    image_base64 = base64.b64encode(f.read()).decode()
                payload["reference_image"] = f"data:image/jpeg;base64,{image_base64}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/contents/generations/tasks",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["task_id"]

    async def get_task_status(self, task_id: str) -> dict:
        """获取任务状态"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.BASE_URL}/contents/generations/tasks/{task_id}",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def wait_for_video(self, task_id: str, timeout: int = 300) -> str:
        """等待视频生成完成，返回视频URL"""
        wait_time = 5
        total_waited = 0

        while total_waited < timeout:
            data = await self.get_task_status(task_id)
            status = data.get("status")

            if status == "completed":
                return data["output"]["video_url"]
            elif status == "failed":
                raise Exception(
                    f"Video generation failed: {data.get('error', 'Unknown error')}"
                )

            await asyncio.sleep(wait_time)
            total_waited += wait_time
            wait_time = min(wait_time * 1.5, 30)  # 指数退避，上限30秒

        raise TimeoutError("Video generation timeout")

    async def download_video(self, video_url: str, save_path: Path) -> Path:
        """下载生成的视频"""
        save_path.parent.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(video_url)
            response.raise_for_status()
            save_path.write_bytes(response.content)

        return save_path

    async def generate_video(
        self,
        prompt: str,
        save_path: Path,
        reference_image: Optional[str] = None,
        duration: int = 15,
        timeout: int = 300,
    ) -> Path:
        """完整的视频生成流程：创建任务 -> 等待 -> 下载"""
        task_id = await self.create_video_task(
            prompt=prompt,
            reference_image=reference_image,
            duration=duration,
        )

        video_url = await self.wait_for_video(task_id, timeout=timeout)
        return await self.download_video(video_url, save_path)
