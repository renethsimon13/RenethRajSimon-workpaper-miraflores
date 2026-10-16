"""Firm rules are enforced by the server, whoever the browser claims to be."""
from conftest import post


def test_cannot_approve_own_work(seeded):
    st = seeded.get("/api/state", headers={"X-Person": "st-02"}).json()
    r = post(seeded, "st-02", "adjustment.proposed", {"line": "SchC.8", "delta": 10, "category": "schc_expense", "description": "t", "reason": "test"})
    aid = r.json()["written"][0]["payload"]["id"]
    assert post(seeded, "st-02", "adjustment.approved", {"id": aid}).status_code == 403


def test_adjustment_needs_reason(seeded):
    assert post(seeded, "st-01", "adjustment.proposed", {"line": "SchC.8", "delta": 10}).status_code == 422


def test_large_adjustment_needs_partner(seeded):
    r = post(seeded, "st-01", "adjustment.proposed", {"line": "SchC.1", "delta": -10000, "category": "schc_profit", "description": "t", "reason": "test"})
    aid = r.json()["written"][0]["payload"]["id"]
    post(seeded, "st-02", "adjustment.approved", {"id": aid})
    adj = {a["id"]: a for a in seeded.get("/api/state", headers={"X-Person": "st-02"}).json()["adjustments"]}[aid]
    assert adj["requires_partner"] and adj["status"] == "proposed"
    post(seeded, "st-03", "adjustment.approved", {"id": aid})
    adj = {a["id"]: a for a in seeded.get("/api/state", headers={"X-Person": "st-02"}).json()["adjustments"]}[aid]
    assert adj["status"] == "approved"


def test_judgment_needs_authority(seeded):
    assert post(seeded, "st-01", "note.created", {"target": "line:SchC.1", "kind": "judgment", "text": "x"}).status_code == 422


def test_roles(seeded):
    assert post(seeded, "cu-01", "adjustment.proposed", {"line": "SchC.1", "delta": 1, "reason": "x"}).status_code == 403
    assert post(seeded, "st-01", "standards.updated", {"standards": {}}).status_code == 403
    assert post(seeded, "st-01", "signoff.signed", {"area": "business", "level": "reviewer"}).status_code == 403
    assert seeded.get("/api/lines", headers={"X-Person": "cu-01"}).status_code == 403


def test_sensitive_data_masked_and_logged(seeded):
    body = seeded.get("/api/bootstrap", headers={"X-Person": "st-01"}).text
    assert "666-41-2287" not in body and "4483019276" not in body
    assert seeded.post("/api/unmask", headers={"X-Person": "st-04"}, json={"what": "ssn:ngozi"}).status_code == 403
    assert seeded.post("/api/unmask", headers={"X-Person": "st-02"}, json={"what": "ssn:ngozi"}).json()["value"] == "666-41-2287"
    log = seeded.get("/api/state", headers={"X-Person": "st-05"}).json()["view_log"]
    assert {(x["by"], x["granted"]) for x in log} >= {("st-04", False), ("st-02", True)}


def test_signoff_reopens_when_content_changes(seeded):
    post(seeded, "st-02", "signoff.signed", {"area": "rentals_and_sale", "level": "reviewer"})
    so = lambda: [s for s in seeded.get("/api/state", headers={"X-Person": "st-02"}).json()["signoffs"] if s["area"] == "rentals_and_sale" and s["level"] == "reviewer"][-1]
    assert so()["valid"]
    post(seeded, "st-01", "adjustment.proposed", {"line": "SchE.9A", "delta": -50, "category": "ordinary_income", "description": "t", "reason": "test"})
    assert not so()["valid"]


def test_bulk_undo(seeded):
    r = seeded.post("/api/events", headers={"X-Person": "st-01"}, json={"events": [
        {"type": "verification.added", "payload": {"target": "line:SchB.1.4", "vtype": "recalculated", "note": "a"}},
        {"type": "verification.added", "payload": {"target": "line:SchB.1.5", "vtype": "recalculated", "note": "b"}}]})
    batch = r.json()["batch"]
    count = lambda: len([v for v in seeded.get("/api/state", headers={"X-Person": "st-01"}).json()["verifications"] if v["target"] in ("line:SchB.1.4", "line:SchB.1.5")])
    assert count() == 2
    post(seeded, "st-01", "batch.undo", {"batch": batch})
    assert count() == 0
