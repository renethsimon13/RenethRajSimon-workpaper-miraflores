"""Read models: the schedules a CPA expects, built from the packet + the folded state."""
from __future__ import annotations

import re
from collections import defaultdict

from .packet import AREAS, FORM_NAMES, Packet, area_for_line
from .state import DOC_AREA, DOC_DISPOSITION, State

LOT_RE = re.compile(r"^(?P<name>.*) \(acquired (?P<acq>[^,]+), sold (?P<sold>[^;]+); proceeds (?P<proc>[\d,.\-]+), basis (?P<basis>[\d,.\-]+)(?:, adjustment (?P<code>\w) (?P<adj>[\d,.\-]+))?\)$")


def _f(s):
    return float(str(s).replace(",", "")) if s not in (None, "") else 0.0


def line_row(s: State, l: dict):
    k = l["key"]
    adjs = [a for a in s.adjustments.values() if a["line"] == k and a["status"] != "reversed"]
    vers = [v for v in s.verifications.values() if v["active"] and v["target"] == f"line:{k}"]
    notes = [n for n in s.notes.values() if n["target"] == f"line:{k}" and n["status"] == "open"]
    return {
        "key": k, "form": l["form"], "form_name": FORM_NAMES.get(l["form"], l["form"]), "line": l["line"],
        "label": l["label"], "value": l["value"], "jurisdiction": l["jurisdiction"], "rule": l["rule"],
        "area": area_for_line(k), "has_sources": bool(l.get("sources")), "inputs": l.get("inputs") or [],
        "adjusted": s.adjusted_value(k), "pending": s.adjusted_value(k, ("approved", "proposed")), "stale": s.stale(k),
        "adjustments": len(adjs), "verified": [v["vtype"] for v in vers], "open_notes": len(notes), "note": l.get("note"),
    }


def lines(s: State, version=None):
    ver = version or s.p.current_version
    return [line_row(s, l) for l in s.p.lines[ver].values()]


def resolve_source(p: Packet, src: str):
    if src.startswith("ev-"):
        e = p.ev(src)
        if not e:
            return {"type": "ev", "id": src, "missing": True}
        d = p.documents[e["document_id"]]
        return {"type": "ev", "id": src, "doc": e["document_id"], "doc_title": d["title"], "page": e["page"],
                "field": e["field"], "label": e["label"], "value": e["value"], "text_as_read": e["text_as_read"],
                "confidence": e["confidence"], "position": e["position"], "value_type": e["value_type"]}
    if src.startswith("qa-"):
        q = p.qa.get(src)
        return {"type": "qa", "id": src, "label": q["question"] if q else src, "value": q["answer"] if q else None,
                "by": q["answered_by"] if q else None}
    if src.startswith("py:"):
        return {"type": "py", "id": src, "label": "Prior-year record " + src[3:], "value": _pointer(p.data["prior_years"], src[3:])}
    if src.startswith("ref:"):
        return {"type": "ref", "id": src, "label": "Engine parameter " + src[4:], "value": _ref(p, src)}
    if src.startswith("asset:"):
        return {"type": "asset", "id": src, "label": "Asset " + src[6:]}
    if src.startswith("household:"):
        h = next((x for x in p.data["household"]["people"] if x["id"] == src[10:]), None)
        return {"type": "household", "id": src, "label": "Household: " + (h["name"] if h else src), "value": h}
    if src.startswith("timeline:"):
        return {"type": "timeline", "id": src, "label": "Timeline " + src[9:]}
    return {"type": "other", "id": src, "label": src}


def _pointer(obj, ptr):
    cur = obj
    for part in [x for x in ptr.split("/") if x]:
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, list):
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _ref(p, src):
    rest = src[4:]
    if rest.startswith("param."):
        return p.data["engine_reference"]["parameters"].get(rest[6:])
    if rest.startswith("fx."):
        parts = rest.split(".")
        return p.data["engine_reference"]["parameters"]["fx"].get(parts[1], {}).get(parts[2])
    return None


