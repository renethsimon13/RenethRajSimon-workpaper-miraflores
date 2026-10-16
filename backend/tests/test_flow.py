"""Filing lifecycle and adjustment propagation, end to end."""
from conftest import post


def state(c, who="st-02"):
    return c.get("/api/state", headers={"X-Person": who}).json()


def test_adjustments_propagate_and_flag_recompute(seeded):
    lines = {l["key"]: l for l in seeded.get("/api/lines", headers={"X-Person": "st-01"}).json()}
    assert lines["SchC.1"]["adjusted"] == 151300
    assert lines["SchC.31"]["adjusted"] == 73568          # sums recompute exactly
    assert lines["F1040.24"]["stale"]                      # tax rules are flagged, not guessed
    books = seeded.get("/api/schedules/books-to-tax", headers={"X-Person": "st-01"}).json()
    assert books["foots"] and books["workpaper_schc_31"] == 73568


def test_filing_lifecycle(seeded):
    assert post(seeded, "st-03", "filing.approval_requested", {}).status_code == 409       # gates not met
    assert post(seeded, "st-03", "filing.approval_requested", {"override": "demo"}).status_code == 200
    assert post(seeded, "cu-01", "filing.client_approved", {}).status_code == 200
    assert post(seeded, "st-03", "filing.efile_submitted", {}).status_code == 409          # blocking review notes
    for n in state(seeded)["notes"]:
        if n.get("blocking") and n["status"] == "open":
            post(seeded, "st-02", "note.resolved", {"id": n["id"], "text": "resolved"})
    assert post(seeded, "st-03", "filing.efile_submitted", {}).status_code == 200
    assert post(seeded, "st-01", "verification.added", {"target": "line:SchC.1", "vtype": "recalculated", "note": "x"}).status_code == 409  # frozen
    assert post(seeded, "st-03", "filing.efile_rejected", {"jurisdiction": "federal"}).status_code == 200
    assert post(seeded, "st-01", "fact.corrected", {"path": "household:theo.ssn", "from": "666-74-3309", "to": "666-74-3390", "evidence": ["D71"]}).status_code == 200
    assert post(seeded, "st-03", "filing.efile_submitted", {}).status_code == 200          # amounts unchanged: 8879 still valid
    assert post(seeded, "st-03", "filing.efile_accepted", {}).status_code == 200
    assert post(seeded, "st-01", "adjustment.proposed", {"line": "SchC.1", "delta": 1, "reason": "x"}).status_code == 409
    assert post(seeded, "st-03", "filing.amendment_started", {"reason": "notice"}).status_code == 200
    assert post(seeded, "st-01", "adjustment.proposed", {"line": "SchC.1", "delta": 1, "reason": "x", "category": "schc_profit", "description": "t"}).status_code == 200


def test_client_approval_tied_to_return(seeded):
    post(seeded, "st-03", "filing.approval_requested", {"override": "demo"})
    post(seeded, "cu-01", "filing.client_approved", {})
    post(seeded, "st-01", "adjustment.proposed", {"line": "SchC.8", "delta": -100, "category": "schc_expense", "description": "t", "reason": "after approval"})
    post(seeded, "st-02", "adjustment.approved", {"id": state(seeded)["adjustments"][-1]["id"]})
    for n in state(seeded)["notes"]:
        if n.get("blocking") and n["status"] == "open":
            post(seeded, "st-02", "note.resolved", {"id": n["id"], "text": "ok"})
    r = post(seeded, "st-03", "filing.efile_submitted", {})
    assert r.status_code == 409 and "re-approval" in r.json()["detail"]


def test_exports(seeded):
    h = {"X-Person": "st-03"}
    notice = seeded.get("/api/export/notice/N-2025-L566", headers=h).text
    assert "151,300" in notice and "D66" in notice and "666-" not in notice
    roll = seeded.get("/api/export/rollforward", headers=h).json()
    assert roll["for_tax_year"] == 2026 and roll["carryovers"]
