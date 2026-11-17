# Modulo 3 · Il subagente formatter (45 min)

**File:** `app/schemas.py`, `app/formatter.py`

## 3.1 Prima lo schema (10 min)

I componenti si passano **oggetti tipizzati**, non testo libero. Lo schema è il contratto tra il
formatter e il resto del sistema:

```python
class Turn(BaseModel):
    speaker: str
    text: str            # viene LETTO così com'è
    style: str = ""      # come leggerlo (in inglese), non viene letto

class Script(BaseModel):
    speakers: list[str] = Field(min_length=1, max_length=2)  # Gemini: max 2 voci per richiesta
    turns: list[Turn] = Field(min_length=1)

    @model_validator(mode="after")
    def speakers_declared(self):
        unknown = {t.speaker for t in self.turns} - set(self.speakers)
        if unknown:
            raise ValueError(f"battute con speaker non dichiarati: {sorted(unknown)}")
        return self
```

- `text` e `style` sono separati perché Gemini TTS legge ad alta voce tutto ciò che sta nel testo:
  le indicazioni di recitazione vanno altrove.
- `max_length=2` porta nello schema un limite di Gemini: lo scopriamo subito, non al momento della sintesi.
- Il validatore controlla la coerenza tra i campi: un modello piccolo può dichiarare `Marco` e poi
  scrivere una battuta di `Marco Rossi`.

## 3.2 Il prompt di sistema (15 min)

```text
Prepari testi italiani per la sintesi vocale.
Restituisci SOLO un oggetto JSON con questo schema:
{"speakers": ["Nome1"], "turns": [{"speaker": "Nome1", "text": "...", "style": "..."}]}

Regole:
1. "text" resta in italiano e fedele al testo originale: non riassumere, non inventare.
2. Scrivi per l'orecchio: togli markdown, URL ed emoji; sciogli simboli e abbreviazioni
   ("%" -> "per cento", "ecc." -> "eccetera").
3. Se il testo è un dialogo, usa un nome per ogni parlante (massimo 2).
   Altrimenti un solo speaker: "Narratore".
4. "style" è una breve indicazione di recitazione in inglese ...
```

Come è costruito: compito in una riga, formato d'uscita esplicito, regole numerate e brevi, esempi
concreti dentro le regole, divieti espliciti dove i modelli sbagliano di solito ("non riassumere").

Esercizio: formattate un paragrafo con `%`, `€` e un URL, poi un'intervista scritta con i trattini
(`— Come sta? — Bene.`). Cambiate una regola e osservate l'effetto.

## 3.3 Validare e far correggere (20 min)

```python
def parse_script(raw: str) -> Script:
    try:
        return Script.model_validate(json.loads(raw))
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON non valido: {e}") from e
```

Se il risultato non è valido, **rimandiamo al modello la sua risposta insieme all'errore**:

```python
def build_messages(text, previous=None, error=None):
    messages = [SystemMessage(SYSTEM_PROMPT), HumanMessage(text)]
    if error:
        messages += [AIMessage(previous),
                     HumanMessage(f"Risposta non valida: {error}\nCorreggi e rispondi solo con il JSON.")]
    return messages
```

Funziona bene perché gli errori di Pydantic sono precisi (`turns.2.speaker: Field required`).
Il ciclo "riprova al massimo 3 volte" non lo scriviamo qui: lo costruiamo nel grafo, nel modulo 4.

> **Cosa guardare.**
> - *Pagina*: aprite il passo `formatter` e leggete il prompt di sistema esattamente come arriva al
>   modello, poi la risposta grezza. Il passo `validate` dice se lo schema è rispettato e, se no, perché.
> - *LangSmith*: alzate la temperatura a 1.2 e formattate un testo lungo finché una risposta non viene
>   scartata. Nella trace vedrete due chiamate al modello: nella seconda, i messaggi includono la
>   risposta sbagliata e l'errore di Pydantic.
