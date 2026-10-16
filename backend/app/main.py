"""HTTP API. Identity comes from the role switcher (X-Person header); every write is
checked against the firm's rules here, on the server, not in the browser."""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import ai, exports, seed, store, views
from .packet import AREAS, FORM_NAMES, get_packet
from .state import VERIFY_TYPES_DEFAULT, State, short_hash

app = FastAPI(title="Miraflores workpaper")
app.add_middleware(GZipMiddleware, minimum_size=1000)

P = get_packet()


@app.on_event("startup")
def _seed_on_empty():
    # A reviewer opening the link sees a season in progress; Firm → Reset returns to the bare packet.
    if os.environ.get("SEED_ON_EMPTY") == "1" and not store.all_events():
        seed.seed(P, state)

# ---------------------------------------------------------------------- state cache
_state_cache = {"n": -1, "state": None}


def state() -> State:
    evs = store.all_events()
    key = (len(evs), evs[-1]["id"] if evs else 0)
    if _state_cache["n"] != key:
        _state_cache["state"] = State(P, evs)
        _state_cache["n"] = key
    return _state_cache["state"]


# ---------------------------------------------------------------------- identity & masking
def person_of(req: Request) -> str:
    pid = req.headers.get("x-person") or req.query_params.get("as") or "st-01"
    if pid not in P.staff and pid not in P.client_users:
        raise HTTPException(400, "unknown person")
    return pid


def role_of(pid):
    return P.staff[pid]["role"] if pid in P.staff else "client"


def cleared(pid):
    return bool(P.staff.get(pid, {}).get("sensitive_data_clearance"))


def _sensitive_literals():
    hh = P.data["household"]
    lits = {}
    for x in hh["people"]:
        lits[x["ssn"]] = "***-**-" + x["ssn"][-4:]
        if x.get("ip_pin"):
            lits[x["ip_pin"]] = "******"
    b = hh["bank_account_for_refund_or_payment"]
    lits[b["routing"]] = "*****" + b["routing"][-4:]
    lits[b["account"]] = "******" + b["account"][-4:]
    for e in P.data["extracted_values"]:
        if e["value_type"] == "account_number" and isinstance(e["value"], str):
            lits[e["value"]] = "**** " + e["value"][-4:]
    lits["41207"] = "*****"  # signature PINs in the timeline
    lits["88310"] = "*****"
    lits["666-74-3309"] = "***-**-3309"
    lits["666-74-3390"] = "***-**-3390"
    return lits


SENSITIVE = _sensitive_literals()
SSN_RE = re.compile(r"\b666-\d{2}-(\d{4})\b")


def mask_text(t: str) -> str:
    for k, v in SENSITIVE.items():
        t = t.replace(k, v)
    return SSN_RE.sub(lambda m: "***-**-" + m.group(1), t)


def out(req: Request, data, status=200):
    """Every response is masked by default. Revealing a value is a separate, logged call."""
    body = json.dumps(data, default=str)
    body = mask_text(body)
    return Response(body, status_code=status, media_type="application/json")


# ---------------------------------------------------------------------- permissions
STAFF_WRITE = {"preparer", "reviewer", "partner"}
NOTE_KINDS = {"review_note": {"reviewer", "partner", "quality_reviewer"},
              "preparer_note": STAFF_WRITE, "judgment": STAFF_WRITE, "election": STAFF_WRITE,
              "due_diligence": STAFF_WRITE, "penalty_decision": {"reviewer", "partner"},
              "variance_explanation": STAFF_WRITE, "comment": STAFF_WRITE | {"quality_reviewer", "firm_administrator", "client"},
              "post_filing": {"quality_reviewer", "partner", "reviewer", "preparer"}}
RETURN_MUTATIONS = {"adjustment.proposed", "adjustment.approved", "adjustment.reversed", "verification.added",
                    "verification.removed", "finding.accepted", "finding.dismissed", "finding.reopened", "signoff.signed"}


