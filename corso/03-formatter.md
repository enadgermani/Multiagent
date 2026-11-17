# Modulo 3 · Il subagente formatter (45 min)

**File:** `app/schemas.py`, `app/formatter.py`

## 3.1 Prima lo schema (10 min)

I componenti si passano **oggetti tipizzati**, non testo libero. Lo schema è il contratto tra il
formatter e il resto del sistema:

```python
class Turn(BaseModel):
    speaker: str
    text: str            # trascrizione LETTA parola per parola; può contenere tag <...> e |reazioni|
    style: str = ""      # recitazione di tutto il turno (in inglese): finisce in speech_metadata.style

    @field_validator("text")
    @classmethod
    def known_tags(cls, text):
        unknown = {t for t in re.findall(r"<([^<>]+)>", text) if t.strip().lower() not in VOCAL_TAGS}
        if unknown:
            raise ValueError(f"tag non ammessi: {sorted(unknown)}. Usa solo: {sorted(VOCAL_TAGS)}")
        return text

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
- `known_tags` accetta solo i tag vocali previsti da Gemini (`VOCAL_TAGS`, presi dalla guida). Se il
  modello inventa `<door slam>`, l'errore elenca i tag validi e torna al modello: si corregge da solo.
- `max_length=2` porta nello schema un limite di Gemini: lo scopriamo subito, non al momento della sintesi.
- Il validatore controlla la coerenza tra i campi: un modello piccolo può dichiarare `Marco` e poi
  scrivere una battuta di `Marco Rossi`.

## 3.2 Il prompt di sistema (15 min)

Gemini TTS legge `text` **parola per parola**, e separa due livelli di regia
([prompting guide](https://aistudio.google.com/docs/speech-generation?codelanguage=python)):

| Livello | Dove va | Esempi |
|---|---|---|
| sostenuto, vale per tutto il turno: emozione, ritmo, tono, intonazione | `style` → `speech_metadata.style` | `"speaking slowly"`, `"whispers"`, `"sarcastic"`, `"high pitch, excited"` |
| puntuale, in un punto preciso del testo | dentro `text`, tra `<...>`, in inglese | `<sigh>`, `<breath>`, `<laugh>`, `<short pause>`, `<long pause>` |

Più tre strumenti che stanno nel testo stesso: punteggiatura e puntini per le esitazioni, MAIUSCOLO per
l'enfasi, `|reazione|` per le brevi reazioni di chi ascolta in un dialogo. Se l'emozione cambia a metà,
si divide in due turni con `style` diversi. Il prompt traduce tutto questo in regole per il modello
(versione completa in `app/formatter.py`):

```text
Prepari testi italiani per Gemini TTS, che legge "text" parola per parola.
Restituisci SOLO un oggetto JSON con questo schema: {...}

TESTO: italiano, fedele, scritto per l'orecchio, niente regia nel testo.
PARLANTI: un nome per parlante (massimo 2), altrimenti "Narratore".
COME RECITARE: due livelli
5. "style" = come suona TUTTO il turno, in inglese ...
6. Eventi puntuali DENTRO "text", tra parentesi angolari, sempre in inglese, solo questi: ...
7. Pause naturali con virgole, trattini e puntini di sospensione.
8. Enfasi: MAIUSCOLO sulla parola chiave, con parsimonia.
9. Solo nei dialoghi: brevi reazioni tra barre verticali, es. "Il lancio è giovedì |ah sì?| Siamo pronti?"
Usa tag, maiuscole e reazioni solo dove il testo li giustifica: meglio pochi che troppi.
```

Come è costruito: compito in una riga, formato d'uscita esplicito, regole numerate e brevi, esempi
concreti dentro le regole, divieti espliciti dove i modelli sbagliano di solito ("non riassumere").

Esercizio: formattate un paragrafo con `%`, `€` e un URL, poi un'intervista scritta con i trattini
(`— Come sta? — Bene.`), poi un brano emotivo ("Ero stanchissimo... e poi, all'improvviso, la notizia!").
Controllate dove il modello mette `<sigh>`, maiuscole e cambi di `style`, e ascoltate il risultato.
Togliete la regola 9 e osservate cosa cambia nei dialoghi.

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
