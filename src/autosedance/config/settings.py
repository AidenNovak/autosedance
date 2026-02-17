from typing import Literal
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App env
    app_env: Literal["dev", "prod", "test"] = "dev"

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
    cors_origins: str = ""  # comma-separated; when empty, credentials are disabled
    disable_worker: bool = False

    # Upload limits
    max_upload_mb: int = 300
    upload_validate_ffprobe: bool = True

    # Auth (email OTP)
    auth_enabled: bool = True
    auth_require_for_reads: bool = True
    auth_require_for_writes: bool = True
    auth_secret_key: str = ""  # required in prod; empty means ephemeral (dev-only)
    auth_otp_ttl_minutes: int = 10
    auth_otp_min_interval_seconds: int = 60
    auth_otp_max_verify_attempts: int = 8
    auth_session_ttl_days: int = 30
    auth_email_allowlist: str = ""  # comma-separated; empty means allow all
    auth_dev_print_code: bool = False  # dev-only: log OTP to server logs (no SMTP)

    # Reverse proxy / real IP
    trust_proxy_headers: bool = False
    trusted_proxy_ips: str = ""  # comma-separated

    # Rate limit (OTP)
    auth_rl_request_code_per_ip_per_hour: int = 30
    auth_rl_request_code_per_email_per_hour: int = 6
    auth_rl_verify_per_ip_per_hour: int = 120

    # Session cookie
    session_cookie_name: str = "autos_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    session_cookie_domain: str = ""  # optional

    # SMTP (QQ mail supported)
    smtp_host: str = "smtp.qq.com"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""  # QQ 邮箱需要填写“授权码”，不是登录密码
    smtp_from: str = "2453204059@qq.com"
    smtp_from_name: str = "AutoSedance"
    smtp_use_ssl: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