def line_detail(s: State, key: str, version=None):
    p = s.p
    ver = version or p.current_version
    l = p.lines[ver].get(key)
    if not l:
        return None

    def tree(k, depth, seen):
        x = p.lines[ver].get(k)
        if not x:
            return {"key": k, "missing": True}
        node = {"key": k, "label": x["label"], "value": x["value"], "rule": x["rule"],
                "adjusted": s.adjusted_value(k), "sources": [resolve_source(p, z) for z in (x.get("sources") or [])][:12],
                "children": []}
        if depth > 0 and k not in seen:
            node["children"] = [tree(i, depth - 1, seen | {k}) for i in (x.get("inputs") or [])]
        elif x.get("inputs"):
            node["more"] = len(x["inputs"])
        return node

    prior = p.data["prior_years"]["return_2024"]
    rule_text = p.data["engine_reference"]["rules"].get(l["rule"])
    findings = [f for f in s.findings() if any(r.get("type") == "line" and r.get("id") == key for r in f["refs"]) or any(x["line"] == key for x in f["proposed"])]
    return {
        **line_row(s, l), "rule_text": rule_text, "tree": tree(key, 3, set()),
        "sources": [resolve_source(p, z) for z in (l.get("sources") or [])],
        "dependents": p.dependents_of.get(key, []),
        "versions": {v: (p.lines[v].get(key) or {}).get("value") for v in p.versions},
        "prior_year": {"value": prior["lines"].get(key), "label": prior["line_labels"].get(key), "source": prior["line_sources"].get(key)},
        "adjustments_list": [a for a in s.adjustments.values() if a["line"] == key],
        "verifications": [v for v in s.verifications.values() if v["target"] == f"line:{key}"],
        "notes": [n for n in s.notes.values() if n["target"] == f"line:{key}"],
        "questions": [q for q in s.questions.values() if q.get("target") == f"line:{key}"],
        "links": [x for x in s.links if x["from"] == f"line:{key}" or x["to"] == f"line:{key}"],
        "files": [f for f in s.files if f.get("target") == f"line:{key}"],
        "findings": [{"id": f["id"], "title": f["title"], "severity": f["severity"], "status": f["status"]} for f in findings],
        "related": related_items(p, key),
    }


def related_items(p: Packet, key):
    """Cross-return / cross-year / related-return links."""
    rel = []
    if key in p.data["prior_years"]["return_2024"]["lines"]:
        rel.append({"kind": "prior_year", "label": "Same line on the 2024 return", "ref": f"py:/return_2024/lines/{key}"})
    if key.startswith(("SchE.28A", "F7203")):
        rel.append({"kind": "related_return", "label": "Lindqvist Family Woodworks 1120-S (prepared by Willamette CPA Group) — K-1s D39, D40", "ref": "doc:D39"})
    if key.startswith("SchE.28B") or "Ridgeline" in (p.line(key) or {}).get("label", ""):
        rel.append({"kind": "related_return", "label": "Ridgeline Real Estate Fund III 1065 — K-1 D37, state supplement D38", "ref": "doc:D37"})
    if key.startswith(("F8863", "F8812.6")):
        rel.append({"kind": "related_return", "label": "Ada's own 2025 Form 1040 (consumer software; 'can be claimed' checked)", "ref": "household:ada"})
    if key.startswith(("SchCA540NR", "F540NR")):
        fk = key.replace("SchCA540NR.", "").split(".")[0]
        rel.append({"kind": "cross_jurisdiction", "label": "Federal counterpart (Schedule CA column A)", "ref": f"line:SchCA540NR.{fk}.A"})
    return rel


# ---------------------------------------------------------------------- documents