def authorize(s: State, pid: str, t: str, pl: dict):
    role = role_of(pid)
    frozen = s.filing["frozen_at"] and s.filing["status"] in ("submitted", "filed")
    if frozen and t in RETURN_MUTATIONS:
        raise HTTPException(409, "The return is frozen at filing. Start an amendment to change it.")
    if t == "adjustment.proposed":
        if role not in STAFF_WRITE:
            raise HTTPException(403, f"{role} cannot propose adjustments")
        if not pl.get("reason"):
            raise HTTPException(422, "An adjustment needs a reason (who, why, tax effect are recorded)")
    elif t == "adjustment.approved":
        adj = s.adjustments.get(pl["id"])
        if not adj:
            raise HTTPException(404, "no such adjustment")
        if role not in ("reviewer", "partner"):
            raise HTTPException(403, "Only a reviewer or partner can approve")
        if adj["proposed_by"] == pid:
            raise HTTPException(403, "A person may not review or sign off on work they prepared.")
        if adj["requires_partner"] and role != "partner":
            pass  # reviewer approval recorded; status stays proposed until a partner approves
        pl["role"] = role
    elif t == "adjustment.reversed":
        adj = s.adjustments.get(pl["id"])
        if not adj:
            raise HTTPException(404, "no such adjustment")
        if role not in STAFF_WRITE:
            raise HTTPException(403, "not allowed")
        if adj["status"] == "approved" and role == "preparer":
            raise HTTPException(403, "An approved adjustment can only be reversed by a reviewer or partner")
    elif t in ("verification.added", "verification.removed"):
        if role not in STAFF_WRITE:
            raise HTTPException(403, f"{role} cannot record verifications")
        if t == "verification.added" and pl.get("vtype") not in s.standards.get("verification_types", VERIFY_TYPES_DEFAULT):
            raise HTTPException(422, "Unknown verification type (see firm standards)")
    elif t == "note.created":
        kind = pl.get("kind", "comment")
        if role not in NOTE_KINDS.get(kind, set()):
            raise HTTPException(403, f"{role} cannot create a {kind}")
        if kind in ("judgment", "election", "penalty_decision") and not pl.get("authority"):
            raise HTTPException(422, "Every judgment call records the authority relied on.")
        if frozen and kind not in ("post_filing", "comment"):
            raise HTTPException(409, "Return is frozen; only post-filing notes are allowed")
    elif t in ("note.resolved", "note.reopened"):
        n = s.notes.get(pl["id"])
        if not n:
            raise HTTPException(404, "no such note")
        if n.get("kind") == "review_note" and role not in ("reviewer", "partner") and n["by"] != pid:
            raise HTTPException(403, "Only the note's author, a reviewer or a partner can clear a review note")
        if role == "client":
            raise HTTPException(403, "not allowed")
    elif t == "note.replied":
        if pl["id"] not in s.notes:
            raise HTTPException(404, "no such note")
    elif t == "question.asked":
        if role not in STAFF_WRITE:
            raise HTTPException(403, "Only the engagement team asks questions")
    elif t == "question.answered":
        q = s.questions.get(pl["id"])
        if not q:
            raise HTTPException(404, "no such question")
        if not (q["to"] == pid or (q["to"] == "client" and role == "client")):
            raise HTTPException(403, "Only the person asked can answer")
    elif t == "question.closed":
        if role not in STAFF_WRITE:
            raise HTTPException(403, "not allowed")
    elif t == "signoff.signed":
        level, area = pl["level"], pl["area"]
        if level != role:
            raise HTTPException(403, f"A {role} cannot sign off at {level} level")
        if level in ("reviewer", "partner") and area != "return" and s.prepared_by(pid, area):
            raise HTTPException(403, "A person may not review or sign off on work they prepared.")
        if level == "partner" and area == "return":
            blocking = [n for n in s.notes.values() if n.get("blocking") and n["status"] == "open"]
            if blocking:
                raise HTTPException(409, f"{len(blocking)} open review notes block the partner sign-off")
        pl["hash"] = s.return_hash() if area == "return" else s.area_hash(area)
    elif t in ("finding.accepted", "finding.dismissed", "finding.reopened"):
        if role not in STAFF_WRITE:
            raise HTTPException(403, "not allowed")
        if t == "finding.dismissed" and not pl.get("reason"):
            raise HTTPException(422, "Dismissing a finding needs a reason")
    elif t == "time.logged":
        if pid not in P.staff:
            raise HTTPException(403, "staff only")
    elif t in ("standards.updated",):
        if role != "firm_administrator":
            raise HTTPException(403, "Only the firm administrator changes firm standards")
    elif t == "assignment.set":
        if role not in ("firm_administrator", "partner"):
            raise HTTPException(403, "Only the administrator or partner assigns work")
    elif t == "filing.extension_filed":
        if role not in ("reviewer", "partner"):
            raise HTTPException(403, "not allowed")
    elif t == "filing.approval_requested":
        if role != "partner":
            raise HTTPException(403, "The partner sends the return for client approval")
        gates = [g for g in s.required_steps() if not g["done"] and g["step"] not in ("Client approval and e-file authorization",)]
        if gates and not pl.get("override"):
            raise HTTPException(409, "Not ready: " + "; ".join(g["step"] for g in gates))
        pl["hash"] = s.return_hash()
        pl["summary"] = s.summary()["approved"]
    elif t == "filing.client_approved":
        if role != "client":
            raise HTTPException(403, "Only the client approves and signs Form 8879")
        if s.filing["status"] != "awaiting_client":
            raise HTTPException(409, "Nothing awaiting approval")
        pl["hash"] = s.return_hash()
        pl["summary"] = s.summary()["approved"]
    elif t == "filing.efile_submitted":
        if role != "partner":
            raise HTTPException(403, "The signing partner transmits the return")
        appr = s.filing.get("client_approval")
        if not appr or appr.get("hash") != s.return_hash():
            raise HTTPException(409, "Client approval does not match the current return — re-approval needed")
        blocking = [n for n in s.notes.values() if n.get("blocking") and n["status"] == "open"]
        if blocking:
            raise HTTPException(409, "Open review notes block filing")
    elif t in ("filing.efile_rejected", "filing.efile_accepted"):
        if role not in ("partner", "firm_administrator"):
            raise HTTPException(403, "not allowed")
    elif t == "filing.amendment_started":
        if role != "partner":
            raise HTTPException(403, "Only the partner opens an amendment")
    elif t == "fact.corrected":
        if role not in STAFF_WRITE:
            raise HTTPException(403, "not allowed")
        if not pl.get("evidence"):
            raise HTTPException(422, "A corrected fact needs its evidence")
    elif t in ("file.attached", "link.added", "view.seen", "batch.undo", "batch.redo"):
        if t in ("batch.undo", "batch.redo") and role not in STAFF_WRITE:
            raise HTTPException(403, "not allowed")
    else:
        raise HTTPException(400, f"unknown event type {t}")


