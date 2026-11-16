# Modulo 3 · Il primo subagente: il formatter (45 min)

**Obiettivi:** progettare un contratto dati tra agenti; scrivere un prompt di sistema efficace per un
modello piccolo; validare l'output; far correggere l'LLM con il proprio errore.

**File:** `app/schemas.py`, `app/agents/formatter.py`

## 3.1 Prima lo schema, poi il prompt (10 min)

Gli agenti non si passano testo libero: si passano **oggetti tipizzati**. Lo schema è il contratto,
ed è la prima cosa da scrivere.

```python
class Turn(BaseModel):
    speaker: str
    text: str            # verbatim: tutto ciò che sta qui viene LETTO
    style: str = ""      # come leggerlo, in inglese

class Script(BaseModel):
    mode: Literal["single", "multi"]
    speakers: list[str] = Field(min_length=1)
    turns: list[Turn] = Field(min_length=1)
    notes: str = ""

    @model_validator(mode="after")
    def consistent(self):
        unknown = {t.speaker for t in self.turns} - set(self.speakers)
        if unknown:
            raise ValueError(f"battute con speaker non dichiarati: {sorted(unknown)}")
        ...
```

Perché `text` e `style` separati? Perché la documentazione di Gemini TTS lo chiede: le indicazioni di
regia scritte nel testo **vengono pronunciate**. Lo schema incorpora un vincolo del sistema a valle.

I validatori incrociati (`consistent`) catturano errori che il JSON "valido" non cattura: un modello
piccolo dichiara `["Marco", "Giulia"]` e poi scrive una battuta di `"Giulia Rossi"`.

## 3.2 Il prompt di sistema (15 min)

Aprite `SYSTEM_PROMPT` in `app/agents/formatter.py`. Struttura:

1. **Ruolo e compito** in una riga.
2. **Formato di uscita** con lo schema scritto per esteso.
3. **Regole numerate**, divise per area (testo, parlanti, stile). I modelli piccoli seguono meglio le liste brevi e concrete.
4. **Esempi dentro le regole** (`"ecc." -> "eccetera"`): un esempio vale dieci aggettivi.
5. **Divieti espliciti** dove il modello sbaglia di solito: "NON riassumere", "senza ```".

Regole per l'orecchio che contano davvero nel TTS italiano: simboli (`%`, `€`), abbreviazioni,
sigle, URL e markdown da eliminare, tabelle da trasformare in frasi.

**Lab:** con `FORMATTER_PROVIDER=local`, formattate questi tre testi e confrontate con il formatter finto:

- un paragrafo di un articolo con `%`, `€` e un URL;
- un dialogo in forma `Nome: battuta`;
- un'intervista scritta con trattini (`— Come sta? — Bene.`), che le regex non capiscono.

Il terzo caso è quello che giustifica l'LLM.

## 3.3 Validare e chiedere la correzione (15 min)

```python
def parse_script(raw: str) -> Script:
    m = _JSON_BLOCK.search(raw)               # tollera testo prima/dopo
    if not m:
        raise ValueError("nessun oggetto JSON trovato nella risposta")
    data = json.loads(m.group(0))
    return Script.model_validate(data)        # ValidationError è un ValueError
```

Se fallisce, **rimandiamo al modello la sua risposta e l'errore**:

```python
messages += [AIMessage(previous_output),
             HumanMessage("La tua risposta non è valida:\n" + error + "\nCorreggila...")]
```

È il pattern *self-correction* (o *reflexion* leggera). Funziona sorprendentemente bene perché i
messaggi di errore di Pydantic sono precisi ("turns.2.text: il testo della battuta è vuoto").

Dove mettiamo il ciclo "riprova al massimo 3 volte"? **Non** in un `for` dentro il formatter: lo
mettiamo nel grafo (modulo 4), così ogni tentativo è visibile, tracciato e testabile.

### Alternativa: structured output nativo

LangChain offre `model.with_structured_output(Script)`, che usa function calling o JSON schema del
provider. È più comodo; noi facciamo a mano per due motivi didattici: vedere cosa succede sotto, e
funzionare uguale su Ollama e DeepSeek. **Esercizio extra:** riscrivete il formatter con
`with_structured_output(Script, method="json_schema")` per Ollama e confrontate la percentuale di
successi su 20 testi.

## 3.4 Un mini "eval" (5 min)

Un prompt non si giudica a occhio su un esempio. Create `tests/eval_formatter.py` (non nei test automatici,
costa tempo GPU) che esegue il formatter reale su 10 testi e conta:

- quante risposte sono valide al primo colpo;
- quante battute contengono ancora `%`, `http`, `*`;
- la lunghezza del testo in uscita rispetto all'entrata (sotto l'80%? il modello ha riassunto!).

Cambiate una regola del prompt e rieseguite: questo è il ciclo di sviluppo con gli LLM.

## Verifica

`uv run pytest tests/test_pipeline.py -k "formatter or parse"` è verde.
