"""Self-contained records: notice response, client copy, roll-forward, full workpaper."""
from __future__ import annotations

import html
from datetime import datetime, timezone

from . import views
from .packet import AREAS
from .state import State

CSS = """body{font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;color:#1d1d1f;max-width:960px;margin:32px auto;padding:0 20px}
h1{font-size:22px}h2{font-size:17px;margin-top:28px;border-bottom:1px solid #ddd;padding-bottom:4px}h3{font-size:15px}
table{border-collapse:collapse;width:100%;margin:8px 0}td,th{border:1px solid #ddd;padding:4px 8px;text-align:left;vertical-align:top}
th{background:#f5f5f7}td.n{text-align:right;font-variant-numeric:tabular-nums}.doc{background:#fafafa;border:1px solid #e5e5e5;padding:10px;white-space:pre-wrap;font-family:ui-monospace,monospace;font-size:12px}
.muted{color:#666}.tag{display:inline-block;padding:0 6px;border-radius:4px;background:#eef;font-size:12px}"""


def esc(x):
    return html.escape(str(x if x is not None else ""))


def money(x):
    try:
        return f"{float(x):,.0f}"
    except Exception:
        return esc(x)


def page(title, body):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{esc(title)}</title><style>{CSS}</style></head><body>{body}<p class='muted'>Generated {ts}. Packet SHA-256 recorded with every export so the record can be tied to the exact inputs.</p></body></html>"


def _doc_block(s: State, doc_id, pages=None):
    d = s.p.documents[doc_id]
    parts = [f"<h3>{esc(doc_id)} — {esc(d['title'])}</h3><p class='muted'>{esc(d['issuer'])}; received {esc(d['received_at'][:10])}; file {esc(d['file_name'])}</p>"]
    for pg in d["pages"]:
        if pages and pg["page"] not in pages:
            continue
        parts.append(f"<div class='doc'><b>Page {pg['page']}</b>\n{esc(pg['printed_content'])}</div>")
    vers = [v for v in s.verifications.values() if v["active"] and v["target"] == f"doc:{doc_id}"]
    if vers:
        parts.append("<p>Verified: " + "; ".join(f"{esc(v['vtype'])} by {esc(v['by'])} {esc(v['ts'][:10])}" for v in vers) + "</p>")
    return "".join(parts)


def _trail(s: State, pred):
    rows = [e for e in s.events if pred(e)]
    if not rows:
        return "<p class='muted'>No workpaper events.</p>"
    return "<table><tr><th>When</th><th>Who</th><th>What</th><th>Detail</th></tr>" + "".join(
        f"<tr><td>{esc(e['ts'])}</td><td>{esc(e['actor'])}</td><td>{esc(e['type'])}</td><td>{esc(e['payload'].get('description') or e['payload'].get('text') or e['payload'].get('reason') or e['payload'].get('vtype') or '')}</td></tr>"
        for e in rows) + "</table>"


def _line_rows(s: State, keys):
    out = "<table><tr><th>Line</th><th>Label</th><th>Engine</th><th>Workpaper</th><th>Sources</th></tr>"
    for k in keys:
        l = s.p.line(k)
        if not l:
            continue
        wp = money(s.adjusted_value(k)) + (" <span class='tag'>pending engine recompute</span>" if s.stale(k) else "")
        out += f"<tr><td>{esc(k)}</td><td>{esc(l['label'])}</td><td class='n'>{money(l['value'])}</td><td class='n'>{wp}</td><td>{esc(', '.join(l.get('sources') or []))}</td></tr>"
    return out + "</table>"


