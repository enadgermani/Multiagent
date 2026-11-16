"""Test dell'API HTTP con backend finti."""

import importlib

from fastapi.testclient import TestClient


def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FORMATTER_PROVIDER", "fake")
    monkeypatch.setenv("TTS_BACKEND", "fake")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    from app import config

    config.get_settings.cache_clear()
    import app.main as main

    importlib.reload(main)
    return TestClient(main.app)


def test_full_flow_and_regenerate(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    assert "Kore" in c.get("/api/config").json()["voices"]

    r = c.post("/api/format", json={"text": "Primo paragrafo.\n\nSecondo paragrafo."})
    assert r.status_code == 200, r.text
    job, script = r.json()["job_id"], r.json()["script"]
    assert script["mode"] == "single"

    body = {"script": script, "options": {"voices": {"Narratore": "Charon"}, "speed": 1.0, "pitch": 0}}
    r = c.post(f"/api/jobs/{job}/synthesize", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["plan"]["voices"]["Narratore"] == "Charon"
    mp3 = c.get(out["mp3"])
    assert mp3.status_code == 200 and mp3.headers["content-type"] == "audio/mpeg"

    # seconda generazione sullo stesso lavoro: fork, nuova voce, niente LLM
    body["options"]["voices"]["Narratore"] = "Aoede"
    r2 = c.post(f"/api/jobs/{job}/synthesize", json=body).json()
    assert r2["job_id"] != job and r2["plan"]["voices"]["Narratore"] == "Aoede"
    assert r2["trace"][0]["agent"] == "fork"


def test_bad_job_id(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    assert c.get("/api/jobs/../../etc/audio.mp3").status_code == 404
    assert c.get("/api/jobs/" + "0" * 32 + "/audio.exe").status_code == 404
