"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _default_database_url() -> str:
    return "postgresql+psycopg://postgres:postgres@localhost:5432/review_discovery"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(default_factory=_default_database_url)
    log_level: str = "INFO"
    log_file: str = str(PROJECT_ROOT / "data" / "app.log")

    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "review-discovery-engine/1.0"

    embedding_model: str = "all-MiniLM-L6-v2"
    sentiment_model: str = "cardiffnlp/twitter-roberta-base-sentiment-latest"
    groq_api_key: str = ""
    groq_api_url: str = "https://api.groq.com/openai/v1/chat/completions"
    groq_model: str = "llama-3.3-70b-versatile"
    groq_requests_per_minute: int = 30
    groq_requests_per_day: int = 1000
    groq_tokens_per_minute: int = 12000
    groq_tokens_per_day: int = 100000

    pulse_review_cap: int = 1000
    pulse_theme_limit: int = 3
    pulse_quote_limit: int = 3
    pulse_action_limit: int = 3
    pulse_max_words: int = 250
    pulse_max_retries: int = 1
    pulse_prompt_version: str = "v1"
    pulse_sampling_seed: int = 42
    pulse_docs_mcp_command: str = ""
    pulse_docs_timeout_seconds: int = 30

    api_host: str = "0.0.0.0"
    api_port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