def notice_package(s: State, notice: str):
    p = s.p
    n = next((x for x in p.data["tax_agency_records"]["notices"] if x["id"] == notice), None)
    if not n:
        return page("Not found", "<p>No such notice.</p>")
    body = [f"<h1>Response record — {esc(n['type'])}, tax year {n['tax_year']}</h1>",
            f"<p>{esc(p.data['packet']['name'])} · client {esc(p.data['packet']['client_id'])} · notice dated {esc(n['dated'])} · response due {esc(n.get('response_due'))}</p>",
            f"<p>Return status: <span class='tag'>{esc(s.filing['status'])}</span> · return hash {esc(s.return_hash())} · packet {esc(p.sha256[:16])}…</p>"]
    items = n.get("items_under_examination") or [n.get("summary")]
    for i, item in enumerate(items, 1):
        body.append(f"<h2>Item {i}: {esc(item)}</h2>")
        if "Noncash" in item:
            body.append(_line_rows(s, ["F8283.A1.stock", "F8283.A1.vehicle", "SchA.12", "SchA.11", "SchA.14"]))
            body.append("<p><b>Position.</b> Stock: 200 sh Northlake Total Market Index Fund held since 04/2019 (long-term, publicly traded) to a donor-advised fund; deduction at fair market value 14,500 (average of high and low on 12/05/2025); written acknowledgment states no goods or services. Vehicle: deduction limited to gross proceeds from the charity's arm's-length sale per Form 1098-C (IRC 170(f)(12)); the client's estimate was not used.</p>")
            body.append(_doc_block(s, "D65") + _doc_block(s, "D66"))
            body.append("<h3>Workpaper trail</h3>" + _trail(s, lambda e: (e.get("entity") or "").startswith(("line:F8283", "line:SchA.1")) or e["payload"].get("finding") == "VEHICLE_DONATION_VALUE" or e["payload"].get("id") == "VEHICLE_DONATION_VALUE"))
        elif "Schedule C" in item:
            b = views.books_to_tax(s)
            r = b["receipts"]
            body.append("<table><tr><th>Reconciliation of gross receipts</th><th>Amount</th></tr>"
                        f"<tr><td>Forms 1099-NEC (Fennimore, Atlas, Sable &amp; Finch, Riverbend, Quill)</td><td class='n'>{money(r['forms_1099_nec'])}</td></tr>"
                        f"<tr><td>Form 1099-K (Paywell) — Atlas card payments, also included in Atlas's 1099-NEC</td><td class='n'>{money(r['form_1099_k'])}</td></tr>"
                        f"<tr><td>Less duplicate reporting of Atlas card payments</td><td class='n'>({money(r['atlas_paid_by_card_in_1099k'])})</td></tr>"
                        f"<tr><td>Receipts from 11 clients who issued no Form 1099</td><td class='n'>{money(r['no_1099_clients'])}</td></tr>"
                        f"<tr><th>Gross receipts per books and return</th><th class='n'>{money(r['books_revenue'])}</th></tr></table>")
            body.append(_line_rows(s, ["SchC.1", "SchC.31"]))
            for d in ("D14", "D15", "D16", "D17", "D18", "D19", "D20", "D21"):
                body.append(_doc_block(s, d, pages=[3] if d == "D15" else None))
            body.append("<h3>Workpaper trail</h3>" + _trail(s, lambda e: (e.get("entity") or "").startswith("line:SchC.1") or e["payload"].get("finding") == "SCHC_1099K_DOUBLE" or e["payload"].get("id") == "SCHC_1099K_DOUBLE"))
    signs = s.signoff_status()
    body.append("<h2>Sign-offs on the filed return</h2><table><tr><th>Area</th><th>Level</th><th>By</th><th>When</th><th>Current?</th></tr>" + "".join(
        f"<tr><td>{esc(AREAS.get(x['area'], x['area']))}</td><td>{esc(x['level'])}</td><td>{esc(x['by'])}</td><td>{esc(x['ts'])}</td><td>{'yes' if x['valid'] else 'reopened'}</td></tr>" for x in signs) + "</table>")
    return page(f"Notice response {notice}", "".join(body))


