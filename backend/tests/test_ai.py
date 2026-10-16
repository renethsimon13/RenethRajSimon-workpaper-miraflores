"""The assistant is grounded: citations outside the retrieved evidence are flagged, and calls are logged."""
from app import ai


def test_fallback_without_key_still_cites(seeded):
    r = seeded.post("/api/ask", headers={"X-Person": "st-02"}, json={"question": "Why did gross receipts change?"}).json()
    assert not r["ai_enabled"] and "line:SchC.1" in r["citations"]


def test_fabricated_citation_is_flagged(seeded, monkeypatch):
    monkeypatch.setattr(ai, "_call_model", lambda s, u: ("Receipts are 151,300 [line:SchC.1]; see also [doc:D99].", "fake:model"))
    r = seeded.post("/api/ask", headers={"X-Person": "st-02"}, json={"question": "gross receipts"}).json()
    assert r["citations"] == ["line:SchC.1"] and r["unverified"] == ["doc:D99"]
    log = [e for e in seeded.get("/api/events", headers={"X-Person": "st-02"}).json() if e["type"] == "ai.answered"]
    assert log and log[-1]["payload"]["model"] == "fake:model"


def test_client_cannot_use_assistant(seeded):
    assert seeded.post("/api/ask", headers={"X-Person": "cu-01"}, json={"question": "x"}).status_code == 403
