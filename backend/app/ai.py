"""'Ask the workpaper': grounded answers and drafts with checked citations.

Design rules (why this is safe to put in front of a CPA):
- Retrieval first: the model only sees evidence pulled from the workpaper (lines, documents, findings,
  client answers), each with a stable id. It is told to cite every statement with those ids.
- Citations are verified after generation: any id the model cites that was not in the evidence is flagged
  as unverified, so a fabricated source can't look real.
- Nothing is written to the return. Drafts become notes or questions only when a person saves them, and
  every AI call is logged as an event (question, model, cited ids).
- No API key? The feature degrades to retrieval only: it shows the cited evidence it would have used.
"""
from __future__ import annotations

import json
import os
import re

import httpx

from . import views
from .packet import area_for_line
from .state import State

ANTHROPIC_MODEL = os.environ.get("AI_MODEL_ANTHROPIC", "claude-sonnet-5-5")
GEMINI_MODEL = os.environ.get("AI_MODEL_GEMINI", "gemini-2.5-flash")

SYSTEM = """You are the assistant inside a CPA firm's tax workpaper for one 2025 joint return (Okafor-Lindqvist).
Answer ONLY from the EVIDENCE provided. Every factual sentence must end with one or more citations in square
brackets using the evidence ids exactly as given, e.g. [line:SchC.1] [doc:D15] [finding:SCHC_1099K_DOUBLE].
If the evidence does not answer the question, say so plainly and say what document or question would.
Do not invent numbers; only use figures in the evidence (simple arithmetic on them is fine, show it).
Statements about tax law must be labelled "(reviewer to confirm)". Be concise: a CPA is reading.
'Engine' means the software's computed return; 'workpaper' means engine plus approved adjustments."""

MODES = {
    "ask": "Answer the reviewer's question.",
    "draft_client_question": "Draft a short, plain-English question to the client (no jargon, one or two sentences, "
                             "polite) that would resolve the issue. Then, on a new line starting 'Why:', cite the evidence.",
    "draft_notice_response": "Draft the narrative of a response to the IRS examination letter for the items it lists, "
                             "using only the evidence: position, supporting documents, reconciliation. Cite everything.",
}


def _line_brief(s: State, key: str):
    l = s.p.line(key)
    if not l:
        return None
    ins = []
    for i in (l.get("inputs") or [])[:8]:
        x = s.p.line(i)
        if x:
            ins.append(f"{i}={x['value']}")
    srcs = []
    for z in (l.get("sources") or [])[:5]:
        e = s.p.ev(z)
        if e:
            srcs.append(f"{e['document_id']} p{e['page']} {e['label']}={e['value']} (conf {e['confidence']})")
        else:
            srcs.append(z)
    adj = [a for a in s.adjustments.values() if a["line"] == key and a["status"] != "reversed"]
    txt = (f"{key} {l['label']}: engine {l['value']}; workpaper {s.adjusted_value(key)}"
           f"{' (pending engine recompute)' if s.stale(key) else ''}; rule {l['rule']}")
    if ins:
        txt += "; inputs " + ", ".join(ins)
    if srcs:
        txt += "; sources " + " | ".join(srcs)
    if l.get("note"):
        txt += "; engine note: " + l["note"]
    for a in adj:
        txt += f"; adjustment {a['delta']:+,.0f} ({a['status']}) by {a['proposed_by']}: {a['reason']}"
    return txt


