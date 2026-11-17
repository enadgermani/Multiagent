# Modulo 1 · Chiamare un modello, locale o remoto (20 min)

**Concetto:** un'interfaccia unica per modelli diversi, la temperatura, il fallback locale → remoto, e il tracing.
**Costruiamo:** `app/config.py`, `app/llm.py`.
**Prerequisiti:** modulo 0.

## 1.1 Le chiavi e la configurazione

`pydantic-settings` legge `.env`, valida i tipi e tiene le chiavi in `SecretStr` (stampandole si vede
`**********`). Se un valore è sbagliato, per esempio `FORMATTER_PROVIDER=locale`, l'app non parte e dice perché.

`load_dotenv()` serve per un motivo pratico: LangSmith legge le sue variabili da `os.environ`, mentre
pydantic-settings non le esporta.

`app/config.py`

```python
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
```

## 1.2 Locale o remoto?

| | Qwen 9B su Ollama | DeepSeek API |
|---|---|---|
| Costo | zero | pochi centesimi per milione di token |
| Privacy | il testo resta in casa | il testo va al fornitore |
| Qualità | buona su compiti stretti e ben spiegati | migliore su testi ambigui |
| Disponibilità | solo se il PC è acceso | sempre |

Scelta del progetto: locale per default, remoto se il locale non risponde.

## 1.3 Un'interfaccia unica

In LangChain ogni modello ha lo stesso metodo `.invoke(messaggi)`. Il resto del programma non sa quale
modello c'è dietro.

`app/llm.py`

```python
"""I modelli del formatter: Qwen in locale (Ollama) e DeepSeek in remoto.

Entrambi sono `BaseChatModel` di LangChain: il resto del codice chiama
`.invoke(messaggi)` senza sapere quale modello c'è dietro.
"""

from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from .config import Settings


def local_model(s: Settings, temperature: float):
    return ChatOllama(
        model=s.ollama_model,
        base_url=s.ollama_base_url,
        temperature=temperature,
        format="json",     # Ollama genera solo JSON sintatticamente valido
        reasoning=False,   # niente "thinking": più veloce
        num_ctx=16_384,    # il default di Ollama è piccolo e tronca i testi lunghi
    )


def remote_model(s: Settings, temperature: float):
    # DeepSeek usa il protocollo OpenAI: stesso client, base_url diverso.
    return ChatOpenAI(
        model=s.deepseek_model,
        base_url="https://api.deepseek.com",
        api_key=s.deepseek_api_key,
        temperature=temperature,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


def formatter_model(s: Settings, temperature: float = 0.2):
    # Temperatura bassa (0-0.3): formattare è un compito preciso, non creativo.
    if s.formatter_provider == "local":
        return local_model(s, temperature)
    if s.formatter_provider == "remote":
        return remote_model(s, temperature)
    # auto: se Ollama solleva un errore (spento, timeout...) si passa a DeepSeek
    if s.deepseek_api_key is None:
        return local_model(s, temperature)
    return local_model(s, temperature).with_fallbacks([remote_model(s, temperature)])


def describe(s: Settings) -> str:
    """Nome leggibile dei modelli in uso, per la pagina web."""
    local, remote = f"ollama/{s.ollama_model}", f"deepseek/{s.deepseek_model}"
    if s.formatter_provider == "local" or (s.formatter_provider == "auto" and s.deepseek_api_key is None):
        return local
    if s.formatter_provider == "remote":
        return remote
    return f"{local} (fallback: {remote})"
```

- `format="json"` vincola Qwen a produrre JSON sintatticamente valido (non garantisce i campi giusti: lo vedremo nel modulo 3).
- `num_ctx`: con il valore di default di Ollama un testo lungo verrebbe tagliato senza errori.
- DeepSeek usa il protocollo di OpenAI: stesso client, `base_url` diverso.
- `with_fallbacks` prova Qwen e, **se solleva un errore**, passa a DeepSeek. Non scatta se Qwen risponde male: per quello serve la validazione.
- `describe` dà un nome leggibile ai modelli: lo userà la pagina web.

## 1.4 Tracing con LangSmith, da subito

Se in `.env` mettete `LANGSMITH_TRACING=true` e `LANGSMITH_API_KEY`, ogni chiamata a un modello
LangChain viene registrata su LangSmith senza scrivere altro codice: messaggi, parametri, token, tempi.
Conviene accenderlo ora, così ogni modulo successivo si può osservare. (I testi vengono inviati a LangSmith.)

## Verifica

Salvate questo file come `prove/m01_modelli.py`:

```python
from langchain_core.messages import SystemMessage, HumanMessage
from app.config import get_settings
from app.llm import formatter_model
m = formatter_model(get_settings(), temperature=0.2)
print(m.invoke([SystemMessage('Rispondi in JSON: {"saluto": "..."}'), HumanMessage('Saluta in italiano')]).content)
```

ed eseguitelo dalla cartella del progetto:

```bash
uv run python -m prove.m01_modelli
```

Ripetetelo con temperatura 1.2 un paio di volte: le risposte cambiano. Poi fermate Ollama e rilanciate:
risponde DeepSeek (se avete la chiave).

> **Cosa guardare su LangSmith:** progetto `voce-agenti`, una trace per ogni chiamata. Cliccateci:
> messaggi completi, `temperature`, `format`, token in entrata e in uscita, latenza.