def documents(s: State):
    p = s.p
    landed = p.landed[p.current_version]
    out = []
    for d in p.data["documents"]:
        ls = landed.get(d["id"], [])
        evs = p.values_by_doc.get(d["id"], [])
        vers = [v for v in s.verifications.values() if v["active"] and v["target"] == f"doc:{d['id']}"]
        status = "landed" if ls else ("explained" if d["id"] in DOC_DISPOSITION else "unaccounted")
        if d["id"] in ("D15", "D47", "D54", "D73"):
            status = "not_applied"
        used_in = [v for v, vv in p.versions.items() if d["id"] in vv["documents_used"]]
        superseded = [v for v, vv in p.versions.items() if d["id"] in vv["documents_superseded"]]
        low = [e["id"] for e in evs if e["confidence"] < 0.9]
        out.append({
            "id": d["id"], "title": d["title"], "type": d["document_type"], "issuer": d["issuer"], "belongs_to": d["belongs_to"],
            "tax_year": d["tax_year"], "received_at": d["received_at"], "uploaded_by": d["uploaded_by"], "file_name": d["file_name"],
            "pages": d["page_count"], "corrected": bool(d.get("marked_corrected")), "extraction": d["extraction"],
            "values": len(evs), "landed_lines": ls, "landed_count": len(ls), "disposition": DOC_DISPOSITION.get(d["id"]),
            "status": status, "area": DOC_AREA.get(d["id"], "intake_and_engagement"), "used_in_versions": used_in,
            "superseded_in": superseded, "verified": [v["vtype"] for v in vers], "low_confidence": low,
            "findings": [f["id"] for f in s.findings_base if any(r.get("doc") == d["id"] or (r.get("type") == "doc" and r.get("id") == d["id"]) for r in f["refs"])],
        })
    return out


def anchor_spans(text: str, evs: list[dict]):
    """Locate each extracted value in the printed text. For real documents, the same
    contract is served as page-image bounding boxes instead of character offsets."""
    spans = []
    used = []
    for e in evs:
        cands = []
        t = e.get("text_as_read") or ""
        if t:
            cands.append(t)
        v = e.get("value")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            cands += [f"{v:,.2f}", f"{v:,.0f}", str(v)]
        elif isinstance(v, str) and v:
            cands.append(v)
            if re.match(r"\d{4}-\d{2}-\d{2}$", v):
                y, m, d_ = v.split("-")
                cands.append(f"{m}/{d_}/{y}")
        pos = -1
        if e.get("text_as_read") == "" and e["field"].endswith("_basis"):
            # Blank on the page: anchor the read to the blank itself, e.g. "N1 ... basis (not reported)"
            lot = e["field"].split("_")[0]
            i = text.find(lot + " ")
            j = text.find("(not reported)", i) if i >= 0 else -1
            if j >= 0:
                spans.append({"ev": e["id"], "start": j, "end": j + len("(not reported)")})
                used.append((j, j + len("(not reported)")))
                continue
        if e["value_type"] == "boolean" or (e["value"] in (0, 0.0) and e["field"].endswith("_wash")):
            spans.append({"ev": e["id"], "start": None, "end": None, "implied": True})
            continue
        for c in cands:
            start = 0
            while True:
                i = text.find(c, start)
                if i < 0:
                    break
                # don't match inside a longer number
                before = text[i - 1] if i > 0 else " "
                after = text[i + len(c)] if i + len(c) < len(text) else " "
                if not (before.isdigit() or (before in ",." and i > 1 and text[i - 2].isdigit())) and not after.isdigit() and not any(a <= i < b for a, b in used):
                    pos = i
                    break
                start = i + 1
            if pos >= 0:
                spans.append({"ev": e["id"], "start": pos, "end": pos + len(c)})
                used.append((pos, pos + len(c)))
                break
        if pos < 0:
            spans.append({"ev": e["id"], "start": None, "end": None})
    return spans


def document_detail(s: State, doc_id: str):
    p = s.p
    d = p.documents.get(doc_id)
    if not d:
        return None
    evs = p.values_by_doc.get(doc_id, [])
    pages = []
    for pg in d["pages"]:
        pevs = [e for e in evs if e["page"] == pg["page"]]
        pages.append({
            "page": pg["page"], "render": {"kind": "simulated_text", "content": pg["printed_content"]},
            "anchors": anchor_spans(pg["printed_content"], pevs),
            "boxes": [{"ev": e["id"], **e["position"]} for e in pevs],
        })
    values = []
    for e in evs:
        values.append({**e, "landed": p.ev_landed.get(e["id"], []),
                       "verified": [v["vtype"] for v in s.verifications.values() if v["active"] and v["target"] == f"ev:{e['id']}"]})
    base = next(x for x in documents(s) if x["id"] == doc_id)
    return {**base, "pages_detail": pages, "values_detail": values,
            "notes": [n for n in s.notes.values() if n["target"].startswith(f"doc:{doc_id}")],
            "files": [f for f in s.files if f.get("target") == f"doc:{doc_id}"]}