ENTITY = {"adjustment": "id", "verification": "id", "note": "id", "question": "id", "finding": "id"}


def _entity(t, pl):
    k = t.split(".")[0]
    if pl.get("target"):
        return pl["target"]
    if k == "adjustment" and "line" in pl:
        return f"line:{pl['line']}"
    if pl.get("id"):
        return f"{k}:{pl['id']}"
    return None


# ---------------------------------------------------------------------- routes
@app.get("/api/health")
def health():
    return {"ok": True, "packet_sha256": P.sha256, "events": len(store.all_events())}


@app.get("/api/bootstrap")
def bootstrap(req: Request):
    s = state()
    d = P.data
    return out(req, {
        "packet": {**d["packet"], "sha256": P.sha256, "documents": len(d["documents"]), "values": len(d["extracted_values"]),
                   "versions": [{"version": v["version"], "computed_at": v["computed_at"], "trigger": v["trigger"]} for v in d["return_versions"]],
                   "current_version": P.current_version, "readme": d["readme"]},
        "people": P.people(), "areas": AREAS, "forms": FORM_NAMES, "household": d["household"],
        "firm": {"name": d["firm"]["name"], "deadlines": d["firm"]["deadlines"], "identity": d["firm"]["firm_identity"], "assignment": s.assignment},
        "standards": s.standards, "budget": s.budget, "client": d["client"], "timeline": d["timeline"],
        "agency": d["tax_agency_records"], "what_if": d["what_if"], "rates": P.rates,
        "engine_rules": d["engine_reference"]["rules"], "ai": ai.available(),
    })