def retrieve(s: State, question: str, focus: str | None = None, limit: int = 14):
    p = s.p
    items: dict[str, str] = {}
    sm = s.summary()
    items["summary:return"] = (f"Engine v3: federal total tax {sm['engine']['federal']['total_tax']}, balance due "
                               f"{sm['engine']['federal']['balance_due']}; California total tax {sm['engine']['california']['total_tax']}, "
                               f"balance due {sm['engine']['california']['balance_due']}. Workpaper (approved adjustments, estimated): "
                               f"federal tax {sm['approved']['federal']['total_tax']}, balance {sm['approved']['federal']['balance_due']}; "
                               f"California tax {sm['approved']['california']['total_tax']}, balance {sm['approved']['california']['balance_due']}.")
    targets = []
    if focus:
        targets.append(focus)
    q = question or ""
    targets += [f"line:{k}" for k in re.findall(r"\b((?:F\d{4}|Sch\w*|F540NR|SchCA540NR|F4562-[CE]|FTB\w+)\.[\w.]+)", q) if p.line(k)]
    targets += [f"doc:{d}" for d in re.findall(r"\bD\d{2}\b", q) if d in p.documents]
    words = [w for w in re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{2,}", q.lower()) if w not in STOP]
    scored = {}
    for w in words[:12]:
        for r in views.search(s, w)[:15]:
            scored[(r["type"], r["id"])] = scored.get((r["type"], r["id"]), 0) + 1
    ranked = sorted(scored, key=lambda k: -scored[k])
    for typ, ident in ranked:
        targets.append(f"{typ}:{ident}")
    seen = set()
    for t in targets:
        if t in seen or len(items) > limit:
            continue
        seen.add(t)
        kind, _, ident = t.partition(":")
        if kind == "line":
            b = _line_brief(s, ident)
            if b:
                items[t] = b
        elif kind == "doc":
            d = p.documents.get(ident.split("#")[0])
            if d:
                text = " ".join(pg["printed_content"] for pg in d["pages"])[:1600]
                landed = p.landed[p.current_version].get(d["id"], [])
                items[t] = f"{d['id']} {d['title']} (issuer {d['issuer']}, received {d['received_at'][:10]}): {text} || lands on: {', '.join(landed[:12]) or 'nothing'}"
        elif kind == "finding":
            f = next((x for x in s.findings() if x["id"] == ident), None)
            if f:
                items[t] = f"Finding ({f['severity']}, {f['status']}): {f['title']}. {f['summary']} Engine {f['engine_value']} -> expected {f['expected_value']}."
        elif kind == "qa":
            x = p.qa.get(ident)
            if x:
                items[t] = f"Client questionnaire {ident} ({x['answered_by']}): Q: {x['question']} A: {x['answer']}"
        elif kind == "msg":
            x = p.messages.get(ident)
            if x:
                items[t] = f"Client message {ident} {x['sent_at'][:10]} from {x['from']}: {x['text']}"
        elif kind == "note":
            n = s.notes.get(ident)
            if n:
                items[t] = f"Workpaper note ({n['kind']}, {n['status']}) on {n['target']} by {n['by']}: {n['text']}"
    # relevant open findings are always useful context
    for f in s.findings():
        if len(items) > limit + 4:
            break
        if f["status"] == "open" and f["severity"] in ("error", "review") and any(w in (f["title"] + f["summary"]).lower() for w in words):
            items.setdefault(f"finding:{f['id']}", f"Finding ({f['severity']}, open): {f['title']}. {f['summary']}")
    return items


STOP = set("schedule return engine number workpaper line lines amount drop dropped change changed value form tax 2025 the and for with that this what why how does did was were are is from into have has had about which there their they them our your you why when where who whom than then also just only into over under more less much many any all some each per its it's not but can could would should will shall may might must".split())


GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
_gemini_model: str | None = None
_gemini_candidates: list[str] = []


def _gemini_headers():
    # The key travels in a header, never in the URL, so it can't leak into error messages or logs.
    return {"x-goog-api-key": os.environ["GEMINI_API_KEY"], "content-type": "application/json"}


def _pick_gemini_model() -> str:
    """Ask Google which models this key can use and pick a current 'flash' model (cheap, fast)."""
    global _gemini_model, _gemini_candidates
    if _gemini_model:
        return _gemini_model
    preferred = os.environ.get("AI_MODEL_GEMINI")
    try:
        r = httpx.get(f"{GEMINI_BASE}/models", headers=_gemini_headers(), params={"pageSize": 200}, timeout=20)
        r.raise_for_status()
        names = [m["name"].split("/", 1)[1] for m in r.json().get("models", [])
                 if "generateContent" in (m.get("supportedGenerationMethods") or [])]
    except Exception:
        names = []
    if preferred and (not names or preferred in names):
        _gemini_model = preferred
    else:
        flash = [n for n in names if "flash" in n and "lite" not in n and "image" not in n and "tts" not in n and "exp" not in n]
        stable = [n for n in flash if "preview" not in n] or flash
        _gemini_model = sorted(stable, key=lambda n: ("latest" not in n, n), reverse=False)[-1] if stable else (names[0] if names else "gemini-2.5-flash")
        # prefer an explicit '-latest' alias when Google offers one
        latest = [n for n in stable if n.endswith("flash-latest")]
        if latest:
            _gemini_model = latest[0]
    # fallbacks when the first choice is busy: other flash models, then flash-lite
    lite = [n for n in names if "flash-lite" in n and "preview" not in n]
    lite_sorted = sorted(lite, reverse=True)
    rest = [n for n in sorted(stable if names else [], reverse=True) if n != _gemini_model]
    _gemini_candidates = [_gemini_model] + [n for n in lite_sorted[:1] + rest[:1] + lite_sorted[1:2] if n != _gemini_model]
    return _gemini_model


def _call_model(system: str, user: str):
    global _gemini_model
    if os.environ.get("ANTHROPIC_API_KEY"):
        r = httpx.post("https://api.anthropic.com/v1/messages", timeout=60, headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": ANTHROPIC_MODEL, "max_tokens": 900, "system": system, "messages": [{"role": "user", "content": user}]})
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json()["content"]), f"anthropic:{ANTHROPIC_MODEL}"
    if os.environ.get("GEMINI_API_KEY"):
        # Instructions go at the top of the message: some models (e.g. flash-lite variants) reject a separate system field.
        body = {"contents": [{"role": "user", "parts": [{"text": "INSTRUCTIONS:\n" + system + "\n\n" + user}]}],
                "generationConfig": {"maxOutputTokens": 1200, "temperature": 0.2}}
        import time
        first = _pick_gemini_model()
        tried, last = [], None
        deadline = time.monotonic() + 55  # never keep the reviewer waiting more than about a minute
        for model in (_gemini_candidates or [first]):
            if time.monotonic() > deadline:
                break
            # short, cited answers don't need hidden "thinking", which is what makes flash models slow.
            # Gemini 3+ uses thinkingLevel; 2.x uses thinkingBudget.
            m = re.match(r"gemini-(\d+)", model)
            if m and int(m.group(1)) >= 3:
                body["generationConfig"]["thinkingConfig"] = {"thinkingLevel": "low"}
            else:
                body["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}
            for attempt in range(2):
                remaining = max(5.0, deadline - time.monotonic())
                try:
                    r = httpx.post(f"{GEMINI_BASE}/models/{model}:generateContent", headers=_gemini_headers(), json=body, timeout=min(20.0, remaining))
                except httpx.TimeoutException:
                    # too slow: don't wait twice on the same model, go straight to the faster backup
                    r = httpx.Response(504, json={"error": {"message": f"{model} took too long to answer"}}, request=httpx.Request("POST", GEMINI_BASE))
                    break
                if r.status_code == 400 and "thinking" in r.text.lower() and "thinkingConfig" in body["generationConfig"]:
                    body["generationConfig"].pop("thinkingConfig")  # this model can't switch thinking off: ask again without the setting
                    continue
                if r.status_code in (429, 500, 503) and attempt == 0 and time.monotonic() + 8 < deadline:
                    time.sleep(2)  # busy: one short retry, then try the next model
                    continue
                break
            tried.append(model)
            if r.status_code == 404:
                _gemini_model = None
                os.environ.pop("AI_MODEL_GEMINI", None)
                last = r
                continue
            if r.status_code in (429, 500, 503, 504, 400):
                last = r
                continue
            r.raise_for_status()
            parts = r.json()["candidates"][0].get("content", {}).get("parts", [])
            return "".join(pt.get("text", "") for pt in parts), f"gemini:{model}"
        if last is not None:
            last.raise_for_status()
    return None, None


def _safe_error(ex: Exception) -> str:
    """Errors shown to users and stored in the log never include URLs, keys or tokens."""
    if isinstance(ex, httpx.HTTPStatusError):
        msg = f"provider returned HTTP {ex.response.status_code}"
        try:
            detail = ex.response.json().get("error", {})
            if isinstance(detail, dict) and detail.get("message"):
                msg += f": {detail['message'][:160]}"
        except Exception:
            pass
    else:
        msg = type(ex).__name__
    for k in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
        v = os.environ.get(k)
        if v:
            msg = msg.replace(v, "[key]")
    import re as _re
    return _re.sub(r"https?://\S+", "[url]", msg)


def available():
    return "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "gemini" if os.environ.get("GEMINI_API_KEY") else None


def answer(s: State, question: str, mode: str = "ask", focus: str | None = None):
    mode = mode if mode in MODES else "ask"
    if mode == "draft_notice_response":
        n = s.p.data["tax_agency_records"]["notices"][1]
        question = question or ("Letter 566 items: " + " | ".join(n["items_under_examination"]))
        focus = focus or "finding:VEHICLE_DONATION_VALUE"
    ev = retrieve(s, question + (" " + focus if focus else ""), focus)
    if mode == "draft_notice_response":
        for k in ("finding:SCHC_1099K_DOUBLE", "finding:DAF_ACK", "doc:D65", "doc:D66", "line:SchC.1", "line:F8283.A1.vehicle", "line:F8283.A1.stock"):
            kind, _, ident = k.partition(":")
            if k not in ev:
                more = retrieve(s, ident, k, limit=1)
                ev.update({kk: vv for kk, vv in more.items() if kk == k})
    evidence = "\n".join(f"[{k}] {v}" for k, v in ev.items())
    user = f"TASK: {MODES[mode]}\n\nQUESTION / ITEM: {question}\n\nEVIDENCE:\n{evidence}"
    text, model, error = None, None, None
    try:
        text, model = _call_model(SYSTEM, user)
    except Exception as ex:  # network/key problems must not break the workpaper
        error = _safe_error(ex)
    cited = re.findall(r"\[([a-z]+:[^\]\s]+)\]", text or "")
    valid = [c for c in dict.fromkeys(cited) if c in ev]
    unverified = [c for c in dict.fromkeys(cited) if c not in ev]
    if text is None:
        text = ("AI drafting is off" + (f" ({error})" if error else " (no API key configured)") +
                ". Here is the evidence the assistant would use — each item opens in the workpaper:\n\n" +
                "\n".join(f"• {v[:260]}{'…' if len(v) > 260 else ''} [{k}]" for k, v in list(ev.items())[:10]))
        valid = list(ev.keys())[:10]
    return {"mode": mode, "answer": text, "model": model, "citations": valid, "unverified": unverified,
            "evidence": [{"id": k, "text": v[:400]} for k, v in ev.items()], "ai_enabled": bool(model), "error": error}