# ---------------------------------------------------------------------- schedules

def sales(s: State):
    p = s.p
    rows = []
    for l in p.lines[p.current_version].values():
        m = re.match(r"F8949\.([A-Z])\.(\w+)$", l["key"])
        if not m or m.group(2) == "total":
            continue
        lm = LOT_RE.match(l["label"])
        if not lm:
            continue
        src = (l.get("sources") or [None])[0]
        e = p.ev(src) if src else None
        lot = m.group(2)
        broker = {"N": "Northlake", "M": "Meridian", "X": "Brightpath", "C": "Coinhaven"}.get(lot[0], "Woodworks (S corp)")
        rows.append({"key": l["key"], "box": m.group(1), "lot": lot, "broker": broker, "name": lm["name"], "acquired": lm["acq"], "sold": lm["sold"],
                     "proceeds": _f(lm["proc"]), "basis": _f(lm["basis"]), "adj_code": lm["code"], "adj": _f(lm["adj"]),
                     "gain": l["value"], "adjusted_gain": s.adjusted_value(l["key"]), "doc": e["document_id"] if e else None,
                     "page": e["page"] if e else None,
                     "term": "long" if m.group(1) in "DEFK" else "short",
                     "verified": bool([v for v in s.verifications.values() if v["active"] and v["target"] == f"line:{l['key']}"]),
                     "flag": "basis 0" if _f(lm["basis"]) == 0 and lot[0] in "NC" else None})
    by = defaultdict(lambda: {"count": 0, "proceeds": 0.0, "basis": 0.0, "adj": 0.0, "gain": 0.0})
    for r in rows:
        k = (r["broker"], r["term"])
        b = by[k]
        b["count"] += 1
        b["proceeds"] += r["proceeds"]
        b["basis"] += r["basis"]
        b["adj"] += r["adj"]
        b["gain"] += r["gain"]
    recon = []
    bp = {e["field"]: e["value"] for e in p.values_by_doc["D74"] if e["field"] in ("st_proceeds", "st_basis", "lt_proceeds", "lt_basis")}
    for term, pre in (("short", "st"), ("long", "lt")):
        g = by[("Brightpath", term)]
        recon.append({"statement": f"Brightpath 1099-B summary ({term}-term)", "statement_proceeds": bp[f"{pre}_proceeds"], "lots_proceeds": round(g["proceeds"], 2),
                      "statement_basis": bp[f"{pre}_basis"], "lots_basis": round(g["basis"], 2),
                      "ok": abs(bp[f"{pre}_proceeds"] - g["proceeds"]) < 0.01 and abs(bp[f"{pre}_basis"] - g["basis"]) < 0.01, "doc": "D74"})
    mer = p.ev_field("D31", "b_summary_proceeds")["value"]
    mt = by[("Meridian", "short")]["proceeds"] + by[("Meridian", "long")]["proceeds"]
    recon.append({"statement": "Meridian 1099-B (corrected) summary", "statement_proceeds": mer, "lots_proceeds": round(mt, 2), "ok": abs(mer - mt) < 0.01, "doc": "D31",
                  "note": "Difference = lot M18 on page 32 (not read by the pipeline)" if abs(mer - mt) > 0.01 else None})
    da = p.ev_field("D34", "total")["value"]
    ct = sum(r["proceeds"] for r in rows if r["broker"] == "Coinhaven")
    recon.append({"statement": "Coinhaven 1099-DA gross proceeds", "statement_proceeds": da, "lots_proceeds": ct, "ok": abs(da - ct) < 0.01, "doc": "D34"})
    return {"rows": rows, "groups": [{"broker": k[0], "term": k[1], **{kk: round(vv, 2) if isinstance(vv, float) else vv for kk, vv in v.items()}} for k, v in sorted(by.items())],
            "reconciliation": recon}


