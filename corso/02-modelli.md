# Modulo 2 · Modelli locali e remoti dietro un'unica interfaccia (40 min)

**Obiettivi:** configurare chiavi in sicurezza; chiamare Qwen in locale e DeepSeek in remoto con lo
stesso codice; ottenere JSON affidabile; costruire un fallback locale → remoto.

**File:** `.env.example`, `app/config.py`, `app/llm.py`

## 2.1 Le chiavi non stanno nel codice (5 min)

```bash
cp .env.example .env     # .env è in .gitignore
```

`app/config.py` usa `pydantic-settings`: legge variabili d'ambiente e `.env`, valida i tipi, e tiene
le chiavi in `SecretStr` (che non si stampa per sbaglio nei log: `print(s.gemini_api_key)` mostra `**********`).

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    gemini_api_key: SecretStr | None = Field(default=None, alias="GEMINI_API_KEY")
    formatter_provider: Literal["local", "remote", "auto", "fake"] = Field("auto", alias="FORMATTER_PROVIDER")
    ...
```

> Perché `Literal`? Se scrivete `FORMATTER_PROVIDER=locale` l'app non parte e vi dice perché. Gli errori di configurazione devono esplodere all'avvio, non alla prima richiesta.

## 2.2 Locale contro remoto: il compromesso (5 min)

| | Qwen 9B su Ollama | DeepSeek API |
|---|---|---|
| Costo per chiamata | 0 (elettricità) | pochi centesimi per milione di token |
| Privacy | il testo non esce di casa | il testo va a un fornitore |
| Qualità | buona su compiti stretti e ben descritti | migliore su compiti ambigui |
| Latenza | dipende dalla GPU (prima chiamata lenta: carica il modello) | rete + coda del fornitore |
| Disponibilità | se il PC è acceso | quasi sempre |

Strategia di questo progetto: **locale per default, remoto come rete di sicurezza**.

## 2.3 Una sola interfaccia (15 min, lab)

LangChain definisce `BaseChatModel`: qualsiasi provider espone `.invoke(messages)`. Scriviamo `app/llm.py`:

```python
def local_model(s):
    from langchain_ollama import ChatOllama
    return ChatOllama(model=s.ollama_model, base_url=s.ollama_base_url,
                      temperature=0.2, format="json", reasoning=False,
                      num_ctx=16_384, keep_alive="10m")
```

Ogni parametro è una decisione:

- `format="json"`: Ollama **vincola la generazione** a JSON sintatticamente valido (*constrained decoding*). Non garantisce lo *schema*, ma elimina un'intera classe di errori.
- `reasoning=False`: i Qwen recenti "pensano" prima di rispondere. Per formattare non serve e raddoppia la latenza.
- `num_ctx`: Ollama di default usa un contesto piccolo. Un testo lungo verrebbe **troncato in silenzio**. Classico bug da produzione.
- `keep_alive`: tiene il modello in VRAM tra le richieste.

```python
def remote_model(s):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=s.deepseek_model, base_url=s.deepseek_base_url,
                      api_key=s.deepseek_api_key, temperature=0.2, timeout=60, max_retries=2,
                      model_kwargs={"response_format": {"type": "json_object"}})
```

DeepSeek parla il protocollo OpenAI: stesso client, `base_url` diverso. Molti provider (e anche
Ollama, su `/v1`) fanno così: è lo "standard de facto".

**Esercizio:** in una shell Python

```python
from app.config import get_settings
from app.llm import local_model
from langchain_core.messages import SystemMessage, HumanMessage
m = local_model(get_settings())
print(m.invoke([SystemMessage("Rispondi in JSON {\"saluto\": str}"), HumanMessage("Saluta in italiano")]).content)
```

Ripetete con `remote_model`. Il codice chiamante è identico.

## 2.4 Il fallback (10 min)

```python
def formatter_model(s):
    if s.formatter_provider == "auto":
        primary = local_model(s)
        return primary.with_fallbacks([remote_model(s)]) if s.deepseek_api_key else primary
```

`with_fallbacks` restituisce un `Runnable` che prova il primo modello e, **se solleva un'eccezione**,
passa al successivo. Provate: `ollama stop qwen3.5:9b` e spegnete il servizio Ollama, poi rifate l'invoke con `formatter_model`.

Nota importante: il fallback scatta su *errori*, non su risposte *sbagliate*. Se Qwen risponde con
JSON valido ma contenuto scadente, il fallback non interviene. Per quello serve la validazione (modulo 3).

## 2.5 Il modello finto (5 min)

`FORMATTER_PROVIDER=fake` usa `formatter.fake_format`: regole fisse, nessun LLM. Serve a tre cose:

1. sviluppare UI e grafo senza GPU né costi;
2. test automatici veloci e deterministici;
3. **termine di paragone**: guardate cosa fa l'LLM che le regex non sanno fare. Se la differenza è poca, forse l'LLM non serve.

## Verifica

- `uv run python -c "from app.config import get_settings; print(get_settings())"` non mostra le chiavi in chiaro.
- Con Ollama spento e `FORMATTER_PROVIDER=auto` + chiave DeepSeek, la formattazione funziona comunque.
