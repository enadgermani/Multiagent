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