@app.get("/api/state")
def get_state(req: Request):
    pid = person_of(req)
    s = state()
    data = {
        "me": pid, "role": role_of(pid), "cleared": cleared(pid),
        "summary": s.summary(), "findings": s.findings(), "adjustments": list(s.adjustments.values()),
        "verifications": [v for v in s.verifications.values()], "notes": list(s.notes.values()),
        "questions": list(s.questions.values()), "signoffs": s.signoff_status(), "steps": s.required_steps(),
        "filing": s.filing, "inbox": s.inbox(pid), "changes": s.changes_since(pid), "time": s.time_vs_budget(),
        "area_hashes": {a: s.area_hash(a) for a in AREAS}, "return_hash": s.return_hash(),
        "assignment": s.assignment, "area_assignee": s.area_assignee, "standards": s.standards,
        "files": s.files, "links": s.links, "undone_batches": sorted(s.undone_batches),
        "batches": _batches(s), "last_event": s.events[-1]["id"] if s.events else 0,
        "view_log": s.view_log if role_of(pid) in ("firm_administrator", "partner") else [],
        "variances": s.variances(), "facts": s.facts,
    }
    if role_of(pid) == "client":
        data = {k: data[k] for k in ("me", "role", "cleared", "filing", "inbox", "questions", "files", "last_event")} | {
            "summary": {"approved": s.summary()["approved"], "engine": s.summary()["engine"]},
            "questions": [q for q in s.questions.values() if q["to"] == "client"]}
    return out(req, data)


def _batches(s: State):
    seen = {}
    for e in s.events:
        if e["batch"] and e["type"] not in ("batch.undo", "batch.redo"):
            b = seen.setdefault(e["batch"], {"batch": e["batch"], "actor": e["actor"], "ts": e["ts"], "count": 0, "types": set()})
            b["count"] += 1
            b["types"].add(e["type"])
    out_ = []
    for b in seen.values():
        b["types"] = sorted(b["types"])
        b["undone"] = b["batch"] in s.undone_batches
        out_.append(b)
    return sorted(out_, key=lambda x: x["ts"], reverse=True)[:30]


@app.get("/api/lines")
def get_lines(req: Request, version: str | None = None):
    _staff_only(req)
    return out(req, views.lines(state(), version))


@app.get("/api/line/{key}")
def get_line(req: Request, key: str, version: str | None = None):
    _staff_only(req)
    d = views.line_detail(state(), key, version)
    if not d:
        raise HTTPException(404, "no such line")
    return out(req, d)


@app.get("/api/documents")
def get_documents(req: Request):
    pid = person_of(req)
    docs = views.documents(state())
    if role_of(pid) == "client":
        docs = [d for d in docs if d["uploaded_by"] == "client"]
    return out(req, docs)


@app.get("/api/documents/{doc_id}")
def get_document(req: Request, doc_id: str):
    _staff_only(req)
    d = views.document_detail(state(), doc_id)
    if not d:
        raise HTTPException(404, "no such document")
    return out(req, d)


