# Bonus · LangGraph Studio (facoltativo)

LangGraph Studio è un'interfaccia per **eseguire** il grafo da sola, senza l'app: si sceglie l'input,
si vede lo stato dopo ogni nodo e si risponde all'interrupt a mano. È utile per provare un nodo
nuovo prima di collegarlo alla pagina web. Serve una chiave LangSmith in `.env`.

Il file `langgraph.json` dice a Studio dove trovare il grafo:

```json
{"dependencies": ["."], "graphs": {"voce_agenti": "./app/studio.py:graph"}, "env": ".env"}
```

```bash
uv run --with "langgraph-cli[inmem]" --with colorama langgraph dev
```

Il comando stampa l'indirizzo di Studio (`https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`).

Da sapere:

- `langgraph dev` avvia solo il grafo e Studio, non la pagina web. Sono due server indipendenti: le
  esecuzioni dell'app su `:8000` non compaiono in Studio (compaiono su LangSmith).
- In `app/studio.py` il grafo è compilato senza checkpointer, perché Studio usa il proprio.
- Come input usate `{"text": "Marco: Ciao Giulia\nGiulia: Ciao!"}`. Quando il grafo si ferma su
  `human_review`, nel box di risposta lasciate `""` e premete **Resume** per approvare il copione, oppure
  scrivete solo ciò che volete cambiare, ad esempio `{"options": {"voices": {"Marco": "Puck"}, "speed": 1.2}}`.
