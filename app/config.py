"""Configurazione centralizzata.

Tutte le chiavi arrivano da variabili d'ambiente o dal file `.env` (mai committato:
vedi `.gitignore`). pydantic-settings valida i tipi all'avvio, così un errore di
configurazione esplode subito e non a metà di una richiesta.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Google Gemini TTS -------------------------------------------------
    gemini_api_key: SecretStr | None = Field(default=None, alias="GEMINI_API_KEY")
    tts_model: str = Field(default="gemini-3.8-flash-tts", alias="TTS_MODEL")
    # "fake" genera un tono sinusoidale: utile per sviluppare senza spendere crediti.
    tts_backend: Literal["gemini", "fake"] = Field(default="gemini", alias="TTS_BACKEND")

    # --- LLM per il subagente "formatter" ---------------------------------
    # local    -> solo Ollama
    # remote   -> solo DeepSeek
    # auto     -> prova Ollama, se fallisce passa a DeepSeek (fallback)
    # fake     -> formatter finto deterministico (test e sviluppo offline)
    formatter_provider: Literal["local", "remote", "auto", "fake"] = Field(
        default="auto", alias="FORMATTER_PROVIDER"
    )
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    # Controlla il nome esatto con `ollama list` (es. qwen3.5:9b, qwen3:8b ...)
    ollama_model: str = Field(default="qwen3.5:9b", alias="OLLAMA_MODEL")
    deepseek_api_key: SecretStr | None = Field(default=None, alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")

    # --- Varie --------------------------------------------------------------
    output_dir: str = Field(default="output", alias="OUTPUT_DIR")
    max_input_chars: int = Field(default=20_000, alias="MAX_INPUT_CHARS")


@lru_cache
def get_settings() -> Settings:
    return Settings()
