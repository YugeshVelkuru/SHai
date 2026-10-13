from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SmartAssist AI"
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./smartassist.db"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    dialogflow_project_id: str = ""
    dialogflow_location: str = "global"
    dialogflow_agent_id: str = ""

    analytics_retention_days: int = 90
    rag_top_k: int = 3
    rag_similarity_threshold: float = 0.35


@lru_cache
def get_settings() -> Settings:
    return Settings()
