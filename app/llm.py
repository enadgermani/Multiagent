"""I modelli del formatter: Qwen in locale (Ollama) e DeepSeek in remoto.

Entrambi sono `BaseChatModel` di LangChain: il resto del codice chiama
`.invoke(messaggi)` senza sapere quale modello c'è dietro.
"""

from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from .config import Settings


def local_model(s: Settings):
    return ChatOllama(
        model=s.ollama_model,
        base_url=s.ollama_base_url,
        temperature=0.2,   # formattare non è creatività
        format="json",     # Ollama genera solo JSON sintatticamente valido
        reasoning=False,   # niente "thinking": più veloce
        num_ctx=16_384,    # il default di Ollama è piccolo e tronca i testi lunghi
    )


def remote_model(s: Settings):
    # DeepSeek usa il protocollo OpenAI: stesso client, base_url diverso.
    return ChatOpenAI(
        model=s.deepseek_model,
        base_url="https://api.deepseek.com",
        api_key=s.deepseek_api_key,
        temperature=0.2,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


def formatter_model(s: Settings):
    if s.formatter_provider == "local":
        return local_model(s)
    if s.formatter_provider == "remote":
        return remote_model(s)
    # auto: se Ollama solleva un errore (spento, timeout...) si passa a DeepSeek
    if s.deepseek_api_key is None:
        return local_model(s)
    return local_model(s).with_fallbacks([remote_model(s)])
