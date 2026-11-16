"""Test senza rete né chiavi: LLM finto, TTS finto. Si eseguono con `pytest`."""

import json

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.types import Command

from app.agents import formatter, settings_agent
from app.audio import build_filter
from app.config import Settings
from app.graph import build_graph
from app.schemas import Script, VoiceOptions
from app.tts import FakeTTS

DIALOG = "Marco: Ciao Giulia, come va?\nGiulia: Bene! Il 50% del lavoro è fatto.\nMarco: Ottimo."
GOOD = json.dumps({"mode": "single", "speakers": ["Narratore"],
                   "turns": [{"speaker": "Narratore", "text": "Ciao a tutti.", "style": "warm"}]})


def make_settings(tmp_path, **kw):
    return Settings(FORMATTER_PROVIDER="fake", TTS_BACKEND="fake", OUTPUT_DIR=str(tmp_path), **kw)


# ---------------------------------------------------------------- formatter
def test_fake_formatter_detects_dialog():
    script = formatter.parse_script(formatter.fake_format(DIALOG))
    assert script.mode == "multi"
    assert script.speakers == ["Marco", "Giulia"]
    assert "50 per cento" in script.turns[1].text


def test_parse_rejects_undeclared_speaker():
    bad = {"mode": "multi", "speakers": ["A"], "turns": [{"speaker": "B", "text": "x"}]}
    with pytest.raises(ValueError, match="non dichiarati"):
        formatter.parse_script(json.dumps(bad))


def test_parse_tolerates_text_around_json():
    assert formatter.parse_script("Ecco:\n" + GOOD + "\nfine").turns[0].text == "Ciao a tutti."


# ---------------------------------------------------------------- settings
def test_casting_respects_user_and_fills_distinct():
    v = settings_agent.cast_voices(["A", "B", "C"], {"A": "Kore", "B": "auto"})
    assert v["A"] == "Kore" and len(set(v.values())) == 3


@pytest.mark.parametrize("n,strategy", [(1, "single_call"), (2, "two_speaker_call"), (3, "per_turn_calls")])
def test_strategy_by_speaker_count(n, strategy):
    names = [f"S{i}" for i in range(n)]
    script = Script(mode="single" if n == 1 else "multi", speakers=names,
                    turns=[{"speaker": s, "text": f"battuta {s}"} for s in names])
    plan = settings_agent.plan_tts(script, VoiceOptions(), "m")
    assert plan.strategy == strategy
    if strategy == "two_speaker_call":
        sc = plan.requests[0]["generation_config"]["speech_config"]
        assert len(sc["speakers"]) == 2


def test_italian_direction_always_present():
    script = formatter.parse_script(GOOD)
    plan = settings_agent.plan_tts(script, VoiceOptions(speed=0.7, speed_method="prompt"), "m")
    style = plan.requests[0]["input"][0]["content"][0]["annotations"][0]["style"]
    assert "Italian" in style and "slow" in style
    assert plan.post["speed"] == 1.0  # in modalità prompt niente DSP sulla velocità


def test_long_text_is_chunked():
    turns = [{"speaker": "Narratore", "text": "x" * 1000} for _ in range(8)]
    script = Script(mode="single", speakers=["Narratore"], turns=turns)
    assert len(settings_agent.plan_tts(script, VoiceOptions(), "m").requests) > 1


def test_filter_chain():
    assert build_filter(1.0, 0.0) == ""
    assert "atempo=2.0" in build_filter(3.0, 0.0)
    assert build_filter(1.0, 2.0)  # pitch genera un filtro


# ---------------------------------------------------------------- grafo end-to-end
def test_graph_interrupt_and_resume(tmp_path):
    tts = FakeTTS()
    g = build_graph(make_settings(tmp_path), tts=tts)
    cfg = {"configurable": {"thread_id": "a" * 32}}
    g.invoke({"text": DIALOG, "attempts": 0}, cfg)
    state = g.get_state(cfg)
    assert state.next == ("human_review",)  # fermo in attesa dell'umano

    script = state.values["script"]
    script["turns"][0]["text"] = "Ciao Giulia, tutto bene?"  # l'utente modifica
    g.invoke(Command(resume={"script": script, "options": {"speed": 1.25, "pitch": -2}}), cfg)
    v = g.get_state(cfg).values
    assert v["plan"]["strategy"] == "two_speaker_call"
    assert tts.calls[0]["input"][0]["content"][0]["text"] == "Ciao Giulia, tutto bene?"
    assert (tmp_path / ("a" * 32 + ".mp3")).stat().st_size > 0
    assert [t["agent"] for t in v["trace"]] == [
        "formatter", "validate", "human_review", "settings", "synthesize", "postprocess"]


def test_self_correction_loop(tmp_path):
    # Il primo output dell'LLM è rotto: il grafo deve ritentare con l'errore.
    model = FakeListChatModel(responses=["non è json", GOOD])
    s = make_settings(tmp_path)
    s.formatter_provider = "local"  # forza il ramo LLM, il modello è iniettato
    g = build_graph(s, model=model, tts=FakeTTS())
    cfg = {"configurable": {"thread_id": "b" * 32}}
    g.invoke({"text": "Ciao a tutti.", "attempts": 0}, cfg)
    v = g.get_state(cfg).values
    assert v["attempts"] == 2 and v["error"] is None
    assert [t["ok"] for t in v["trace"] if t["agent"] == "validate"] == [False, True]


def test_gives_up_after_max_attempts(tmp_path):
    model = FakeListChatModel(responses=["rotto"] * 5)
    s = make_settings(tmp_path)
    s.formatter_provider = "local"
    g = build_graph(s, model=model, tts=FakeTTS())
    cfg = {"configurable": {"thread_id": "c" * 32}}
    g.invoke({"text": "x", "attempts": 0}, cfg)
    st = g.get_state(cfg)
    assert st.next == () and st.values["attempts"] == 3
