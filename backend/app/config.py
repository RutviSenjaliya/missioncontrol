"""Application configuration loaded from environment variables (.env supported)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database: PostgreSQL is the intended shared/production database.
    database_url: str = "postgresql+psycopg://missioncontrol:missioncontrol@localhost:5432/missioncontrol"

    # MCP server (self-hosted, Streamable HTTP)
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8001
    mcp_server_url: str = "http://127.0.0.1:8001/mcp"

    # Backend API
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # AI provider: "rule" (deterministic, no external calls) or "bedrock"
    ai_provider: str = "rule"
    bedrock_region: str = "us-east-1"
    bedrock_model_id: str = ""

    # Agent execution limits
    agent_max_tool_calls: int = 12
    agent_tool_timeout_seconds: float = 20.0
    agent_mission_timeout_seconds: float = 90.0
    agent_max_retries: int = 1

    # Seed data
    demo_user_name: str = "Demo User"
    demo_user_token: str = "change-me-demo-token"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
