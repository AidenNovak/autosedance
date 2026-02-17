"""豆包 LLM 客户端（火山引擎 OpenAI 兼容格式）"""

import base64
from pathlib import Path

import httpx

from ..config import get_settings


class DoubaoClient:
    """豆包 LLM 客户端"""

    BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

    def __init__(self):
        self.settings = get_settings()
        self.headers = {
            "Authorization": f"Bearer {self.settings.volcengine_api_key}",
            "Content-Type": "application/json",
        }

    async def chat(self, system_prompt: str, user_message: str) -> str:
        """调用豆包模型进行对话"""
        payload = {
            "model": self.settings.llm_model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_message}],
                },
            ],
        }

        async with httpx.AsyncClient(timeout=120.0, verify=False) as client:
            response = await client.post(
                f"{self.BASE_URL}/responses",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return self._parse_response(data)

    def _parse_response(self, data: dict) -> str:
        """解析豆包API响应"""
        output = data.get("output", [])
        for item in output:
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        return content.get("text", "")
        return ""

    async def chat_with_image(
        self, system_prompt: str, user_message: str, image_path: str
    ) -> str:
        """多模态对话（用于视频理解）"""
        image_path = Path(image_path)
        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode()

        # 检测图片类型
        suffix = image_path.suffix.lower()
        mime_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(suffix, "image/jpeg")

        payload = {
            "model": self.settings.llm_model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": user_message},
                        {
                            "type": "input_image",
                            "image_url": f"data:{mime_type};base64,{image_base64}",
                        },
                    ],
                },
            ],
        }

        async with httpx.AsyncClient(timeout=120.0, verify=False) as client:
            response = await client.post(
                f"{self.BASE_URL}/responses",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return self._parse_response(data)

    async def chat_with_video(
        self, system_prompt: str, user_message: str, video_path: str
    ) -> str:
        """视频理解（如果模型支持视频输入）"""
        video_path = Path(video_path)
        with open(video_path, "rb") as f:
            video_base64 = base64.b64encode(f.read()).decode()

        payload = {
            "model": self.settings.llm_model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": user_message},
                        {
                            "type": "input_video",
                            "video_url": f"data:video/mp4;base64,{video_base64}",
                        },
                    ],
                },
            ],
        }

        async with httpx.AsyncClient(timeout=300.0, verify=False) as client:
            response = await client.post(
                f"{self.BASE_URL}/responses",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return self._parse_response(data)
