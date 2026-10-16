"""Read-only access to the pipeline packet.

The packet is loaded exactly as delivered and never mutated. Everything the
workpaper adds (adjustments, verifications, notes, sign-offs...) lives in the
event log and is layered on top of these indexes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from functools import cached_property
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "okafor_lindqvist_2025_packet.json"

# Work areas mirror the firm's budget areas so time, sign-offs and review all share one vocabulary.
AREAS = {
    "intake_and_engagement": "Intake & engagement",
    "wages_and_stock_compensation": "Wages & stock compensation",
    "investments_and_digital_assets": "Investments & digital assets",
    "business": "Business (Schedule C)",
    "rentals_and_sale": "Rentals & sale",
    "pass_throughs_and_basis": "Pass-throughs & basis",
    "deductions_and_credits": "Deductions & credits",
    "payments_and_penalties": "Payments & penalties",
    "california": "California",
    "return_summary": "Return summary",
}

_AREA_RULES = [
    (r"^F8949\.[A-Z]\.N[1-4]$", "wages_and_stock_compensation"),
    (r"^(F1040\.1|F8959|F6251|Sch2\.[123]$|F1040\.17$|Sch3\.11$)", "wages_and_stock_compensation"),
    (r"^(SchB|F1040\.2b|F1040\.3|SchD|F8949|F8938|F8960|Sch3\.1$|Sch2\.12$)", "investments_and_digital_assets"),
    (r"^(SchC|SchSE|F4562-C|Sch1\.(3|15|16|17)$|F8995|Sch2\.4$)", "business"),
    (r"^(SchE\.(1|2|3|9|11|12|14|16|18|19|20|21|22|26)[AB]?|SchE\.26|F4562-E|F4797|F8582)", "rentals_and_sale"),
    (r"^(SchE\.(28|32|41)|F7203|Sch1\.5$)", "pass_throughs_and_basis"),
    (r"^(SchA|F8283|F8812|F8863|F2441|F8889|F8606|F1040\.4|F1040\.1[2-5]|F1040\.19|F1040\.20|Sch3\.8|F8867|Sch1\.13)", "deductions_and_credits"),
    (r"^(F1040\.2[5-9]|F1040\.3[0-8]|Sch3\.1[05]|F2210)", "payments_and_penalties"),
    (r"^(SchCA540NR|F540NR|FTB|ScheduleS)", "california"),
]

FORM_NAMES = {
    "F1040": "Form 1040", "Sch1": "Schedule 1", "Sch2": "Schedule 2", "Sch3": "Schedule 3",
    "SchA": "Schedule A", "SchB": "Schedule B", "SchC": "Schedule C", "SchD": "Schedule D",
    "SchE": "Schedule E", "SchSE": "Schedule SE", "F8949": "Form 8949", "F4797": "Form 4797",
    "F4562-C": "Form 4562 (Schedule C)", "F4562-E": "Form 4562 (rentals)", "F8582": "Form 8582",
    "F6251": "Form 6251 (AMT)", "F8959": "Form 8959", "F8960": "Form 8960 (NIIT)", "F8995": "Form 8995-A (QBI)",
    "F8812": "Schedule 8812", "F8863": "Form 8863", "F2441": "Form 2441", "F8889": "Form 8889 (HSA)",
    "F8606": "Form 8606", "F8283": "Form 8283", "F7203": "Form 7203", "F8938": "Form 8938",
    "F2210": "Form 2210", "F8867": "Form 8867", "SchCA540NR": "Schedule CA (540NR)", "F540NR": "Form 540NR",
    "ScheduleS": "Schedule S", "FTB3885A": "FTB 3885A", "FTB5805": "FTB 5805",
}


def area_for_line(key: str) -> str:
    for pat, area in _AREA_RULES:
        if re.match(pat, key):
            return area
    return "return_summary"


class Packet:
    def __init__(self, path: str | os.PathLike | None = None):
        self.path = Path(path or os.environ.get("PACKET_PATH", DEFAULT_PATH))
        raw = self.path.read_bytes()
        self.sha256 = hashlib.sha256(raw).hexdigest()
        self.data = json.loads(raw)
        d = self.data
        self.documents = {x["id"]: x for x in d["documents"]}
        self.values = {e["id"]: e for e in d["extracted_values"]}
        self.values_by_doc: dict[str, list] = {}
        for e in d["extracted_values"]:
            self.values_by_doc.setdefault(e["document_id"], []).append(e)
        self.versions = {v["version"]: v for v in d["return_versions"]}
        self.current_version = d["return_versions"][-1]["version"]
        self.lines = {v["version"]: {l["key"]: l for l in v["lines"]} for v in d["return_versions"]}
        self.qa = {q["id"]: q for q in d["client"]["questionnaire"]}
        self.messages = {m["id"]: m for m in d["client"]["messages"]}
        self.calls = {c["id"]: c for c in d["client"]["call_notes"]}
        self.staff = {s["id"]: s for s in d["firm"]["staff"]}
        self.client_users = {c["id"]: c for c in d["firm"]["client_users"]}
        self.rates = d["return_versions"][-1]["tax_effect_rates"]

    # ------------------------------------------------------------------ lookups
    def line(self, key: str, version: str | None = None):
        return self.lines[version or self.current_version].get(key)

    def value(self, key: str, version: str | None = None, default=0):
        l = self.line(key, version)
        return l["value"] if l else default

    def ev(self, ev_id: str):
        return self.values.get(ev_id)

    def ev_field(self, doc_id: str, field: str):
        for e in self.values_by_doc.get(doc_id, []):
            if e["field"] == field:
                return e
        return None

    def page_text(self, doc_id: str, page: int) -> str:
        for p in self.documents[doc_id]["pages"]:
            if p["page"] == page:
                return p["printed_content"]
        return ""

    def people(self):
        """Everyone who can be 'switched to' in the app: staff + client users."""
        out = []
        for s in self.data["firm"]["staff"]:
            out.append({**s, "kind": "staff"})
        for c in self.data["firm"]["client_users"]:
            out.append({**c, "kind": "client", "sensitive_data_clearance": False, "credential": None})
        return out

    @cached_property
    def landed(self) -> dict[str, dict[str, list[str]]]:
        """version -> document id -> line keys that cite one of its values."""
        out = {}
        for ver, lines in self.lines.items():
            m: dict[str, list[str]] = {}
            for l in lines.values():
                for s in l.get("sources") or []:
                    e = self.values.get(s)
                    if e:
                        m.setdefault(e["document_id"], [])
                        if l["key"] not in m[e["document_id"]]:
                            m[e["document_id"]].append(l["key"])
            out[ver] = m
        return out

    @cached_property
    def ev_landed(self) -> dict[str, list[str]]:
        m: dict[str, list[str]] = {}
        for l in self.lines[self.current_version].values():
            for s in l.get("sources") or []:
                m.setdefault(s, []).append(l["key"])
        return m

    @cached_property
    def dependents_of(self) -> dict[str, list[str]]:
        """Reverse of inputs: which lines consume a given line."""
        m: dict[str, list[str]] = {}
        for l in self.lines[self.current_version].values():
            for i in l.get("inputs") or []:
                m.setdefault(i, []).append(l["key"])
        return m


_packet: Packet | None = None


def get_packet() -> Packet:
    global _packet
    if _packet is None:
        _packet = Packet()
    return _packet