def assets(s: State):
    p = s.p
    v = p.versions[p.current_version]
    prior = {a["asset_id"]: a for a in p.data["prior_years"]["asset_records"]}
    out = []
    for a in v["assets"]:
        pr = prior.get(a["asset_id"], {})
        out.append({**a, "prior_method": pr.get("method"), "history_federal": pr.get("federal"), "history_california": pr.get("california")})
    proposed = []
    if any(x["status"] in ("approved", "proposed") and x.get("finding") == "HVAC_CAPITALIZE" for x in s.adjustments.values()):
        proposed.append({"asset_id": "SAC-HVAC (proposed)", "description": "1450 Fremont Way - heat pump system (Delta Breeze inv. 5521)",
                         "cost": 11000.0, "placed_in_service": "2025-08-12", "method": "SL / mid-month", "life_years": 27.5,
                         "federal": {"depreciation_2025": round(11000 / 27.5 * 4.5 / 12, 2)}, "california": {"depreciation_2025": round(11000 / 27.5 * 4.5 / 12, 2)},
                         "status": "from workpaper adjustment"})
    return {"assets": out, "proposed": proposed, "ca_differences": v["carryovers_out"]["california"]["depreciation_basis_differences"]}


def books_to_tax(s: State):
    p = s.p
    b = {e["field"]: e["value"] for e in p.values_by_doc["D14"]}
    v = lambda k: p.value(k)
    items = [
        ("Book net income (QuickBooks, cash basis)", b["net_income"], "D14 p1", "books"),
        ("Add back: health insurance (Erik) — moved to Schedule 1 line 17", b["Insurance - health (Erik)"], "R-SEHI", "engine"),
        ("Add back: fuel — replaced by standard mileage", b["Car and truck - fuel"], "R-STANDARD-MILEAGE", "engine"),
        ("Add back: book depreciation (5-yr SL)", b["Depreciation"], "D14 p2", "engine"),
        ("Less: tax depreciation (100% special)", -v("SchC.13"), "R-EQUIPMENT-METHOD", "engine"),
        ("Less: standard mileage", -v("SchC.9"), "R-STANDARD-MILEAGE", "engine"),
        ("Add back: 50% of meals", b["Meals"] - v("SchC.24b"), "R-MEALS-50", "engine"),
        ("Add: Form 1099-K amounts the engine could not match", v("SchC.1") - b["total_income"], "R-SCHC-GROSS", "engine"),
        ("Less: home office (simplified)", -v("SchC.30"), "R-HOME-OFFICE-SIMPLIFIED", "engine"),
    ]
    engine_total = sum(x[1] for x in items)
    wp = [a for a in s.adjustments.values() if a["status"] in ("approved", "proposed") and a["line"].startswith("SchC.")]
    wp_rows = []
    for a in wp:
        sign = -1 if a.get("category") == "schc_expense" else 1
        if a["line"] == "SchC.44a":
            continue
        wp_rows.append({"label": a["description"], "amount": sign * a["delta"], "status": a["status"], "id": a["id"]})
    receipts = {
        "forms_1099_nec": sum(p.ev_field(d, "box1")["value"] for d in ("D16", "D17", "D18", "D19", "D20")),
        "form_1099_k": p.ev_field("D21", "box1a")["value"],
        "atlas_paid_by_card_in_1099k": p.ev_field("D15", "atlas_paywell")["value"],
        "no_1099_clients": p.ev_field("D15", "unreported_small")["value"],
        "books_revenue": b["total_income"],
    }
    receipts["explained"] = receipts["forms_1099_nec"] + receipts["no_1099_clients"]
    return {"items": [{"label": x[0], "amount": x[1], "ref": x[2], "by": x[3]} for x in items], "engine_schc_31": v("SchC.31"),
            "foots": abs(engine_total - v("SchC.31")) < 1, "workpaper": wp_rows,
            "workpaper_schc_31": v("SchC.31") + sum(r["amount"] for r in wp_rows if r["status"] == "approved"),
            "receipts": receipts}


