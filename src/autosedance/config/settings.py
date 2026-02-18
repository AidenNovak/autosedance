from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App env
    app_env: Literal["dev", "prod", "test"] = "dev"

    # API 配置 - 火山引擎
    volcengine_api_key: str = ""

    # 模型配置
    llm_model: str = "doubao-seed-2-0-pro-260215"

    # 视频参数
    segment_duration: int = 15

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

    # Auth (invite + password)
    auth_enabled: bool = True
    auth_require_for_reads: bool = True
    auth_require_for_writes: bool = True
    auth_secret_key: str = ""  # required in prod; empty means ephemeral (dev-only)
    auth_session_ttl_days: int = 30
    auth_email_allowlist: str = ""  # comma-separated; empty means allow all

    # Reverse proxy / real IP
    trust_proxy_headers: bool = False
    trusted_proxy_ips: str = ""  # comma-separated

    # Rate limits
    auth_rl_register_per_ip_per_hour: int = 30
    auth_rl_register_per_email_per_hour: int = 6
    auth_rl_login_per_ip_per_hour: int = 240

    # Invite codes (viral onboarding)
    invite_enabled: bool = True
    invite_children_per_redeem: int = 5
    invite_seed_count: int = 50
    invite_code_prefix: str = "AS-"

    # Overload protection (basic backpressure)
    overload_max_inflight_requests: int = 30
    overload_acquire_timeout_seconds: float = 0.1
    overload_retry_after_seconds: int = 10

    # Session cookie
    session_cookie_name: str = "autos_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    session_cookie_domain: str = ""  # optional

@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
