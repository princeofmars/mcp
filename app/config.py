from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/gateway.db"
    secret_key: str = "change-this-in-production"
    fernet_key: str | None = None
    seed_demo: bool = True
    demo_admin_key: str = "adm_demo_change_me"
    demo_agent_key: str = "mcp_demo_change_me"
    admin_host: str = "0.0.0.0"
    admin_port: int = 8000
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8001
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
