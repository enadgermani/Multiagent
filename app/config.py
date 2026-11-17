"""Configurazione: le chiavi arrivano dal file .env (mai committato)."""

from functools import lru_cache
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# pydantic-settings legge .env solo per i campi di Settings, senza esportarli.
# LangSmith invece legge LANGSMITH_* da os.environ: load_dotenv() li rende visibili.
load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: SecretStr = Field(alias="GEMINI_API_KEY")
    tts_model: str = Field(default="gemini-3.8-flash-tts", alias="TTS_MODEL")

    # local = Qwen su Ollama, remote = DeepSeek, auto = locale con fallback remoto
    formatter_provider: Literal["local", "remote", "auto"] = Field(default="auto", alias="FORMATTER_PROVIDER")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen3.5:9b", alias="OLLAMA_MODEL")
    deepseek_api_key: SecretStr | None = Field(default=None, alias="DEEPSEEK_API_KEY")
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")

    output_dir: str = Field(default="output", alias="OUTPUT_DIR")


@lru_cache
def get_settings() -> Settings:
    return Settings()