def state_split(s: State):
    p = s.p
    rows = []
    for n, label in (("1", "Wages"), ("2", "Taxable interest"), ("3", "Ordinary dividends"), ("4", "IRA distributions"),
                     ("7", "Capital gain"), ("12", "Business income"), ("17", "Rental, partnerships, S corps"),
                     ("22", "Total income"), ("26", "Adjustments")):
        row = {"line": n, "label": label}
        for col in "ABCDE":
            l = p.line(f"SchCA540NR.{n}.{col}")
            row[col] = l["value"] if l else None
            if col == "E" and l:
                row["E_rule"] = l["rule"]
                row["E_rule_text"] = p.data["engine_reference"]["rules"].get(l["rule"])
                row["E_adjusted"] = s.adjusted_value(l["key"])
        rows.append(row)
    params = p.data["engine_reference"]["parameters"]
    return {"rows": rows, "resident_days": params["ca_resident_days"], "year_days": params["year_days"],
            "residency": p.data["household"]["residency"], "ratio": p.value("F540NR.34"),
            "ridgeline": {e["field"]: e["value"] for e in p.values_by_doc["D38"]},
            "wage_detail": [
                {"employer": "Corvane Systems", "box1": p.ev_field("D08", "box1")["value"], "box16_CA": p.ev_field("D08", "box16")["value"], "work_location": "California (employment ended 5/16)", "ca_source_correct": p.ev_field("D08", "box16")["value"]},
                {"employer": "Halvorsen Data", "box1": p.ev_field("D09", "box1")["value"], "box16_CA": p.ev_field("D09", "box16")["value"], "work_location": "Sacramento remote 6/2-7/14, Austin from 7/15 (payroll kept CA to 9/30 in error)", "ca_source_correct": p.ev_field("D73", "ytd_ca_wages")["value"]},
            ]}


def basis(s: State):
    p = s.p
    br = p.data["prior_years"]["basis_records"]
    d40 = {e["field"]: e["value"] for e in p.values_by_doc["D40"]}
    d39 = {e["field"]: e["value"] for e in p.values_by_doc["D39"]}
    rows = []
    b = 21300.0
    rows.append({"year": 2022, "begin": None, "income": None, "distributions": None, "end": b, "source": "Client 2022 worksheet (prior preparer file) — unverified", "status": "client"})
    e23 = b + d40["box1"] + d40["box4"] - d40["box16d"]
    rows.append({"year": 2023, "begin": b, "income": d40["box1"] + d40["box4"], "distributions": d40["box16d"], "end": e23, "source": "2023 K-1 (D40, found 6/5/2026) — was a gap", "status": "filled gap"})
    e24 = e23 + 16900 - 30000
    rows.append({"year": 2024, "begin": e23, "income": 16900, "distributions": 30000, "end": e24, "source": "2024 K-1 per prior return; prior preparer 'assumed basis sufficient' (it was: 2,300)", "status": "recomputed"})
    inc25 = d39["box1"] + d39["box4"]
    rows.append({"year": 2025, "begin": e24, "income": inc25, "distributions": d39["box16d"], "end": max(0, e24 + inc25 - d39["box16d"]),
                 "excess": max(0, d39["box16d"] - (e24 + inc25)), "source": "2025 K-1 (D39); Form 7203", "status": "engine agrees" if p.value("F7203.excess") == max(0, d39["box16d"] - (e24 + inc25)) else "differs"})
    return {"scorp": rows, "ridgeline": br["partnership_ridgeline"] + [{"year": 2025, "beginning_capital": 60000, "income": 9870, "distributions": 6000, "foreign_tax": 210, "ending_capital_account": 63660, "outside_basis": None, "source": "D37"}],
            "ira": br["ira_nondeductible_basis_ngozi"] + [{"year": 2025, "contribution": 7000, "converted": 14026, "basis_used": 14000, "basis_end": 0, "taxable": 26, "source": "D41, D42, D43; F8606"}],
            "home": br["home_7709_barton_ridge"] + [{"event": "points on purchase", "amount": 4800, "source": "D54/D55"}]}


