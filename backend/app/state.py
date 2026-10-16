"""Projection: fold the event log over the packet into the workpaper's current state."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from .checks import engine_diagnostics, run_checks
from .packet import AREAS, Packet, area_for_line

STAFF_ROLES = {"preparer", "reviewer", "partner", "firm_administrator", "quality_reviewer"}

DOC_AREA = {
    **{d: "intake_and_engagement" for d in ("D01", "D02", "D03", "D04", "D05", "D06", "D07", "D69", "D70", "D71", "D72")},
    **{d: "wages_and_stock_compensation" for d in ("D08", "D09", "D10", "D11", "D12", "D13", "D73")},
    **{d: "business" for d in ("D14", "D15", "D16", "D17", "D18", "D19", "D20", "D21", "D22", "D23", "D24", "D25", "D26", "D27")},
    **{d: "investments_and_digital_assets" for d in ("D28", "D29", "D30", "D31", "D32", "D33", "D34", "D35", "D36", "D74")},
    **{d: "pass_throughs_and_basis" for d in ("D37", "D38", "D39", "D40")},
    **{d: "deductions_and_credits" for d in ("D41", "D42", "D43", "D44", "D45", "D54", "D55", "D56", "D57", "D58", "D59", "D60", "D61", "D62", "D63", "D64", "D65", "D66")},
    **{d: "rentals_and_sale" for d in ("D46", "D47", "D48", "D49", "D50", "D51", "D52", "D53")},
    **{d: "payments_and_penalties" for d in ("D67", "D68")},
}

# Why a document that is in the file feeds no return line. Every document must land somewhere or say why not.
DOC_DISPOSITION = {
    "D01": "Engagement evidence (required step: engagement letter signed).",
    "D02": "Consent evidence (IRC 7216).",
    "D03": "IP PIN for e-file (identity).",
    "D04": "Identity verification.",
    "D05": "Identity verification.",
    "D06": "Prior-year return: carryovers, variance baseline, dependent SSNs.",
    "D07": "Prior preparer file: open items carried into this year.",
    "D10": "Second image of D09 (same W-2); counted once.",
    "D13": "ESPP purchase data; basis comes from D11 supplement.",
    "D15": "Should land on Schedule C (business use, Spotify, 1099-K match) — not applied by the engine.",
    "D30": "Superseded by the CORRECTED Meridian 1099 (D31).",
    "D47": "Should capitalize the HVAC — not applied by the engine.",
    "D54": "Should reduce home property tax by the seller credit — not applied by the engine.",
    "D69": "Agency record: estimated payments agreed here.",
    "D70": "Resolved 2023 notice; history only.",
    "D71": "Arrived after v3; corrects Theo's SSN (e-file).",
    "D72": "2028 examination letter (post-filing).",
    "D73": "Should source California wages — not applied by the engine.",
}

# Extraction-level findings resolved by the return-level finding they cause.
COVERED_BY = {"EXTRACT_BLANK_AS_ZERO": "RSU_BASIS_ZERO", "DUP_PAGE_D23_3": "MILEAGE_DUP_PAGE",
              "EXTRACT_NOT_PRINTED_ev-1049": "CHARITY_ACK", "EXTRACT_NOT_PRINTED_ev-1045": "PROVIDER_NAME"}

VERIFY_TYPES_DEFAULT = ["agreed_to_source_document", "recalculated", "confirmed_with_client", "agreed_to_prior_year",
                        "agreed_to_third_party_record"]


def short_hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:12]


class State:
    def __init__(self, p: Packet, events: list[dict]):
        self.p = p
        self.events = events
        undone = {e["payload"]["batch"] for e in events if e["type"] == "batch.undo"}
        redone = {e["payload"]["batch"] for e in events if e["type"] == "batch.redo"}
        self.undone_batches = undone - redone
        self.live = [e for e in events if not (e["batch"] and e["batch"] in self.undone_batches) or e["type"] in ("batch.undo", "batch.redo")]
        self.findings_base = run_checks(p)
        self.diagnostics = engine_diagnostics(p)
        self._fold()

    # ------------------------------------------------------------------ folding
    def _fold(self):
        p = self.p
        self.standards = json.loads(json.dumps(p.data["firm"]["starter_standards"]))
        self.budget = dict(p.data["firm"]["budget_hours"])
        self.assignment = dict(p.data["firm"]["assignment_at_start"])
        self.area_assignee: dict[str, str] = {}
        self.adjustments: dict[str, dict] = {}
        self.verifications: dict[str, dict] = {}
        self.notes: dict[str, dict] = {}
        self.questions: dict[str, dict] = {}
        self.signoffs: list[dict] = []
        self.finding_status: dict[str, dict] = {}
        self.time: list[dict] = []
        self.files: list[dict] = []
        self.view_log: list[dict] = []
        self.last_seen: dict[str, int] = {}
        self.filing = {"status": "in_preparation", "history": [], "frozen_at": None, "amendment": 0,
                       "client_approval": None, "efile": [], "extension": None}
        self.links: list[dict] = []
        self.facts: list[dict] = []
        self.whatif_sandbox: dict[str, list] = defaultdict(list)

        for e in self.live:
            t, pl, a = e["type"], e["payload"], e["actor"]
            if t == "adjustment.proposed":
                eff = self.tax_effect(pl.get("category"), pl["delta"])
                self.adjustments[pl["id"]] = {
                    **pl, "proposed_by": a, "ts": e["ts"], "status": "proposed", "approvals": [], "event": e["id"],
                    "area": area_for_line(pl["line"]), "fed_effect": round(eff["fed"], 2), "ca_effect": round(eff["ca"], 2),
                    "fed_balance": round(eff["fed_balance"], 2), "ca_balance": round(eff["ca_balance"], 2),
                    "requires_partner": max(abs(eff["fed"]), abs(eff["ca"]), abs(eff["fed_balance"]), abs(eff["ca_balance"])) > self.partner_threshold(),
                    "amendment": self.filing["amendment"], "batch": e["batch"],
                }
            elif t == "adjustment.approved" and pl["id"] in self.adjustments:
                adj = self.adjustments[pl["id"]]
                adj["approvals"].append({"by": a, "ts": e["ts"], "role": pl.get("role")})
                if not adj["requires_partner"] or pl.get("role") == "partner":
                    adj["status"] = "approved"
            elif t == "adjustment.reversed" and pl["id"] in self.adjustments:
                self.adjustments[pl["id"]].update(status="reversed", reversed_by=a, reversed_at=e["ts"], reverse_reason=pl.get("reason"))
            elif t == "verification.added":
                self.verifications[pl["id"]] = {**pl, "by": a, "ts": e["ts"], "active": True, "batch": e["batch"]}
            elif t == "verification.removed" and pl["id"] in self.verifications:
                self.verifications[pl["id"]]["active"] = False
            elif t == "note.created":
                self.notes[pl["id"]] = {**pl, "by": a, "ts": e["ts"], "status": "open", "replies": [], "history": [{"ts": e["ts"], "by": a, "action": "created"}]}
            elif t == "note.replied" and pl["id"] in self.notes:
                self.notes[pl["id"]]["replies"].append({"by": a, "ts": e["ts"], "text": pl["text"]})
            elif t == "note.resolved" and pl["id"] in self.notes:
                n = self.notes[pl["id"]]
                n.update(status="resolved", resolved_by=a, resolved_at=e["ts"], resolution=pl.get("text"))
                n["history"].append({"ts": e["ts"], "by": a, "action": "resolved"})
            elif t == "note.reopened" and pl["id"] in self.notes:
                self.notes[pl["id"]]["status"] = "open"
                self.notes[pl["id"]]["history"].append({"ts": e["ts"], "by": a, "action": "reopened"})
            elif t == "question.asked":
                self.questions[pl["id"]] = {**pl, "by": a, "ts": e["ts"], "status": "open", "answers": []}
            elif t == "question.answered" and pl["id"] in self.questions:
                q = self.questions[pl["id"]]
                q["answers"].append({"by": a, "ts": e["ts"], "text": pl["text"], "files": pl.get("files", [])})
                q["status"] = "answered"
            elif t == "question.closed" and pl["id"] in self.questions:
                self.questions[pl["id"]]["status"] = "closed"
            elif t == "signoff.signed":
                self.signoffs.append({**pl, "by": a, "ts": e["ts"], "event": e["id"]})
            elif t == "signoff.withdrawn":
                self.signoffs = [s for s in self.signoffs if s["id"] != pl["id"]]
            elif t in ("finding.accepted", "finding.dismissed", "finding.reopened"):
                self.finding_status[pl["id"]] = {"status": {"finding.accepted": "accepted", "finding.dismissed": "dismissed", "finding.reopened": "open"}[t],
                                                 "by": a, "ts": e["ts"], "reason": pl.get("reason"), "authority": pl.get("authority")}
            elif t == "time.logged":
                self.time.append({**pl, "by": a, "ts": e["ts"]})
            elif t == "file.attached":
                self.files.append({**pl, "by": a, "ts": e["ts"]})
            elif t == "fact.corrected":
                self.facts.append({**pl, "by": a, "ts": e["ts"]})
            elif t == "link.added":
                self.links.append({**pl, "by": a, "ts": e["ts"]})
            elif t == "standards.updated":
                self.standards.update(pl.get("standards", {}))
                if "budget_hours" in pl:
                    self.budget.update(pl["budget_hours"])
            elif t == "assignment.set":
                if pl.get("area"):
                    self.area_assignee[pl["area"]] = pl["person"]
                else:
                    self.assignment[pl["role"]] = pl["person"]
            elif t == "view.sensitive":
                self.view_log.append({**pl, "by": a, "ts": e["ts"]})
            elif t == "view.seen":
                self.last_seen[a] = pl["event_id"]
            elif t.startswith("filing."):
                self._fold_filing(e)

    def _fold_filing(self, e):
        t, pl, f = e["type"], e["payload"], self.filing
        f["history"].append({"type": t, "ts": e["ts"], "by": e["actor"], **pl})
        if t == "filing.extension_filed":
            f["extension"] = pl
        elif t == "filing.approval_requested":
            f["status"] = "awaiting_client"
            f["approval_request"] = pl
        elif t == "filing.client_approved":
            f["client_approval"] = {**pl, "by": e["actor"], "ts": e["ts"]}
            f["status"] = "client_approved"
        elif t == "filing.efile_submitted":
            f["status"] = "submitted"
            f["frozen_at"] = f["frozen_at"] or e["ts"]
            f["efile"].append({**pl, "ts": e["ts"], "status": "submitted"})
        elif t == "filing.efile_rejected":
            f["status"] = "rejected"
            f["frozen_at"] = None
            f["efile"].append({**pl, "ts": e["ts"], "status": "rejected"})
        elif t == "filing.efile_accepted":
            f["efile"].append({**pl, "ts": e["ts"], "status": "accepted"})
            f["status"] = "filed"
            f["frozen_at"] = f["frozen_at"] or e["ts"]
        elif t == "filing.amendment_started":
            f["amendment"] += 1
            f["status"] = "amending"
            f["frozen_at"] = None

    # ------------------------------------------------------------------ helpers
    def partner_threshold(self):
        for r in self.standards.get("rules", []):
            if "requires partner sign-off" in r:
                import re
                m = re.search(r"over ([\d,]+)", r)
                if m:
                    return float(m.group(1).replace(",", ""))
        return 1000.0

    def tax_effect(self, category, delta):
        r = self.p.rates
        out = {"fed": 0.0, "ca": 0.0, "fed_balance": 0.0, "ca_balance": 0.0}
        if not category:
            return out
        if category.startswith("whatif:"):
            wid = category.split(":", 1)[1]
            w = next((a for a in self.p.data["what_if"]["alternatives"] if a["id"] == wid), None)
            if w:
                out["fed"] = float(w["federal"]["total_tax_change"])
                out["ca"] = float(w["california"]["total_tax_change"])
            return out
        if category == "payment_fed":
            out["fed_balance"] = -delta
            return out
        if category == "payment_ca":
            out["ca_balance"] = -delta
            return out
        if category == "credit_fed":
            out["fed"] = -delta
            return out
        if category == "schc_expense":
            rr = r["schc_profit"]
            out["fed"], out["ca"] = -delta * rr["federal_per_dollar"], -delta * rr["california_per_dollar"]
            return out
        if category == "credit_ca":
            out["ca"] = -delta
            return out
        if "/" in category:  # federal category / California category (e.g. a sale while a CA resident)
            f_cat, c_cat = category.split("/", 1)
            out["fed"] = delta * r[f_cat]["federal_per_dollar"]
            out["ca"] = delta * r[c_cat]["california_per_dollar"]
            return out
        rr = r.get(category)
        if rr:
            out["fed"], out["ca"] = delta * rr["federal_per_dollar"], delta * rr["california_per_dollar"]
        return out

    def active_adjustments(self, statuses=("approved",)):
        return [a for a in self.adjustments.values() if a["status"] in statuses]

    def adjusted_value(self, key, statuses=("approved",)):
        return self._adjusted(statuses)[0].get(key, self.p.value(key, default=None))

    def stale(self, key, statuses=("approved", "proposed")):
        """True when an input moved but this line's engine rule can't be re-run here (pending engine recompute)."""
        return key in self._adjusted(statuses)[1]

    def _adjusted(self, statuses):
        """Propagate adjustments up the calculation graph. Lines built by plain arithmetic (R-SUM / R-CARRY)
        are recomputed from adjusted inputs with the same formula the engine used; any other rule whose
        inputs moved is marked stale (pending engine recompute) rather than guessed."""
        cache = getattr(self, "_adj_cache", None)
        if cache is None:
            cache = self._adj_cache = {}
        k = tuple(statuses)
        if k in cache:
            return cache[k]
        lines = self.p.lines[self.p.current_version]
        direct = defaultdict(float)
        for a in self.adjustments.values():
            if a["status"] in statuses:
                direct[a["line"]] += a["delta"]
        vals, stale, memo = {}, set(), {}

        def val(key, depth=0):
            if key in memo:
                return memo[key]
            l = lines.get(key)
            if not l:
                memo[key] = (None, False)
                return memo[key]
            base = l["value"]
            changed, v = False, base
            ins = l.get("inputs") or []
            if ins and isinstance(base, (int, float)) and depth < 40:
                sub = [val(i, depth + 1) for i in ins]
                if any(i in stale for i in ins) and key not in direct:
                    stale.add(key)  # built on a number that is itself awaiting the engine
                if any(c for _, c in sub):
                    nums = [x if isinstance(x, (int, float)) else 0 for x, _ in sub]
                    orig = [lines[i]["value"] if i in lines and isinstance(lines[i]["value"], (int, float)) else 0 for i in ins]
                    if l["rule"] in ("R-SUM", "R-CARRY"):
                        # replay the engine's formula: identify it on the original inputs
                        if l["rule"] == "R-CARRY" or abs(sum(orig) - base) <= 1.01:
                            v = sum(nums) if l["rule"] == "R-SUM" else nums[0]
                        elif orig and abs(orig[0] - sum(orig[1:]) - base) <= 1.01:
                            v = nums[0] - sum(nums[1:])
                        elif len(orig) == 2 and abs(orig[1] - orig[0] - base) <= 1.01:
                            v = nums[1] - nums[0]
                        else:
                            v = base + (sum(nums) - sum(orig))
                        changed = True
                    elif key not in direct:  # a preparer-entered adjustment supplies the corrected result
                        stale.add(key)
            if key in direct and isinstance(base, (int, float)):
                v = v + direct[key]
                changed = True
            if changed:
                vals[key] = round(v, 2) if isinstance(v, float) else v
            memo[key] = (v, changed)
            return memo[key]

        for key in lines:
            val(key)
        cache[k] = (vals, stale)
        return cache[k]

    def summary(self):
        v = self.p.versions[self.p.current_version]["summary"]
        out = {"engine": v}
        for label, st in (("approved", ("approved",)), ("with_proposed", ("approved", "proposed"))):
            adjs = self.active_adjustments(st)
            fed_tax = v["federal"]["total_tax"] + sum(a["fed_effect"] for a in adjs)
            ca_tax = v["california"]["total_tax"] + sum(a["ca_effect"] for a in adjs)
            fed_pay = v["federal"]["payments"] - sum(a["fed_balance"] for a in adjs)
            ca_pay = v["california"]["payments"] - sum(a["ca_balance"] for a in adjs)
            out[label] = {
                "federal": {"total_tax": round(fed_tax), "payments": round(fed_pay), "balance_due": round(fed_tax - fed_pay),
                            "change": round(fed_tax - v["federal"]["total_tax"])},
                "california": {"total_tax": round(ca_tax), "payments": round(ca_pay), "balance_due": round(ca_tax - ca_pay),
                               "change": round(ca_tax - v["california"]["total_tax"])},
                "count": len(adjs),
            }
        return out

    # ------------------------------------------------------------------ targets & areas
    def area_of_target(self, target: str) -> str:
        kind, _, ident = target.partition(":")
        if kind == "line":
            return area_for_line(ident)
        if kind == "ev":
            e = self.p.ev(ident)
            if e:
                lines = self.p.ev_landed.get(ident)
                return area_for_line(lines[0]) if lines else DOC_AREA.get(e["document_id"], "intake_and_engagement")
        if kind == "doc":
            return DOC_AREA.get(ident.split("#")[0], "intake_and_engagement")
        if kind == "finding":
            f = next((x for x in self.findings_base if x["id"] == ident), None)
            return f["area"] if f else "return_summary"
        if kind == "area":
            return ident
        return "return_summary"

    def area_content(self, area: str):
        # What a sign-off attests to: the numbers (including pending adjustments), the evidence and the
        # disposition of findings. Approvals and conversation do not change what was signed.
        lines = {k: self.adjusted_value(k, ("approved", "proposed")) for k in self.p.lines[self.p.current_version] if area_for_line(k) == area}
        adjs = sorted([(a["id"], a["delta"]) for a in self.adjustments.values() if a["area"] == area and a["status"] != "reversed"])
        vers = sorted([(v["id"], v["target"]) for v in self.verifications.values() if v["active"] and self.area_of_target(v["target"]) == area])
        fnd = sorted([(f["id"], self.finding_status.get(f["id"], {}).get("status", "open")) for f in self.findings_base if f["area"] == area])
        return {"lines": lines, "adjustments": adjs, "verifications": vers, "findings": fnd}

    def area_hash(self, area):
        return short_hash(self.area_content(area))

    def signoff_status(self):
        out = []
        for s in self.signoffs:
            cur = self.area_hash(s["area"]) if s["area"] != "return" else self.return_hash()
            out.append({**s, "current_hash": cur, "valid": cur == s["hash"]})
        return out

    def return_hash(self):
        return short_hash({a: self.area_hash(a) for a in AREAS} | {"summary": self.summary()["approved"]})

    def prepared_by(self, person, area):
        """Did this person prepare work in the area (sign-off as preparer or propose an adjustment)?"""
        if any(s["by"] == person and s["area"] == area and s["level"] == "preparer" for s in self.signoffs):
            return True
        return any(a["proposed_by"] == person and a["area"] == area for a in self.adjustments.values())

    # ------------------------------------------------------------------ findings
    def findings(self):
        out = []
        for f in self.findings_base + self.diagnostics:
            st = self.finding_status.get(f["id"], {"status": "open"})
            parent = COVERED_BY.get(f["id"])
            if st["status"] == "open" and parent and self.finding_status.get(parent, {}).get("status") in ("accepted", "dismissed"):
                ps = self.finding_status[parent]
                st = {"status": ps["status"], "by": ps["by"], "ts": ps["ts"], "reason": f"Resolved together with {parent}"}
            adjs = [a for a in self.adjustments.values() if a.get("finding") == f["id"] and a["status"] != "reversed"]
            fed = sum(self.tax_effect(x.get("category"), x["delta"])["fed"] + self.tax_effect(x.get("category"), x["delta"])["fed_balance"] for x in f["proposed"])
            ca = sum(self.tax_effect(x.get("category"), x["delta"])["ca"] + self.tax_effect(x.get("category"), x["delta"])["ca_balance"] for x in f["proposed"])
            out.append({**f, "status": st["status"], "status_by": st.get("by"), "status_ts": st.get("ts"),
                        "status_reason": st.get("reason"), "authority": st.get("authority"),
                        "adjustments": [a["id"] for a in adjs], "est_fed": round(fed), "est_ca": round(ca)})
        return out

    # ------------------------------------------------------------------ variance vs prior year
    def variances(self):
        vr = self.standards.get("variance_review", {"flag_if_change_over_percent": 10, "and_over_amount": 1000})
        pct, amt = vr["flag_if_change_over_percent"], vr["and_over_amount"]
        prior = self.p.data["prior_years"]["return_2024"]["lines"]
        labels = self.p.data["prior_years"]["return_2024"]["line_labels"]
        out = []
        for k, pv in prior.items():
            l = self.p.line(k)
            if not isinstance(pv, (int, float)):
                continue
            cur = self.adjusted_value(k) if l else None
            if not isinstance(cur, (int, float)):
                cur_v = 0 if l is None else None
                if cur_v is None:
                    continue
                cur = cur_v
            d = cur - pv
            p_ = (d / abs(pv) * 100) if pv else (100.0 if cur else 0)
            flagged = abs(d) > amt and abs(p_) > pct
            expl = [n for n in self.notes.values() if n["target"] == f"line:{k}" and n.get("kind") == "variance_explanation"]
            out.append({"key": k, "label": (l or {}).get("label") or labels.get(k, k), "prior": pv, "current": cur, "change": d, "pct": round(p_, 1),
                        "flagged": flagged, "explained": bool(expl), "explanation": expl[-1]["text"] if expl else None,
                        "in_2025": l is not None})
        return out

    # ------------------------------------------------------------------ required steps / gates
    def required_steps(self):
        p = self.p
        ver_targets = defaultdict(list)
        for v in self.verifications.values():
            if v["active"]:
                ver_targets[v["target"]].append(v)
        f = self.findings()
        open_findings = [x for x in f if x["status"] == "open" and x["severity"] in ("error", "warning", "review")]
        so = self.signoff_status()
        valid = lambda level: {s["area"] for s in so if s["level"] == level and s["valid"]}
        areas_with_work = [a for a in AREAS if a != "return_summary"]
        var = self.variances()
        dd_notes = [n for n in self.notes.values() if n.get("kind") == "due_diligence"]
        blocking = [n for n in self.notes.values() if n.get("blocking") and n["status"] == "open"]
        approval = self.filing.get("client_approval")
        docs_unaccounted = [d for d in p.documents if not p.landed[p.current_version].get(d) and d not in DOC_DISPOSITION
                            and not any(n["target"] == f"doc:{d}" for n in self.notes.values())]
        steps = [
            ("Engagement letter and consents signed", bool(p.ev_field("D01", "signed_date_taxpayer")) and bool(p.ev_field("D02", "signed_date")), "D01 and D02 signed 2026-01-12"),
            ("Identity verified", all(ver_targets.get(f"doc:{d}") for d in ("D03", "D04", "D05")), "Verify D03 (IP PIN), D04, D05"),
            ("Prior-year return reviewed", bool(ver_targets.get("doc:D06")), "Verify D06 against prior_years"),
            ("All documents accounted for", not docs_unaccounted, f"{len(docs_unaccounted)} documents neither landed nor explained" if docs_unaccounted else "Every document lands or has a reason"),
            ("Prior-year variances explained", all(v["explained"] for v in var if v["flagged"]), f"{sum(1 for v in var if v['flagged'] and not v['explained'])} flagged variances unexplained"),
            ("Carryovers agreed to prior year", all(ver_targets.get(f"line:{k}") for k in ("SchD.6", "SchD.14", "F8582.1c", "F8606.2")), "Verify SchD.6, SchD.14, F8582.1c, F8606.2"),
            ("Estimated payments agreed to IRS and FTB records", all(any(v["vtype"] == "agreed_to_third_party_record" for v in ver_targets.get(f"line:{k}", [])) for k in ("F1040.26", "F540NR.72"))
             and all(x["status"] != "open" for x in f if x["id"] in ("FED_ESTIMATES_VS_IRS", "CA_ESTIMATES_VS_FTB")), "Agree F1040.26 and F540NR.72 to agency records"),
            ("Due diligence completed", any(n["target"] in ("line:F8867.status", "line:F8812.12") for n in dd_notes), "Record CTC/ODC due diligence (Form 8867)"),
            ("Diagnostics resolved", not open_findings, f"{len(open_findings)} findings/diagnostics open"),
            ("Reviewer sign-off", all(a in valid("reviewer") for a in areas_with_work), f"{len([a for a in areas_with_work if a not in valid('reviewer')])} areas without a current reviewer sign-off"),
            ("Partner sign-off", "return" in valid("partner"), "Partner signs the whole return"),
            ("Client approval and e-file authorization", bool(approval) and approval.get("hash") == self.return_hash(), "Client approves the current return (8879)" if not approval else ("Approved" if approval.get("hash") == self.return_hash() else "Return changed after client approval — re-approval needed")),
        ]
        out = [{"step": s, "done": bool(d), "detail": det} for s, d, det in steps]
        out.append({"step": "No open review notes", "done": not blocking, "detail": f"{len(blocking)} blocking notes open"})
        return out

    # ------------------------------------------------------------------ inbox / changes
    def inbox(self, person):
        p = self.p
        role = self.role_of(person)
        items = []
        for q in self.questions.values():
            if q["status"] == "open" and (q["to"] == person or (q["to"] == "client" and role == "client")):
                items.append({"kind": "question", "id": q["id"], "text": q["text"], "ts": q["ts"], "from": q["by"]})
            if q["status"] == "answered" and q["by"] == person:
                items.append({"kind": "answer", "id": q["id"], "text": f"Answered: {q['text'][:80]}", "ts": q["answers"][-1]["ts"]})
        for n in self.notes.values():
            if n["status"] == "open" and n.get("kind") == "review_note" and role in ("preparer", "partner") and n["by"] != person:
                items.append({"kind": "review_note", "id": n["id"], "text": n["text"], "ts": n["ts"], "blocking": n.get("blocking")})
        for s in self.signoff_status():
            if s["by"] == person and not s["valid"]:
                items.append({"kind": "signoff_reopened", "id": s["id"], "text": f"Your {s['level']} sign-off on {AREAS.get(s['area'], s['area'])} reopened: content changed", "ts": s["ts"]})
        if role in ("reviewer", "partner"):
            for a in self.adjustments.values():
                if a["status"] == "proposed" and (role == "partner" or not a["requires_partner"]) and a["proposed_by"] != person:
                    items.append({"kind": "approve_adjustment", "id": a["id"], "text": f"Approve: {a['description']} ({a['line']})", "ts": a["ts"], "requires_partner": a["requires_partner"]})
        if role == "client" and self.filing["status"] == "awaiting_client":
            items.append({"kind": "approve_return", "id": "approval", "text": "Your return is ready for your review and e-file signature", "ts": self.filing["history"][-1]["ts"]})
        for d in p.data["firm"]["deadlines"]:
            items.append({"kind": "deadline", "id": d["what"], "text": d["what"], "ts": d["date"]})
        return sorted(items, key=lambda x: x["ts"], reverse=True)

    def role_of(self, person):
        s = self.p.staff.get(person)
        if s:
            return s["role"]
        if person in self.p.client_users:
            return "client"
        return "unknown"

    def changes_since(self, person):
        last = self.last_seen.get(person, 0)
        evs = [e for e in self.events if e["id"] > last and e["type"] not in ("view.seen", "view.sensitive") and e["actor"] != person]
        return {"since_event": last, "count": len(evs), "events": evs[-200:]}

    def time_vs_budget(self):
        spent = defaultdict(float)
        for t in self.time:
            spent[t["area"]] += float(t["hours"])
        areas = set(self.budget) | set(spent)
        rows = [{"area": a, "budget": self.budget.get(a, 0), "spent": round(spent.get(a, 0), 2)} for a in sorted(areas)]
        return {"rows": rows, "total_budget": sum(self.budget.values()), "total_spent": round(sum(spent.values()), 2)}