def client_copy(s: State):
    sm = s.summary()["approved"]
    p = s.p
    hh = p.data["household"]
    keys = ["F1040.1z", "F1040.2b", "F1040.3b", "F1040.7", "F1040.8", "F1040.9", "F1040.10", "F1040.11", "F1040.12", "F1040.13", "F1040.15", "F1040.24", "F1040.33"]
    body = [f"<h1>Your 2025 tax return — summary</h1><p>{esc(', '.join(x['name'] for x in hh['people'][:2]))} · married filing jointly · prepared by {esc(p.data['firm']['name'])}</p>",
            f"<table><tr><th></th><th>Federal</th><th>California</th></tr><tr><td>Total tax</td><td class='n'>{money(sm['federal']['total_tax'])}</td><td class='n'>{money(sm['california']['total_tax'])}</td></tr>"
            f"<tr><td>Payments</td><td class='n'>{money(sm['federal']['payments'])}</td><td class='n'>{money(sm['california']['payments'])}</td></tr>"
            f"<tr><td>{'Balance due' if sm['federal']['balance_due'] > 0 else 'Refund'}</td><td class='n'>{money(abs(sm['federal']['balance_due']))}</td><td class='n'>{money(abs(sm['california']['balance_due']))}</td></tr></table>",
            "<p class='muted'><b>Estimated.</b> Totals above are the computed return plus adjustments approved by your CPA team, estimated at marginal rates; the final figures come from the recomputed return. In the lines below, 'Workpaper' recomputes simple sums; lines marked 'pending engine recompute' depend on tax calculations that are re-run before filing.</p>",
            _line_rows(s, keys), f"<p>Filing status: {esc(s.filing['status'])}</p>"]
    return page("2025 return — client copy", "".join(body))


def rollforward(s: State):
    p = s.p
    return {
        "for_tax_year": 2026, "from_return": {"version": p.current_version, "hash": s.return_hash(), "packet_sha256": p.sha256, "filing": s.filing["status"]},
        "carryovers": views.carryovers(s), "basis": views.basis(s), "assets": views.assets(s),
        "open_items": [{"id": n["id"], "text": n["text"], "target": n["target"]} for n in s.notes.values() if n["status"] == "open" or n.get("carry_forward")],
        "open_findings": [{"id": f["id"], "title": f["title"]} for f in s.findings() if f["status"] == "open" and f["severity"] in ("error", "review", "warning")],
        "outside_filings": next((f["summary"] for f in s.findings_base if f["id"] == "OUTSIDE_FILINGS"), None),
        "judgments": [n for n in s.notes.values() if n.get("kind") in ("judgment", "election", "penalty_decision", "due_diligence")],
        "planning": {**p.data["planning_reference_2026"],
                     "federal_safe_harbor_amount": round(1.10 * s.summary()["approved"]["federal"]["total_tax"]),
                     "federal_quarterly": round(1.10 * s.summary()["approved"]["federal"]["total_tax"] / 4),
                     "california_safe_harbor_amount": round(1.10 * s.summary()["approved"]["california"]["total_tax"])},
        "prior_preparer_vs_us": views.prior_year(s)["did_vs_changed"],
    }


def workpaper_record(s: State):
    f = s.findings()
    body = [f"<h1>Workpaper record — {esc(s.p.data['packet']['name'])}</h1><p>Return hash {esc(s.return_hash())} · packet {esc(s.p.sha256)} · status {esc(s.filing['status'])}</p>"]
    body.append("<h2>Findings</h2><table><tr><th>Finding</th><th>Severity</th><th>Status</th><th>Fed est.</th><th>CA est.</th></tr>" + "".join(
        f"<tr><td>{esc(x['title'])}</td><td>{esc(x['severity'])}</td><td>{esc(x['status'])}</td><td class='n'>{money(x['est_fed'])}</td><td class='n'>{money(x['est_ca'])}</td></tr>" for x in f) + "</table>")
    body.append("<h2>Adjustments</h2><table><tr><th>Line</th><th>Change</th><th>Why</th><th>Who</th><th>Status</th><th>Fed</th><th>CA</th></tr>" + "".join(
        f"<tr><td>{esc(a['line'])}</td><td class='n'>{money(a['delta'])}</td><td>{esc(a['reason'])}</td><td>{esc(a['proposed_by'])}</td><td>{esc(a['status'])}</td><td class='n'>{money(a['fed_effect'])}</td><td class='n'>{money(a['ca_effect'])}</td></tr>" for a in s.adjustments.values()) + "</table>")
    body.append("<h2>Required steps</h2><ul>" + "".join(f"<li>{'✔' if x['done'] else '✘'} {esc(x['step'])} — {esc(x['detail'])}</li>" for x in s.required_steps()) + "</ul>")
    body.append("<h2>Event log</h2>" + _trail(s, lambda e: e["type"] not in ("view.seen",)))
    return page("Workpaper record", "".join(body))
