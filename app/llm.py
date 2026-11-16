"""Fabbrica dei modelli: locale (Ollama/Qwen) e remoto (DeepSeek).

Idea chiave: il resto del codice non sa QUALE modello sta usando. Riceve un
oggetto LangChain `BaseChatModel` con l'interfaccia `.invoke(messages)`.
Cambiare provider = cambiare configurazione, non codice.

Il fallback (`.with_fallbacks`) è il primo pattern di "mix locale + remoto":
proviamo il modello gratuito sulla nostra GPU; se è spento o va in errore,
paghiamo qualche centesimo a DeepSeek.
"""

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable

from .config import Settings


def local_model(s: Settings) -> BaseChatModel:
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=s.ollama_model,
        base_url=s.ollama_base_url,
        temperature=0.2,  # formattare non è creatività: bassa temperatura
        format="json",  # Ollama vincola il decoding a JSON valido
        reasoning=False,  # niente "thinking" di Qwen: più veloce, output pulito
        num_ctx=16_384,  # contesto sufficiente per testi lunghi
        keep_alive="10m",  # tiene il modello in VRAM tra una richiesta e l'altra
    )


def remote_model(s: Settings) -> BaseChatModel:
    # DeepSeek espone un'API compatibile OpenAI: basta cambiare base_url.
    from langchain_openai import ChatOpenAI

    if s.deepseek_api_key is None:
        raise RuntimeError("DEEPSEEK_API_KEY non impostata")
    return ChatOpenAI(
        model=s.deepseek_model,
        base_url=s.deepseek_base_url,
        api_key=s.deepseek_api_key,
        temperature=0.2,
        timeout=60,
        max_retries=2,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


def formatter_model(s: Settings) -> Runnable:
    """Restituisce il modello per il formatter secondo FORMATTER_PROVIDER."""
    if s.formatter_provider == "local":
        return local_model(s)
    if s.formatter_provider == "remote":
        return remote_model(s)
    if s.formatter_provider == "auto":
        primary = local_model(s)
        if s.deepseek_api_key is None:
            return primary
        return primary.with_fallbacks([remote_model(s)])
    raise ValueError(f"provider non gestito qui: {s.formatter_provider}")


def describe(s: Settings) -> str:
    """Stringa leggibile per la UI/trace."""
    return {
        "local": f"ollama:{s.ollama_model}",
        "remote": f"deepseek:{s.deepseek_model}",
        "auto": f"ollama:{s.ollama_model} → fallback deepseek:{s.deepseek_model}",
        "fake": "fake (deterministico)",
    }[s.formatter_provider]