@app.get("/api/schedules/{name}")
def get_schedule(req: Request, name: str):
    _staff_only(req)
    fn = {"sales": views.sales, "assets": views.assets, "books-to-tax": views.books_to_tax, "state-split": views.state_split,
          "basis": views.basis, "carryovers": views.carryovers, "k1": views.k1s, "prior-year": views.prior_year,
          "payments": views.payments}.get(name)
    if not fn:
        raise HTTPException(404, "no such schedule")
    return out(req, fn(state()))


@app.get("/api/compare")
def get_compare(req: Request, a: str = "v2", b: str = "v3"):
    _staff_only(req)
    return out(req, views.compare(state(), a, b))


@app.get("/api/search")
def get_search(req: Request, q: str):
    _staff_only(req)
    return out(req, views.search(state(), q))


@app.post("/api/ask")
async def post_ask(req: Request):
    pid = _staff_only(req)
    body = await req.json()
    s = state()
    res = ai.answer(s, body.get("question", ""), body.get("mode", "ask"), body.get("focus"))
    # Every AI call is on the record: who asked, what, which model, which sources it cited.
    store.append(pid, "ai.answered", {"question": body.get("question", "")[:500], "mode": res["mode"], "model": res["model"],
                                      "citations": res["citations"], "unverified": res["unverified"], "answer": res["answer"][:4000]})
    return out(req, res)


@app.post("/api/whatif")
async def post_whatif(req: Request):
    _staff_only(req)
    body = await req.json()
    s = state()
    rows = []
    for x in body.get("changes", []):
        e = s.tax_effect(x.get("category"), float(x.get("delta", 0)))
        rows.append({**x, **e})
    base = s.summary()["approved"]
    fed = sum(r["fed"] for r in rows)
    ca = sum(r["ca"] for r in rows)
    fb = sum(r["fed_balance"] for r in rows)
    cb = sum(r["ca_balance"] for r in rows)
    return out(req, {"rows": rows, "federal_tax_change": round(fed), "california_tax_change": round(ca),
                     "federal_balance_due": round(base["federal"]["balance_due"] + fed + fb),
                     "california_balance_due": round(base["california"]["balance_due"] + ca + cb),
                     "caveat": "Linear estimate at v3 marginal rates; large changes can cross thresholds (CTC phase-out, SALT cap, QBI). The engine recompute is the final word."})


def _staff_only(req):
    pid = person_of(req)
    if role_of(pid) == "client":
        raise HTTPException(403, "Client portal users see their questions, documents and approval only")
    return pid


@app.post("/api/events")
async def post_events(req: Request):
    pid = person_of(req)
    body = await req.json()
    items = body.get("events") or [body]
    batch = body.get("batch") or (store.new_id("batch") if len(items) > 1 else None)
    s = state()
    for it in items:  # authorize everything first: a batch is all-or-nothing
        it.setdefault("payload", {})
        if it["type"] in ("adjustment.proposed", "verification.added", "note.created", "question.asked", "signoff.signed", "file.attached", "link.added", "time.logged"):
            it["payload"].setdefault("id", store.new_id(it["type"].split(".")[0][:4]))
        authorize(s, pid, it["type"], it["payload"])
    written = []
    for it in items:
        if it["type"] == "signoff.signed":
            it["payload"]["hash"] = state().return_hash() if it["payload"]["area"] == "return" else state().area_hash(it["payload"]["area"])
        written.append(store.append(pid, it["type"], it["payload"], _entity(it["type"], it["payload"]), batch))
    return out(req, {"written": written, "batch": batch})