def carryovers(s: State):
    p = s.p
    cin = p.data["prior_years"]["carryovers_into_2025"]
    cout = p.versions[p.current_version]["carryovers_out"]
    notes = {
        "sep_contribution_not_deductible_for_2025": "Likely 0 after Schedule C corrections (finding SEP_EXCESS)",
        "minimum_tax_credit_from_2025_amt": "Form 8801 in 2026; recompute if AMT changes",
        "ira_nondeductible_basis_ngozi": "Agreed: both 7,000 contributions converted",
    }
    return {"in": cin, "out": cout, "notes": notes,
            "verified": {k: bool([v for v in s.verifications.values() if v["active"] and v["target"] == f"line:{k}"]) for k in ("SchD.6", "SchD.14", "F8582.1c", "F8606.2")}}


def k1s(s: State):
    p = s.p
    m = []
    for doc, box_map in (("D39", {"box1": "SchE.28A", "box4": "SchB.1.7", "box16d": "F7203.6", "qbi": "F8995.2.2", "or_tax": "ScheduleS.credit"}),
                         ("D37", {"box2": "SchE.28B", "box5": "SchB.1.8", "box9a": "SchD.12", "box21": "Sch3.1", "box19a": None}),
                         ("D38", {"pct_CA": "SchCA540NR.17.E"})):
        for e in p.values_by_doc[doc]:
            if e["field"] in box_map:
                m.append({"doc": doc, "box": e["field"], "label": e["label"], "value": e["value"], "line": box_map[e["field"]], "ev": e["id"],
                          "line_value": p.value(box_map[e["field"]], default=None) if box_map[e["field"]] else None})
    return {"rows": m, "late": [{"doc": "D37", "received": p.documents["D37"]["received_at"], "note": "Ridgeline K-1 arrived 6/22 (after extension); triggered v3"}]}


def prior_year(s: State):
    p = s.p
    py = p.data["prior_years"]
    did_vs_changed = [
        {"topic": "Home office", "prior": "Simplified method 300 sq ft (note: 'client to confirm')", "now": f"Measured 220 sq ft (Sacramento) / 260 (Austin): average 240 — SchC.30 {p.value('SchC.30'):,}", "evidence": "D24"},
        {"topic": "Woodworks S corp basis", "prior": "2023 K-1 missing; 'assumed basis sufficient'", "now": "2023 K-1 (D40) fills the gap; 2025 distributions exceed basis by 21,215 (capital gain)", "evidence": "D40, D39, F7203"},
        {"topic": "IRA basis (8606)", "prior": "7,000 'per client'; 5498 not obtained", "now": "Agreed to 2024 Form 5498 (D42); 2025 conversion taxable 26", "evidence": "D42, D43, D41"},
        {"topic": "SE health insurance", "prior": "0 — Erik on Ngozi's plan", "now": "Engine deducted 14,400; Erik still eligible for employer coverage → disallow", "evidence": "qa-25"},
        {"topic": "Form 3520 (2023 inheritance)", "prior": "Open item — 'discussed?' no resolution", "now": "Still unresolved: identified as an outside filing / penalty exposure for partner decision", "evidence": "D07 p3, D36"},
        {"topic": "Vehicle", "prior": "Standard mileage 7,400 miles x 0.67", "now": "Standard mileage continues (required once chosen with MACRS not used); log has duplicate page", "evidence": "D23"},
        {"topic": "Dependents", "prior": "Theo SSN 666-74-3390", "now": "Organizer typed 666-74-3309 → corrected to the 2024/SS-card number", "evidence": "D06, D71"},
        {"topic": "Residency", "prior": "Full-year California (Form 540)", "now": "Part-year: CA to 7/14, TX from 7/15 (Form 540NR)", "evidence": "household, qa-02"},
    ]
    return {"return": py["return_2024"], "workpaper": py["prior_preparer_workpaper"], "variances": s.variances(), "did_vs_changed": did_vs_changed}


