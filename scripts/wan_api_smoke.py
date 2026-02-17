"""测试Wan API"""

import asyncio
import httpx
import json
import os


async def test_wan():
    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        raise SystemExit("Missing DASHSCOPE_API_KEY in environment.")
    base_url = "https://dashscope.aliyuncs.com/api/v1"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }

    # 测试简单prompt
    simple_prompt = "一只可爱的数字驴在办公室里工作"

    payload = {
        "model": "wan2.6-t2v",
        "input": {
            "prompt": simple_prompt,
        },
        "parameters": {
            "size": "1280*720",
            "prompt_extend": True,
            "duration": 15,
            "audio": True,
            "shot_type": "multi",
        },
    }

    print("测试Wan API...")
    print(f"请求: {json.dumps(payload, ensure_ascii=False, indent=2)}")

    async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
        response = await client.post(
            f"{base_url}/services/aigc/video-generation/video-synthesis",
            headers=headers,
            json=payload,
        )
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.text}")


if __name__ == "__main__":
    asyncio.run(test_wan())