@app.post("/api/unmask")
async def unmask(req: Request):
    pid = person_of(req)
    body = await req.json()
    if not cleared(pid):
        store.append(pid, "view.sensitive", {"what": body.get("what"), "context": body.get("context"), "granted": False})
        raise HTTPException(403, "No sensitive-data clearance. This attempt was logged.")
    hh = P.data["household"]
    what = body.get("what", "")
    val = None
    for x in hh["people"]:
        if what == f"ssn:{x['id']}":
            val = x["ssn"]
        if what == f"ip_pin:{x['id']}":
            val = x.get("ip_pin")
    if what == "bank:routing":
        val = hh["bank_account_for_refund_or_payment"]["routing"]
    if what == "bank:account":
        val = hh["bank_account_for_refund_or_payment"]["account"]
    if what == "foreign:account":
        val = P.ev_field("D36", "account_number")["value"]
    for f in state().facts:  # corrected facts win over the organizer
        if f.get("path") == what.replace("ssn:", "household:") + ".ssn":
            val = f["to"]
    if val is None:
        raise HTTPException(404, "unknown field")
    store.append(pid, "view.sensitive", {"what": what, "context": body.get("context"), "granted": True})
    return JSONResponse({"what": what, "value": val})  # deliberately unmasked


@app.post("/api/files")
async def upload(req: Request, file: UploadFile = File(...), target: str = Form(""), note: str = Form("")):
    pid = person_of(req)
    data = await file.read()
    if len(data) > 5_000_000:
        raise HTTPException(413, "5 MB limit in the prototype")
    meta = store.save_file(file.filename, file.content_type or "application/octet-stream", data, pid)
    ev = store.append(pid, "file.attached", {**meta, "target": target, "note": note}, target or None)
    return out(req, {"file": meta, "event": ev})


@app.get("/api/files/{fid}")
def download(fid: str):
    r = store.get_file(fid)
    if not r:
        raise HTTPException(404)
    return Response(r.data, media_type=r.mime, headers={"Content-Disposition": f'inline; filename="{r.name}"'})


@app.get("/api/events")
def get_events(req: Request, since: int = 0):
    _staff_only(req)
    return out(req, [e for e in store.all_events() if e["id"] > since][-500:])


@app.get("/api/stream")
async def stream(req: Request):
    q: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    unsub = store.subscribe(lambda ev: loop.call_soon_threadsafe(q.put_nowait, ev))

    async def gen():
        try:
            yield "retry: 3000\n\n"
            while True:
                if await req.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=20)
                    yield f"data: {json.dumps({'id': ev['id'], 'type': ev['type'], 'actor': ev['actor']})}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            unsub()
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------------- exports
@app.get("/api/export/notice/{notice}", response_class=HTMLResponse)
def export_notice(req: Request, notice: str):
    _staff_only(req)
    return HTMLResponse(mask_text(exports.notice_package(state(), notice)))


@app.get("/api/export/client-copy", response_class=HTMLResponse)
def export_client(req: Request):
    person_of(req)
    return HTMLResponse(mask_text(exports.client_copy(state())))


@app.get("/api/export/rollforward")
def export_rollforward(req: Request):
    _staff_only(req)
    return out(req, exports.rollforward(state()))


@app.get("/api/export/workpaper", response_class=HTMLResponse)
def export_workpaper(req: Request):
    _staff_only(req)
    return HTMLResponse(mask_text(exports.workpaper_record(state())))


# ---------------------------------------------------------------------- admin
@app.post("/api/admin/reset")
def admin_reset(req: Request):
    pid = person_of(req)
    if role_of(pid) not in ("firm_administrator", "partner"):
        raise HTTPException(403, "Only the administrator or partner can reset the demo")
    store.reset()
    return {"ok": True}


@app.post("/api/admin/seed")
def admin_seed(req: Request):
    pid = person_of(req)
    if role_of(pid) not in ("firm_administrator", "partner"):
        raise HTTPException(403, "Only the administrator or partner can load the demo season")
    store.reset()
    seed.seed(P, state)
    return {"ok": True, "events": len(store.all_events())}


# ---------------------------------------------------------------------- frontend
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = DIST / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
