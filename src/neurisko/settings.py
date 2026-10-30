"""Runtime settings from environment variables and `.env`."""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "qwen2.5:14b"
    llm_api_key: SecretStr = SecretStr("ollama")
    llm_timeout_s: float = Field(default=120, gt=0)
    max_llm_calls_per_generation: int = Field(default=10, ge=0)
    max_generations: int = Field(default=50, ge=1)

    def public(self) -> dict:
        """Settings safe to record: everything except the API key."""
        return self.model_dump(exclude={"llm_api_key"})
