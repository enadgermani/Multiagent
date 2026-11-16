# Modulo 2 · Modelli locali e remoti (40 min)

**File:** `.env.example`, `app/config.py`, `app/llm.py`

## 2.1 Le chiavi (5 min)

```bash
cp .env.example .env    # .env è in .gitignore
```

`app/config.py` legge `.env` con `pydantic-settings`. Le chiavi sono `SecretStr`: stampandole si vede
`**********`. Se un valore è sbagliato (es. `FORMATTER_PROVIDER=locale`) l'app non parte e dice perché.

## 2.2 Locale o remoto? (5 min)

| | Qwen 9B su Ollama | DeepSeek API |
|---|---|---|
| Costo | zero | pochi centesimi per milione di token |
| Privacy | il testo resta in casa | il testo va al fornitore |
| Qualità | buona su compiti stretti e ben spiegati | migliore su testi ambigui |
| Disponibilità | solo se il PC è acceso | sempre |

Scelta del progetto: locale per default, remoto se il locale non risponde.

## 2.3 Un'interfaccia unica (20 min)

In LangChain ogni modello ha lo stesso metodo `.invoke(messaggi)`. Scriviamo `app/llm.py`:

```python
def local_model(s, temperature):
    return ChatOllama(
        model=s.ollama_model, base_url=s.ollama_base_url,
        temperature=temperature,
        format="json",     # Ollama genera solo JSON sintatticamente valido
        reasoning=False,   # niente "thinking": più veloce
        num_ctx=16_384,    # il default di Ollama è piccolo e tronca i testi lunghi
    )

def remote_model(s, temperature):
    return ChatOpenAI(
        model=s.deepseek_model, base_url="https://api.deepseek.com", api_key=s.deepseek_api_key,
        temperature=temperature, model_kwargs={"response_format": {"type": "json_object"}},
    )
```

- `format="json"` vincola il modello a produrre JSON valido. Non garantisce però che i *campi* siano giusti: per quello serve la validazione del modulo 3.
- `num_ctx`: con il valore di default un testo lungo verrebbe tagliato senza alcun errore.
- DeepSeek usa lo stesso protocollo di OpenAI: si usa il client OpenAI cambiando solo `base_url`.

Provate in una shell Python:

```python
from app.config import get_settings
from app.llm import local_model
from langchain_core.messages import SystemMessage, HumanMessage
m = local_model(get_settings())
m.invoke([SystemMessage('Rispondi in JSON: {"saluto": "..."}'), HumanMessage("Saluta in italiano")]).content
```

Poi la stessa cosa con `remote_model`: il codice che chiama non cambia.

### La temperatura

La temperatura arriva dall'interfaccia (cursore "Temperatura del formatter", default 0.2) e viaggia
nello stato del grafo fino al nodo formatter, che crea il modello con quel valore:

```python
def formatter_node(state):
    model = formatter_model(s, state.get("temperature", 0.2))
    ...
```

Creare il modello a ogni chiamata costa pochissimo: è solo un oggetto di configurazione, la connessione
vera avviene in `.invoke()`.

Esercizio: formattate lo stesso testo a 0, 0.7 e 1.5. A temperatura alta il modello inizia a
parafrasare, aggiunge parole e a volte rompe il JSON: vedrete scattare il ciclo di correzione
(modulo 4). Per formattare conviene restare tra 0 e 0.3.

## 2.4 Il fallback (10 min)

```python
def formatter_model(s):
    ...
    return local_model(s).with_fallbacks([remote_model(s)])
```

`with_fallbacks` prova il primo modello e, se solleva un errore, passa al secondo. Provate a fermare
Ollama e a rifare l'invoke con `formatter_model`.

Attenzione: il fallback scatta sugli **errori**, non sulle risposte **sbagliate**. Se Qwen risponde
con un JSON valido ma scorretto, il fallback non interviene.
