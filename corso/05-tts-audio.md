# Modulo 5 · Subagente settings, Gemini TTS e audio (35 min)

**Obiettivi:** scrivere un "agente" deterministico; costruire richieste Gemini TTS a una e due voci;
gestire i limiti del fornitore (fan-out); applicare velocità e pitch con ffmpeg.

**File:** `app/voices.py`, `app/agents/settings_agent.py`, `app/tts.py`, `app/audio.py`

## 5.1 Conoscere lo strumento: Gemini TTS (8 min)

Dalla [documentazione](https://aistudio.google.com/docs/speech-generation?codelanguage=python), novembre 2026:

- Modelli: `gemini-3.8-flash-tts` e `gemini-3.8-flash-lite-tts` (più economico).
- 30 voci predefinite (Kore, Charon, Puck, Aoede, ...). Sono **timbri**, non lingue: la lingua viene
  rilevata dal testo, e l'italiano è supportato.
- Output: WAV 24 kHz mono 16 bit (in streaming: PCM grezzo).
- Multi-speaker: **massimo 2 parlanti** per richiesta, solo con voci predefinite.
- Controllo espressivo: campo `style` per battuta, tag in linea `<short pause>`, `<laugh>`...
- **Nessun parametro numerico** per velocità o intonazione.

Chiamata minima con l'SDK `google-genai` (API *interactions*):

```python
client = genai.Client(api_key=KEY, http_options={"api_version": "v1beta"})
interaction = client.interactions.create(
    model="gemini-3.8-flash-tts",
    input=[{"type": "user_input", "content": [
        {"type": "text", "text": "Buongiorno a tutti!",
         "annotations": [{"type": "speech_metadata", "style": "warm, cheerful"}]}]}],
    response_format={"type": "audio"},
    generation_config={"speech_config": [{"voice": "Kore"}]},
)
wav = base64.b64decode(interaction.output_audio.data)
```

Per due voci, ogni blocco di testo ha `"speaker"` nelle annotations e lo `speech_config` diventa
`{"speakers": [{"speaker": "Marco", "voice": "Charon"}, {"speaker": "Giulia", "voice": "Aoede"}]}`.

> Le API dei modelli cambiano spesso. Per questo tutto ciò che sa del formato Gemini sta in **due**
> funzioni (`_payload` e `GeminiTTS.synthesize`): se cambia l'API si tocca solo lì.

## 5.2 Il subagente settings (12 min, lab)

Input: `Script` + `VoiceOptions` (scelte dell'utente). Output: `TTSPlan` (serializzabile, lo mostriamo in UI).

Decisioni che prende:

1. **Casting**: rispetta le voci scelte dall'utente; per gli "Automatica" sceglie voci diverse, alternando i registri.
2. **Strategia** in base al numero di parlanti:
   - 1 → `single_call`
   - 2 → `two_speaker_call` (nativo Gemini, il dialogo suona più naturale)
   - 3+ → `per_turn_calls`: una richiesta per battuta, eseguite in parallelo, audio concatenato
3. **Chunking**: oltre 3.500 caratteri, divide in più richieste a fine battuta.
4. **Lingua**: aggiunge sempre allo stile *"Speak Italian with a natural, native accent from Italy."*
5. **Velocità e pitch**: decide cosa va nel prompt e cosa in post-produzione.

Tutte regole: nessun LLM. Ogni regola ha un test (`test_strategy_by_speaker_count`, `test_long_text_is_chunked`, ...).

**Esercizio:** aggiungete la regola "se una battuta supera 3.500 caratteri, spezzala a fine frase".
Prima il test, poi il codice.

## 5.3 Fan-out / fan-in (5 min)

```python
def synthesize_all(client, payloads, max_workers=4):
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(client.synthesize, payloads))   # mantiene l'ordine
```

Le chiamate TTS sono I/O: i thread bastano. `max_workers` limita la pressione sulle quote dell'API.

In LangGraph esiste un modo nativo per fare lo stesso: l'API `Send`, che crea un'istanza di nodo per
ogni elemento e ne raccoglie i risultati con un reducer (*map-reduce*). È il compito per casa del modulo 6.

## 5.4 Velocità e pitch con ffmpeg (10 min)

Due strade per la velocità, entrambe nell'app:

| Metodo | Come | Pro | Contro |
|---|---|---|---|
| Prompt | `style: "slightly slow pace"` | naturale: il modello rallenta *recitando* | impreciso, non ripetibile |
| DSP | `ffmpeg -af atempo=0.85` | preciso al centesimo | oltre ±30% si sentono artefatti |

Il pitch esiste solo in DSP:

```python
ratio = 2 ** (semitoni / 12)
# alta qualità, se ffmpeg è compilato con librubberband:
"rubberband=pitch=" + str(ratio)
# altrimenti: accelera il campionamento (sale il tono E la velocità) e ricompensa la durata
f"asetrate={24000*ratio},aresample=24000,atempo={1/ratio}"
```

Provate da terminale su un WAV generato:

```bash
ffmpeg -i in.wav -af "atempo=1.25" veloce.wav
ffmpeg -i in.wav -af "rubberband=pitch=0.89" grave.wav    # -2 semitoni
ffmpeg -i in.wav -codec:a libmp3lame -b:a 128k out.mp3
```

Nota: `atempo` accetta fattori tra 0,5 e 2 per istanza; `_atempo_chain` li concatena per valori estremi.

## Verifica

Con `TTS_BACKEND=gemini` e una chiave valida, da Python:

```python
from app.config import get_settings
from app.tts import make_tts
from app.agents.settings_agent import plan_tts
from app.schemas import Script, VoiceOptions
s = Script(mode="multi", speakers=["Marco", "Giulia"], turns=[
    {"speaker": "Marco", "text": "Ciao Giulia!", "style": "cheerful"},
    {"speaker": "Giulia", "text": "Ciao Marco, che sorpresa.", "style": "surprised"}])
plan = plan_tts(s, VoiceOptions(), "gemini-3.8-flash-tts")
open("prova.wav", "wb").write(make_tts(get_settings()).synthesize(plan.requests[0]))
```