def payments(s: State):
    p = s.p
    tr = p.data["tax_agency_records"]
    return {"federal": {"return": {"withholding": p.value("F1040.25d"), "estimates": p.value("F1040.26"), "estimates_adjusted": s.adjusted_value("F1040.26"),
                                   "extension": p.value("Sch3.10"), "excess_ss": p.value("Sch3.11")},
                        "eftps": [{"field": e["field"], "value": e["value"]} for e in p.values_by_doc["D67"]],
                        "transcripts": tr["irs_account_transcript_2025"]},
            "california": {"return": {"withholding": p.value("F540NR.71"), "estimates": p.value("F540NR.72"), "estimates_adjusted": s.adjusted_value("F540NR.72"), "extension": p.value("F540NR.73")},
                           "webpay": [{"field": e["field"], "value": e["value"]} for e in p.values_by_doc["D68"]], "ftb": tr["ftb_account"]},
            "extension": p.data["what_if"]["extension"], "post_filing_rates": p.data["post_filing_rates"],
            "planning_2026": p.data["planning_reference_2026"]}


def compare(s: State, a: str, b: str):
    p = s.p
    def val(ver, k):
        if ver == "workpaper":
            return s.adjusted_value(k)
        return (p.lines.get(ver, {}).get(k) or {}).get("value")
    keys = set(p.lines.get(a if a != "workpaper" else p.current_version, {})) | set(p.lines.get(b if b != "workpaper" else p.current_version, {}))
    rows = []
    for k in sorted(keys):
        va, vb = val(a, k), val(b, k)
        if va != vb:
            label = (p.line(k) or p.lines[a if a in p.lines else p.current_version].get(k) or p.lines.get(b, {}).get(k) or {}).get("label", k)
            rows.append({"key": k, "label": label, "a": va, "b": vb, "area": area_for_line(k),
                         "delta": (vb - va) if isinstance(va, (int, float)) and isinstance(vb, (int, float)) else None})
    sa = p.versions[a]["summary"] if a in p.versions else s.summary()["approved"]
    sb = p.versions[b]["summary"] if b in p.versions else s.summary()["approved"]
    meta = {v: {"computed_at": p.versions[v]["computed_at"], "trigger": p.versions[v]["trigger"]} for v in p.versions}
    return {"a": a, "b": b, "rows": rows, "summary_a": sa, "summary_b": sb, "meta": meta}


def search(s: State, q: str):
    q = q.strip().lower()
    if len(q) < 2:
        return []
    p = s.p
    out = []
    for l in p.lines[p.current_version].values():
        if q in l["key"].lower() or q in l["label"].lower() or q == str(l["value"]).lower():
            out.append({"type": "line", "id": l["key"], "title": f"{l['key']} — {l['label']}", "sub": str(l["value"])})
    for d in p.data["documents"]:
        if q in d["id"].lower() or q in d["title"].lower() or q in d["issuer"].lower() or any(q in pg["printed_content"].lower() for pg in d["pages"]):
            out.append({"type": "doc", "id": d["id"], "title": f"{d['id']} — {d['title']}", "sub": d["issuer"]})
    for f in s.findings_base:
        if q in f["title"].lower() or q in f["summary"].lower():
            out.append({"type": "finding", "id": f["id"], "title": f["title"], "sub": f["severity"]})
    for n in s.notes.values():
        if q in n["text"].lower():
            out.append({"type": "note", "id": n["id"], "title": n["text"][:90], "sub": n["target"]})
    for qa in p.data["client"]["questionnaire"]:
        if q in qa["question"].lower() or q in qa["answer"].lower():
            out.append({"type": "qa", "id": qa["id"], "title": qa["question"], "sub": qa["answer"]})
    for m in p.data["client"]["messages"]:
        if q in m["text"].lower():
            out.append({"type": "msg", "id": m["id"], "title": m["text"][:90], "sub": m["from"]})
    return out[:80]
