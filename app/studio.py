"""Punto d'ingresso per LangGraph Studio (`langgraph dev`, vedi langgraph.json).

Studio salva da sé lo stato dei lavori, quindi qui il grafo è compilato senza checkpointer.
"""

from app.config import get_settings
from app.graph import build_graph

graph = build_graph(get_settings())
