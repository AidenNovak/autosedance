from typing import Literal
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API 配置 - 火山引擎
    volcengine_api_key: str = ""

    # API 配置 - 阿里云 DashScope
    dashscope_api_key: str = ""

    # 模型配置
    llm_model: str = "doubao-seed-2-0-pro-260215"
    video_model: Literal["seedance", "wan"] = "wan"  # seedance 或 wan

    # 视频参数
    segment_duration: int = 15
    video_resolution: str = "1080p"
    video_fps: int = 24

    # 路径配置
    output_dir: str = "output"

    # Server/persistence (optional)
    database_url: str = ""  # e.g. sqlite:///output/autosedance.sqlite3
    projects_dir: str = ""  # overrides {output_dir}/projects when set
    cors_origins: str = ""  # comma-separated, empty means allow all

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
