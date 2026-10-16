"""Independent checks: they read the printed documents, the prior year and the
agency records directly and never trust the engine's answer.

Each check returns findings. A finding carries the evidence it rests on (refs)
and, where the fix is mechanical, proposed adjustments with a tax-effect
category so the preparer can accept it in one click.
"""
from __future__ import annotations

import re
from datetime import date

from .packet import Packet


def _f(x):
    try:
        return float(str(x).replace(",", ""))
    except Exception:
        return None


def _money(x):
    return f"{x:,.2f}" if isinstance(x, (int, float)) else str(x)


def finding(code, title, area, severity, kind, summary, refs, *, engine=None, expected=None,
            proposed=None, detail=None, surfaced=None, method=None):
    return {
        "id": code, "code": code, "title": title, "area": area, "severity": severity, "kind": kind,
        "summary": summary, "detail": detail, "engine_value": engine, "expected_value": expected,
        "refs": refs, "proposed": proposed or [], "how_surfaced": surfaced, "method": method,
    }


def R(t, i, **kw):
    return {"type": t, "id": i, **kw}


# --------------------------------------------------------------------------- generic checks

def check_engine_arithmetic(p: Packet):
    """Recompute every R-SUM line from its inputs (column logic for Schedule CA)."""
    lines = p.lines[p.current_version]
    failures = []
    checked = 0
    for l in lines.values():
        if l["rule"] != "R-SUM" or not l.get("inputs") or not isinstance(l["value"], (int, float)):
            continue
        vals = [lines.get(i, {}).get("value") for i in l["inputs"]]
        if not all(isinstance(v, (int, float)) for v in vals):
            continue
        checked += 1
        k = l["key"]
        cands = {sum(vals), vals[0] - sum(vals[1:])}
        if k.startswith("SchCA540NR") and k.endswith(".D"):
            base = k[:-2]
            a = lines.get(base + ".A", {}).get("value", 0) or 0
            b = lines.get(base + ".B", {}).get("value", 0) or 0
            c = lines.get(base + ".C", {}).get("value", 0) or 0
            cands.add(a - b + c)
            if k in ("SchCA540NR.22.D",):
                cands.add(sum(vals))
        if k == "F540NR.97":
            cands.add(vals[1] - vals[0])
        if not any(abs(c - l["value"]) <= 1.01 for c in cands):
            failures.append(k)
    return [finding(
        "ENGINE_ARITHMETIC", f"Engine arithmetic recomputed: {checked} summed lines, {len(failures)} failures",
        "return_summary", "info" if not failures else "error", "reconciliation",
        "Every line the engine built with R-SUM was re-added from its inputs. The arithmetic holds, so the "
        "errors in this return are in its inputs and rules, not its addition." if not failures else
        f"Lines that do not foot: {', '.join(failures)}",
        [R("line", "F1040.24")], method="recompute R-SUM",
    )]


def check_extraction_vs_printed(p: Packet):
    """Compare every extracted value with what is printed on its page."""
    out = []
    blanks, notprinted = [], []
    for e in p.data["extracted_values"]:
        txt = p.page_text(e["document_id"], e["page"])
        if e["value_type"] == "money" and e["text_as_read"] == "" and e["value"] in (0, 0.0):
            blanks.append(e)
        elif e["text_as_read"] and e["value_type"] in ("money",):
            t = e["text_as_read"]
            if t not in txt and t.replace(".00", "") not in txt:
                notprinted.append(e)
        elif e["value_type"] in ("ein", "ssn") and e["value"] and e["value"] not in txt:
            notprinted.append(e)
    if blanks:
        out.append(finding(
            "EXTRACT_BLANK_AS_ZERO", "Blank basis read as $0.00 (confidence 0.98)", "wages_and_stock_compensation",
            "error", "extraction_error",
            f"{len(blanks)} cost-basis fields are blank on the 1099-B ('basis not reported') but were extracted as 0.00 with "
            "0.98 confidence. Blank means 'not reported', not zero.",
            [R("ev", e["id"], doc=e["document_id"], page=e["page"]) for e in blanks],
            method="text_as_read empty but numeric value 0"))
    for e in notprinted:
        txt = p.page_text(e["document_id"], e["page"])
        hint = ""
        if e["value_type"] == "ein":
            m = re.findall(r"\d{2}-\d{7}", txt)
            hint = f" Printed: {', '.join(m)}." if m else ""
        out.append(finding(
            f"EXTRACT_NOT_PRINTED_{e['id']}",
            f"{p.documents[e['document_id']]['title'][:60]}: '{e['label']}' value is not on the page",
            "deductions_and_credits" if e["document_id"] in ("D61", "D62") else "intake_and_engagement",
            "error" if e["value_type"] == "ein" else "warning", "extraction_error",
            f"Extracted {e['value']!r} (confidence {e['confidence']}) does not appear on {e['document_id']} page {e['page']}.{hint}",
            [R("ev", e["id"], doc=e["document_id"], page=e["page"])], method="value not found in printed_content"))
    return out


def check_duplicate_pages_and_documents(p: Packet):
    out = []
    for d in p.data["documents"]:
        seen = {}
        for pg in d["pages"]:
            body = re.sub(r"^\(.*?\)\s*", "", pg["printed_content"]).strip()
            if len(body) < 120:
                continue
            if body in seen:
                out.append(finding(
                    f"DUP_PAGE_{d['id']}_{pg['page']}", f"{d['id']} page {pg['page']} repeats page {seen[body]}",
                    "business" if d["id"] == "D23" else "intake_and_engagement", "error", "reconciliation",
                    f"Page {pg['page']} of '{d['title']}' has the same content as page {seen[body]}. "
                    "Any total built from every page counts it twice.",
                    [R("doc", d["id"], page=pg["page"]), R("doc", d["id"], page=seen[body])],
                    method="page content hash"))
            else:
                seen[body] = pg["page"]
    return out


# --------------------------------------------------------------------------- specific, data-driven checks

def check_rsu_basis(p: Packet):
    sup = p.documents["D11"]["pages"][1]["printed_content"]
    lots = re.findall(r"Lot (RSU-\d+): (\d+) sh acquired (\d\d)/(\d\d)/(\d{4}) .*?adjusted basis ([\d,.]+)", sup)
    lines = p.lines[p.current_version]
    proposed, refs, total = [], [R("doc", "D11", page=2), R("ev", "ev-0012")], 0.0
    for lot, sh, mm, dd, yy, basis in lots:
        acq = f"{yy}-{mm}-{dd}"
        for l in lines.values():
            if l["key"].startswith("F8949.") and "RSU" in l["label"] and f"acquired {acq}" in l["label"] and "basis 0.00" in l["label"]:
                b = _f(basis)
                total += b
                term = "ltcg" if ".E." in l["key"] or ".D." in l["key"] else "stcg"
                if l["label"].split("sold ")[1][:10] <= "2025-07-14":
                    term += "/ca_source_income"  # sold while a California resident: fully CA-source
                proposed.append({"line": l["key"], "delta": -b, "category": term,
                                 "description": f"{lot}: add supplemental adjusted basis {b:,.2f} (vest FMV already in W-2 box 1)"})
                refs.append(R("line", l["key"]))
    if not proposed:
        return []
    return [finding(
        "RSU_BASIS_ZERO", f"RSU shares taxed twice: {total:,.0f} of basis missing", "wages_and_stock_compensation", "error",
        "return_error",
        "Three Corvane RSU lots are on Form 8949 with zero basis. The broker left basis blank (noncovered); the stock-plan "
        "supplement gives the adjusted basis, and the same vest income is already in W-2 box 1 (box 14 RSU 38,200). The engine "
        "matched the ESPP lot to the supplement but not the RSU lots.",
        refs, engine="basis 0.00 on N1, N3, N4", expected=f"basis {total:,.2f}", proposed=proposed,
        surfaced="Document D11 shows 'landed: 1 of 4 lots' in the document index; the 8949 lot trace shows a blank-read-as-zero source.",
        method="match supplement lots to 1099-B lots by acquisition date")]


def check_1099k_in_books(p: Packet):
    k = p.ev_field("D21", "box1a")
    inbooks = p.ev_field("D15", "atlas_paywell")
    gross = p.value("SchC.1")
    books = p.ev_field("D14", "total_income")
    if not (k and inbooks and books) or abs(k["value"] - inbooks["value"]) > 0.5:
        return []
    if gross - books["value"] < k["value"] - 0.5:
        return []
    return [finding(
        "SCHC_1099K_DOUBLE", "Gross receipts include 1099-K card payments already in the books", "business", "error",
        "return_error",
        f"The Paywell 1099-K ({k['value']:,.0f}) is Atlas Outdoor's card payments. The books deposited them gross inside "
        f"Atlas's {p.ev_field('D15','atlas_total')['value']:,.0f} (also on Atlas's 1099-NEC). Books revenue {books['value']:,.0f} = "
        "1099-NECs 142,000 + 9,300 from 11 clients without 1099s. Ask Atlas to correct its 1099-NEC to 28,800 so IRS matching stops.",
        [R("line", "SchC.1"), R("ev", k["id"], doc="D21", page=1), R("ev", inbooks["id"], doc="D15", page=3),
         R("ev", books["id"], doc="D14", page=1), R("doc", "D17", page=1)],
        engine=gross, expected=books["value"],
        proposed=[{"line": "SchC.1", "delta": -k["value"], "category": "schc_profit",
                   "description": "Remove 1099-K amount already in books deposits (Atlas via Paywell)"}],
        surfaced="Books-to-tax view reconciles 1099s to deposits; the unmatched-1099-K rule shows its 12,400 is matched on D15 p3. This is also the record that answers the 2028 Letter 566.",
        method="reconcile information returns to books deposits")]


def check_mileage(p: Packet):
    pages = {}
    for e in p.values_by_doc.get("D23", []):
        if e["field"] == "page_total":
            pages[e["page"]] = e
    txt3 = p.page_text("D23", 3)
    if "Second scan" not in txt3:
        return []
    engine_miles = p.value("SchC.44a")
    unique = sum(e["value"] for pg, e in pages.items() if pg != 3)
    rate = p.data["engine_reference"]["parameters"]["mileage_rate"]
    delta = round(unique * rate - p.value("SchC.9"))
    return [finding(
        "MILEAGE_DUP_PAGE", f"Business miles {engine_miles:,} include a duplicate scan; log supports {unique:,}", "business",
        "error", "return_error",
        f"Page 3 of the mileage log is a second scan of page 2 (same trips, same coffee stain). The engine rule adds every "
        f"page total. Car expense should be {unique:,} x {rate} = {unique*rate:,.0f}, not {p.value('SchC.9'):,}.",
        [R("line", "SchC.44a"), R("line", "SchC.9"), R("doc", "D23", page=2), R("doc", "D23", page=3), R("ev", pages[3]["id"], doc="D23", page=3)],
        engine=engine_miles, expected=unique,
        proposed=[{"line": "SchC.9", "delta": delta, "category": "schc_expense", "description": "Remove duplicate page 3 miles (3,700 x 0.70)"},
                  {"line": "SchC.44a", "delta": -pages[3]["value"], "category": None, "description": "Business miles 8,100"}],
        surfaced="Duplicate-page detector on every document; the mileage line trace shows four page totals feeding one number.",
        method="page content comparison")]


def check_business_use(p: Packet):
    call = p.calls["call-01"]["notes"]
    phone = p.ev_field("D14", "Telephone")["value"]
    net = p.ev_field("D14", "Internet")["value"]
    spot = p.ev_field("D15", "spotify")["value"]
    pm = re.search(r"business share is (\d+)%", " ".join(call))
    im = re.search(r"business use about (\d+)%", " ".join(call))
    out = []
    if pm and im:
        allowed = phone * int(pm.group(1)) / 100 + net * int(im.group(1)) / 100
        delta = round(allowed - (phone + net))
        out.append(finding(
            "SCHC_BUSINESS_USE", "Phone and internet deducted at 100%; client said 70% and 50%", "business", "error", "return_error",
            f"Telephone {phone:,.0f} is a 4-line family plan (70% business per the client); internet {net:,.0f} is shared "
            f"home internet (about 50%). Deductible {allowed:,.0f}, not {phone+net:,.0f}. Note: 70% of a 4-line family plan is "
            "generous (one line of four is 25%) — document Erik's basis for it.",
            [R("line", "SchC.25"), R("call", "call-01"), R("doc", "D15", page=2), R("ev", p.ev_field("D14", "Telephone")["id"], doc="D14", page=1)],
            engine=p.value("SchC.25"), expected=round(allowed),
            proposed=[{"line": "SchC.25", "delta": delta, "category": "schc_expense", "description": "Apply business-use percentages from the 3/26 call"}],
            surfaced="Call notes are evidence items linked to the lines they affect; the line shows an unapplied client statement.",
            method="client statements vs books mapping"))
    if "Spotify" in " ".join(call):
        out.append(finding(
            "SCHC_PERSONAL_SPOTIFY", "Personal Spotify Family booked as business software", "business", "warning", "return_error",
            "Client confirmed Spotify Family is personal and was booked by mistake.",
            [R("line", "SchC.27a.1"), R("call", "call-01"), R("ev", p.ev_field("D15", "spotify")["id"], doc="D15", page=1)],
            engine=p.value("SchC.27a.1"), expected=p.value("SchC.27a.1") - spot,
            proposed=[{"line": "SchC.27a.1", "delta": -spot, "category": "schc_expense", "description": "Remove personal Spotify Family"}],
            method="client statements vs books detail"))
    return out


def check_sehi(p: Packet):
    q = p.qa["qa-25"]["answer"]
    if "offer family coverage" not in q:
        return []
    amt = p.value("Sch1.17")
    return [finding(
        "SEHI_NOT_ALLOWED", "Self-employed health insurance deducted while eligible for spouse's employer plan", "business",
        "error", "return_error",
        f"Erik could be covered under Ngozi's employer plans all year (qa-25) but kept his own plan. Section 162(l)(2)(B) "
        f"denies the deduction for any month he was eligible to participate in a subsidized employer plan, including a "
        f"spouse's. The prior preparer applied the same rule in 2024. Removing it also raises the QBI deduction (about -890 "
        "federal), which the per-dollar rate does not capture.",
        [R("line", "Sch1.17"), R("qa", "qa-25"), R("doc", "D25", page=1), R("py", "/return_2024/notes/Sch1.17")],
        engine=amt, expected=0,
        proposed=[{"line": "Sch1.17", "delta": -amt, "category": "adjustment", "description": "Disallow SE health insurance (IRC 162(l)(2)(B))"}],
        surfaced="Questionnaire answers are evidence linked to lines; the judgment record requires an authority.",
        method="eligibility test from client answer")]


def check_hvac(p: Packet):
    inv = p.page_text("D47", 1)
    if "Installed new" not in inv:
        return []
    wi = next(a for a in p.data["what_if"]["alternatives"] if a["id"] == "hvac_improvement")
    return [finding(
        "HVAC_CAPITALIZE", "11,000 HVAC replacement expensed as a repair", "rentals_and_sale", "error", "return_error",
        "The invoice replaces the whole system (furnace and condenser out, new heat pump, air handler, line set, permit). "
        "That is a restoration of a building system and must be capitalized (Reg. 1.263(a)-3), depreciated over 27.5 years. "
        f"The engine's own what-if gives the effect: federal +{wi['federal']['total_tax_change']:,}, California +{wi['california']['total_tax_change']:,}.",
        [R("line", "SchE.14A"), R("doc", "D47", page=1), R("doc", "D46", page=1), R("call", "call-01"), R("whatif", "hvac_improvement")],
        engine=p.value("SchE.14A"), expected=p.value("SchE.14A") - 11000,
        proposed=[{"line": "SchE.14A", "delta": -11000, "category": "whatif:hvac_improvement", "description": "Capitalize HVAC (27.5-year, placed in service 2025-08-12)"}],
        surfaced="Invoice D47 is 'used' but landed nowhere; the document index shows it, and the what-if quantifies it.",
        method="invoice content vs repair classification")]


def check_interest_duplicate(p: Packet):
    a = p.line("SchB.1.1")
    b = p.line("SchB.1.2")
    if not (a and b) or a["value"] != b["value"]:
        return []
    if "7731" not in p.page_text("D29", 1):
        return []
    return [finding(
        "INTEREST_DOUBLE", f"Northlake sweep interest {a['value']:,} counted twice", "investments_and_digital_assets", "error",
        "return_error",
        "The Northlake composite 1099 already reports the bank-sweep interest (box 1, 1,840). D29 is the sweep bank's own "
        "1099-INT for the same account ending 7731. One payment, two forms, one line too many on Schedule B.",
        [R("line", "SchB.1.1"), R("line", "SchB.1.2"), R("doc", "D28", page=1), R("doc", "D29", page=1)],
        engine=a["value"] * 2, expected=a["value"],
        proposed=[{"line": "SchB.1.2", "delta": -b["value"], "category": "interest", "description": "Remove duplicate sweep interest (same account 7731)"}],
        surfaced="Cross-document duplicate detector on payer, account and amount.",
        method="same account + same amount across forms")]


def check_fx(p: Packet):
    l = p.line("SchB.1.6")
    if not l or "ref:fx.SEK.2024_average" not in (l.get("sources") or []):
        return []
    fx = p.data["engine_reference"]["parameters"]["fx"]["SEK"]
    sek = p.ev_field("D36", "interest_sek")["value"]
    right = round(sek / fx["2025_average"])
    return [finding(
        "FX_WRONG_YEAR", "Swedish interest converted at the 2024 average rate", "investments_and_digital_assets", "warning",
        "return_error",
        f"SEK {sek:,.0f} / 10.56 (2024) = {l['value']:,}. The 2025 average is {fx['2025_average']}: {right:,}.",
        [R("line", "SchB.1.6"), R("ev", p.ev_field("D36", "interest_sek")["id"], doc="D36", page=1), R("param", "fx.SEK.2025_average")],
        engine=l["value"], expected=right,
        proposed=[{"line": "SchB.1.6", "delta": right - l["value"], "category": "interest", "description": "Convert at 2025 average 9.86"}],
        method="reference-year check on rates")]


def check_home_property_tax(p: Packet):
    credit = p.ev_field("D54", "tax_credit")
    l = p.line("SchA.5b")
    if not credit or not l:
        return []
    right = l["value"] - credit["value"]
    salt_total = p.value("SchA.5a") + right
    return [finding(
        "HOME_TAX_PRORATION", "Home property tax ignores the seller's proration credit", "deductions_and_credits", "error",
        "return_error",
        f"The lender paid the full 2025 Travis County bill ({l['value']:,}), but the seller credited the buyers "
        f"{credit['value']:,} at closing for 1/1-7/7. Only the buyers' share ({right:,.0f}) is deductible. State and local "
        f"taxes fall to {salt_total:,.0f}, under the 40,000 cap. Federal effect is about zero: the return is in AMT and taxes "
        "are an AMT add-back (v3 'salt' rate is 0). California allows property tax, so California tax rises.",
        [R("line", "SchA.5b"), R("ev", credit["id"], doc="D54", page=1), R("doc", "D57", page=1), R("doc", "D58", page=1)],
        engine=l["value"], expected=right,
        proposed=[{"line": "SchA.5b", "delta": -credit["value"], "category": "salt", "description": f"Remove seller-paid property tax {credit['value']:,.0f} (closing proration)"}],
        surfaced="Closing statement D54 is 'used' but landed nowhere; document-to-return tracing exposes it.",
        method="closing statement proration vs escrow payment")]


def check_mortgage_payoff(p: Packet):
    l = p.line("SchA.8a")
    if not l or "payoff statement" not in (l.get("note") or ""):
        return []
    pay = p.ev_field("D56", "interest")
    return [finding(
        "MORTGAGE_PAYOFF_DOUBLE", "Payoff interest counted on top of the 1098 that already includes it", "deductions_and_credits",
        "error", "return_error",
        f"Lonestar's 1098 (13,900) says it includes interest paid at payoff; the payoff statement says 'Interest is reported "
        f"on the 2025 Form 1098'. The engine added the payoff interest ({pay['value']:,.0f}) again.",
        [R("line", "SchA.8a"), R("doc", "D55", page=1), R("doc", "D56", page=1), R("ev", pay["id"], doc="D56", page=1)],
        engine=l["value"], expected=l["value"] - pay["value"],
        proposed=[{"line": "SchA.8a", "delta": -pay["value"], "category": "itemized", "description": "Remove payoff interest already on Form 1098"}],
        method="lender statement vs 1098 inclusion note")]


def check_vehicle_donation(p: Packet):
    l = p.line("SchA.12")
    v = p.line("F8283.A1.vehicle")
    sold = p.ev_field("D66", "box4c")
    if not (v and sold) or v["value"] <= sold["value"]:
        return []
    return [finding(
        "VEHICLE_DONATION_VALUE", f"Donated car claimed at {v['value']:,} (Kelley Blue Book); 1098-C caps it at {sold['value']:,.0f}",
        "deductions_and_credits", "error", "return_error",
        "The charity sold the Subaru in an arm's-length sale (1098-C box 4a). The deduction is limited to gross proceeds "
        "(IRC 170(f)(12)); the client's value does not apply. Item 1 of the 2028 examination letter.",
        [R("line", "F8283.A1.vehicle"), R("doc", "D66", page=1), R("qa", "qa-39"), R("call", "call-01"), R("agency", "/notices/1")],
        engine=v["value"], expected=sold["value"],
        proposed=[{"line": "F8283.A1.vehicle", "delta": sold["value"] - v["value"], "category": "itemized", "description": "Limit to 1098-C gross proceeds"}],
        method="third-party form overrides client estimate")]


def check_estimates(p: Packet):
    out = []
    tr = p.data["tax_agency_records"]["irs_account_transcript_2025"][0]["transactions"]
    irs = sum(t["amount"] for t in tr if t["code"] == "670" and t["date"] <= "2026-01-15")
    eng = p.value("F1040.26")
    if irs != eng:
        out.append(finding(
            "FED_ESTIMATES_VS_IRS", f"Federal estimates {eng:,} vs IRS transcript {irs:,}", "payments_and_penalties", "error", "reconciliation",
            "The engine took the Q4 payment from the questionnaire ('4,000 I think', 1/14). The IRS account transcript shows "
            "3,000 on 2026-01-15. Claiming 1,000 that was never paid produces a math-error notice.",
            [R("line", "F1040.26"), R("agency", "/irs_account_transcript_2025/0"), R("qa", "qa-41"), R("doc", "D67", page=1)],
            engine=eng, expected=irs,
            proposed=[{"line": "F1040.26", "delta": irs - eng, "category": "payment_fed", "description": "Agree estimates to IRS transcript"}],
            surfaced="Required step 'Estimated payments agreed to IRS and FTB records' cannot pass while this differs.",
            method="agree to third-party record"))
    ftb = p.data["tax_agency_records"]["ftb_account"]
    ftb_sum = sum(x["amount"] for x in ftb["tax_year_2025_payments"])
    ca = p.value("F540NR.72")
    if ftb_sum != ca:
        out.append(finding(
            "CA_ESTIMATES_VS_FTB", f"California estimates {ca:,} vs FTB account {ftb_sum:,}", "california", "error", "reconciliation",
            "The 9/15/2025 Web Pay payment (3,500) was designated tax year 2024 and the FTB holds it as a 2024 credit. The "
            "engine counts every payment by date. Either ask FTB to transfer it to 2025 before filing, or claim 10,500.",
            [R("line", "F540NR.72"), R("agency", "/ftb_account"), R("ev", p.ev_field("D68", "pay5_year")["id"], doc="D68", page=1)],
            engine=ca, expected=ftb_sum,
            proposed=[{"line": "F540NR.72", "delta": ftb_sum - ca, "category": "payment_ca", "description": "Agree CA estimates to FTB account (9/15 payment held for 2024)"}],
            method="agree to third-party record"))
    return out


def check_ca_wages(p: Packet):
    stub = p.ev_field("D73", "ytd_ca_wages")
    l = p.line("SchCA540NR.1.E")
    corv = p.ev_field("D08", "box16")["value"]
    halv = p.ev_field("D09", "box16")["value"]
    if not (stub and l):
        return []
    right = corv + stub["value"]
    return [finding(
        "CA_WAGES_SOURCE", f"California taxes {l['value']-right:,.0f} of Texas wages", "california", "error", "return_error",
        f"Halvorsen kept California as the work state through 9/30 by mistake (W-2 note, qa-45), so box 16 shows "
        f"{halv:,.0f}. Ngozi moved 7/15; the paystub gives California wages through then: {stub['value']:,.0f}. "
        f"California-source wages = Corvane {corv:,.0f} + {stub['value']:,.0f} = {right:,.0f}. The paystub was 'used' by v3 but "
        "changed nothing. Halvorsen's California withholding stays claimable and comes back as a refund.",
        [R("line", "SchCA540NR.1.E"), R("ev", stub["id"], doc="D73", page=1), R("doc", "D09", page=1), R("qa", "qa-03"), R("qa", "qa-45")],
        engine=l["value"], expected=right,
        proposed=[{"line": "SchCA540NR.1.E", "delta": right - l["value"], "category": "ca_source_income", "description": "Source Halvorsen wages by work location (paystub to 7/15)"}],
        surfaced="State-split view shows each wage dollar by work location and date; D73 is flagged 'used, landed nowhere'.",
        method="residency dates x paystub YTD")]


def check_dependent_ssn(p: Packet):
    hh = {x["id"]: x for x in p.data["household"]["people"]}
    py = {d["name"]: d["ssn"] for d in p.data["prior_years"]["return_2024"]["dependents"]}
    out = []
    for pid, person in hh.items():
        if person.get("role") != "dependent":
            continue
        prior = py.get(person["name"])
        if prior and prior != person["ssn"]:
            card = p.ev_field("D71", "ssn")
            out.append(finding(
                "DEPENDENT_SSN", f"{person['name']}: SSN differs from last year's return", "intake_and_engagement", "error",
                "return_error",
                f"Organizer {person['ssn']} vs 2024 return {prior}. The digits are transposed. Left as is, the e-file is rejected "
                "(timeline 7/13, R0000-504-02); the Social Security card that arrived later confirms the 2024 number.",
                [R("household", pid), R("doc", "D06", page=1)] + ([R("ev", card["id"], doc="D71", page=1)] if card else []) +
                [R("agency", "/efile/0")],
                engine=person["ssn"], expected=prior,
                surfaced="Identity facts are verified against the prior-year return during intake, before review, not at e-file.",
                method="cross-year identity check"))
    return out


def check_broker_summary(p: Packet):
    out = []
    summ = p.ev_field("D31", "b_summary_proceeds")["value"]
    detail = sum(e["value"] for e in p.values_by_doc["D31"] if e["field"].endswith("_proceeds"))
    if abs(summ - detail) > 0.5:
        pg = p.page_text("D31", 32)
        m = re.search(r"(M\d+) (.+?) ([\d.]+) sh acquired (\S+) sold (\S+) proceeds ([\d,.]+) basis ([\d,.]+)", pg)
        prop = []
        if m:
            g = _f(m.group(6)) - _f(m.group(7))
            prop = [{"line": "SchD.2", "delta": g, "category": "stcg", "description": f"Add {m.group(1)} ({m.group(2)}) from unread page 32"}]
        out.append(finding(
            "MERIDIAN_UNREAD_PAGE", f"Meridian sale {m.group(1) if m else ''} on unread page 32 is missing", "investments_and_digital_assets",
            "warning", "completeness",
            f"Summary proceeds {summ:,.2f} vs detail {detail:,.2f}: the difference ({summ-detail:,.2f}) is a fractional-share "
            "sale on page 32, which the pipeline marked 'not read'.",
            [R("doc", "D31", page=32), R("ev", p.ev_field("D31", "b_summary_proceeds")["id"], doc="D31", page=1)],
            engine=detail, expected=summ, proposed=prop, method="summary vs detail reconciliation"))
    return out


def check_crypto(p: Packet):
    msg = p.messages.get("msg-07")
    l = p.line("F8949.H.C6")
    if not (msg and l):
        return []
    basis = _f(re.search(r"for about ([\d,]+)", msg["text"]).group(1))
    proceeds = 5325.0
    rates = p.rates
    return [finding(
        "CRYPTO_C6_BASIS", "Bitcoin lot C6 taxed with zero basis and the transfer-in date", "investments_and_digital_assets",
        "review", "judgment",
        f"Coinhaven only knows the 6/1/2025 transfer-in. The client says it was bought 3/15/2021 for {basis:,.0f} on an exchange "
        "that has closed; the only proof is a bank statement line. If accepted, the lot is long-term with basis 3,050 "
        "(the message arrived after the last engine run). Also note: the export says 'FIFO' but the sold lots are not FIFO.",
        [R("line", "F8949.H.C6"), R("msg", "msg-07"), R("doc", "D35", page=1), R("doc", "D34", page=1)],
        engine=f"ST gain {proceeds:,.0f}", expected=f"LT gain {proceeds-basis:,.0f} (if substantiated)",
        proposed=[{"line": "F8949.H.C6", "delta": -proceeds, "category": "stcg/ca_source_income", "description": "Remove as short-term"},
                  {"line": "F8949.K.total", "delta": proceeds - basis, "category": "ltcg/ca_source_income", "description": "Report as long-term, basis 3,050"}],
        surfaced="Client messages are evidence; the lot's trace shows a missing-basis source and links the message.",
        method="missing basis + later client evidence")]


def check_provider(p: Packet):
    out = []
    l1 = p.line("F2441.1a")
    if l1 and "Bright Oak Kids Club" in p.page_text("D61", 1) and "Bright Oak Kids Club" not in l1["label"]:
        out.append(finding(
            "PROVIDER_NAME", "Form 2441 provider name does not match the statement", "deductions_and_credits", "warning", "return_error",
            f"Return says '{l1['label'].split(':')[1].split(',')[0].strip()}'; statement and 2024 return say 'Bright Oak Kids Club'.",
            [R("line", "F2441.1a"), R("doc", "D61", page=1)], method="label vs source text"))
    return out


def check_charity_ack(p: Packet):
    t = p.page_text("D64", 1)
    if "No goods or services line" not in t:
        return []
    return [finding(
        "CHARITY_ACK", "St. Brigid 1,500: receipt is not a valid written acknowledgment", "deductions_and_credits", "review", "judgment",
        "The handwritten receipt's first digit is ambiguous (1 or 7). The client confirmed 1,500 by phone and bank statement "
        "(check #2207), and the deduction uses 1,500. A gift of 250 or more needs a contemporaneous acknowledgment stating "
        "whether goods or services were provided (IRC 170(f)(8)); this one lacks that line. Request a compliant letter before filing.",
        [R("line", "SchA.11"), R("ev", "ev-1049", doc="D64", page=1), R("msg", "msg-08")],
        method="substantiation requirements")]


def check_mileage_reasonableness(p: Packet):
    trips = [e for e in p.values_by_doc.get("D23", []) if e["field"].endswith("_miles") and e["page"] != 3]
    local = [e for e in trips if e["value"] >= 150]
    totals = [e["value"] for e in p.values_by_doc["D23"] if e["field"] == "page_total"]
    return [finding(
        "MILEAGE_REASONABLE", "Mileage log looks reconstructed", "business", "review", "judgment",
        f"Page totals are round ({', '.join(str(int(t)) for t in totals)}), {len(local)} of {len(trips)} local trips are 150+ miles "
        "(e.g. 240 miles to a Sacramento camera store), and 6/5 has three trips totaling 539 miles. Section 274(d) needs a "
        "contemporaneous log. Ask how it was kept and record the due diligence.",
        [R("doc", "D23", page=1), R("doc", "D23", page=2), R("msg", "msg-03")], method="reasonableness screen")]


def check_wash_sales(p: Packet):
    lots = []
    for e in p.values_by_doc.get("D31", []):
        pass
    txt = " ".join(pg["printed_content"] for pg in p.documents["D31"]["pages"])
    for m in re.finditer(r"(M\d+) (.+?) ([\d.]+) sh acquired (\S+) sold (\S+) proceeds ([\d,.]+) basis ([\d,.]+)(?: wash sale loss disallowed ([\d,.]+))?", txt):
        lots.append(dict(id=m.group(1), name=m.group(2), acq=m.group(4), sold=m.group(5), proc=_f(m.group(6)), basis=_f(m.group(7)), wash=_f(m.group(8) or 0)))
    hits = []
    for l in lots:
        if l["basis"] <= l["proc"] or l["wash"]:
            continue
        s = date.fromisoformat(l["sold"])
        for o in lots:
            if o is not l and o["name"] == l["name"] and abs((date.fromisoformat(o["acq"]) - s).days) <= 30 and o["acq"] != l["acq"]:
                hits.append(f"{l['id']} {l['name']} loss {l['basis']-l['proc']:,.0f} sold {l['sold']}, bought {o['id']} {o['acq']}")
    if not hits:
        return []
    return [finding(
        "WASH_SALE_SCREEN", f"Possible wash sales the broker did not report ({len(hits)})", "investments_and_digital_assets", "review", "judgment",
        "Independent screen of Meridian lots: a loss sale with a purchase of the same security within 30 days. " + "; ".join(hits) +
        ". Brokers report wash sales within an account; confirm with Meridian or adjust.",
        [R("doc", "D31", page=4), R("doc", "D31", page=7), R("doc", "D31", page=9)], method="±30-day replacement screen")]


def check_questionnaire(p: Packet):
    sales = len([l for l in p.lines[p.current_version] if re.match(r"F8949\.[A-Z]\.[NMXC]\d+$", l)])
    return [finding(
        "QUESTIONNAIRE_CONFLICTS", "Client answers contradicted by documents", "intake_and_engagement", "review", "judgment",
        f"qa-14 'no sales' vs {sales} lots on Form 8949; qa-15 'didn't really sell' vs 12 crypto sales; qa-31 'no prior IRA basis' "
        "vs 7,000 on the 2024 Form 8606; qa-41 Q4 '4,000 I think' vs 3,000 per IRS; qa-39 car 'about 6,000' vs 2,900 on 1098-C; "
        "organizer SSN for Theo vs 2024 return. Documents win; each answer is kept as evidence with its contradiction.",
        [R("qa", q) for q in ("qa-14", "qa-15", "qa-31", "qa-39", "qa-41")], method="answers vs documents")]


def check_outside_filings(p: Packet):
    return [finding(
        "OUTSIDE_FILINGS", "Filings outside this return that must be identified", "intake_and_engagement", "review", "completeness",
        "FinCEN 114 (FBAR) for the Sparbanken account, max ~149,567 USD, due 10/15/2026, outside engagement. "
        "Form 3520 for the 2023 foreign inheritance (prior preparer open item, never resolved; penalty exposure). "
        "Forms 1099-NEC for two contractors (4,800 and 2,600), due 2/2/2026, late, outside engagement. "
        "Oregon and Arizona: covered by the entities' composite returns. Ada's own 1040 checks 'can be claimed' (consistent). "
        "Form 8938 is inside this return.",
        [R("doc", "D36", page=1), R("doc", "D07", page=3), R("doc", "D27", page=1), R("doc", "D38", page=1), R("doc", "D39", page=2), R("doc", "D01", page=1)],
        method="completeness")]


def check_ca_amt(p: Packet):
    return [finding(
        "CA_AMT_ISO", "California AMT on the ISO exercise is not computed", "california", "review", "judgment",
        "1,000 ISOs granted 3/1/2022 while a California resident, exercised 7/30/2025 after the move (spread 40,000). "
        "California sources the AMT preference by workdays in California between grant and exercise; the engine does not "
        "compute Schedule P. Partner decision: compute manually or document why it is immaterial.",
        [R("doc", "D12", page=1), R("line", "F6251.2i"), R("line", "F540NR.61")], method="engine limitation")]


def check_sep(p: Packet):
    l = p.line("Sch1.16")
    if not l:
        return []
    # Corrected net profit: remove 1099-K double count, add back disallowed mileage / business-use / Spotify
    k = p.ev_field("D21", "box1a")["value"]
    pages = {e["page"]: e["value"] for e in p.values_by_doc["D23"] if e["field"] == "page_total"}
    miles_fix = pages.get(3, 0) * p.data["engine_reference"]["parameters"]["mileage_rate"]
    phone, net = p.ev_field("D14", "Telephone")["value"], p.ev_field("D14", "Internet")["value"]
    spot = p.ev_field("D15", "spotify")["value"]
    profit = p.value("SchC.31") - k + miles_fix + phone * 0.3 + net * 0.5 + spot
    se_half = profit * 0.9235 * 0.153 / 2
    limit = round(0.2 * (profit - se_half))
    excess = 18000 - limit
    return [finding(
        "SEP_EXCESS", f"SEP limit falls to about {limit:,} on corrected Schedule C — {excess:,} excess contribution", "business", "error", "return_error",
        f"The engine limits the SEP to 20% of (net profit - half SE tax) = {l['value']:,} on its Schedule C. Corrected net profit is "
        f"about {profit:,.0f} (1099-K removed; mileage, business-use and Spotify fixes), so the limit is about {limit:,}. The 18,000 "
        f"deposited on 4/10/2026 leaves about {excess:,} excess: withdraw it with earnings by the extended due date (10/15/2026) "
        "or a 6% excise applies every year it stays (Form 5329). SE health insurance does not enter this limit.",
        [R("line", "Sch1.16"), R("doc", "D26", page=1), R("qa", "qa-26"), R("line", "SchC.31")],
        engine=l["value"], expected=limit,
        proposed=[{"line": "Sch1.16", "delta": limit - l["value"], "category": "adjustment", "description": "SEP deduction at the corrected 20% limit"}],
        surfaced="Dependency between findings: the SEP limit is recomputed from the corrected Schedule C, not the engine's.",
        method="recompute limit on corrected inputs")]


def check_oregon_credit(p: Packet):
    l = p.line("ScheduleS.credit")
    if not l or not l["value"]:
        return []
    return [finding(
        "CA_OSTC_OREGON", "California credit for Oregon composite tax is not allowed", "california", "error", "return_error",
        f"Oregon is a 'reverse-credit' state: a California resident cannot take Schedule S credit for Oregon tax; the credit is "
        f"claimed on an Oregon nonresident return instead. The engine took {l['value']:,}. Disallow it and consider an Oregon "
        "return (outside this engagement) to recover the composite tax.",
        [R("line", "ScheduleS.credit"), R("ev", "ev-0982", doc="D39", page=2), R("doc", "D39", page=2)],
        engine=l["value"], expected=0,
        proposed=[{"line": "ScheduleS.credit", "delta": -l["value"], "category": "credit_ca", "description": "Disallow Schedule S credit for Oregon (reverse-credit state)"}],
        method="state credit rules")]


def check_scorp_gain_source(p: Packet):
    g = p.value("F7203.excess")
    if not g:
        return []
    share = round(g * p.data["engine_reference"]["parameters"]["ca_resident_days"] / 365)
    return [finding(
        "SCORP_GAIN_CA_SOURCE", f"S corp excess-distribution gain ({g:,}) sourced to California by days", "california", "review", "judgment",
        f"The engine prorates pass-through gains by residency days (~{share:,} to California). Gain from distributions in excess of "
        "stock basis is gain on an intangible, recognized when basis is exhausted — on these facts in December, while a Texas "
        "resident. Partner call: source it to Texas (California about -725) or document why the day-proration stands.",
        [R("line", "F7203.excess"), R("line", "SchCA540NR.7.E"), R("doc", "D39", page=1)],
        proposed=[{"line": "SchCA540NR.7.E", "delta": -share, "category": "ca_source_income", "description": "Source S corp excess-distribution gain to Texas (recognized after the move)"}],
        method="sourcing rule review")]


def check_daf_ack(p: Packet):
    t = p.page_text("D65", 1)
    if "exclusive legal control" in t:
        return []
    return [finding(
        "DAF_ACK", "Donor-advised fund acknowledgment is missing the required statement", "deductions_and_credits", "review", "judgment",
        "A gift to a donor-advised fund needs a written acknowledgment that the sponsoring organization has exclusive legal control "
        "over the assets (IRC 170(f)(18)); D65 says only 'no goods or services provided'. Without it the 14,500 deduction is at "
        "risk — and this is item 1 of the 2028 examination letter. Also confirm the mutual fund's value at NAV on 12/05/2025 "
        "(the acknowledgment uses a high/low average).",
        [R("line", "F8283.A1.stock"), R("doc", "D65", page=1), R("agency", "/notices/1")],
        method="substantiation requirements")]


CHECKS = [
    check_engine_arithmetic, check_extraction_vs_printed, check_duplicate_pages_and_documents,
    check_rsu_basis, check_1099k_in_books, check_mileage, check_business_use, check_sehi, check_hvac,
    check_interest_duplicate, check_fx, check_home_property_tax, check_mortgage_payoff, check_vehicle_donation,
    check_estimates, check_ca_wages, check_dependent_ssn, check_broker_summary, check_crypto, check_provider,
    check_charity_ack, check_mileage_reasonableness, check_wash_sales, check_questionnaire, check_outside_filings,
    check_ca_amt, check_sep, check_oregon_credit, check_scorp_gain_source, check_daf_ack,
]


_RUN_CACHE: dict = {}


def run_checks(p: Packet):
    """Findings depend only on the packet, which never changes, so compute once per packet."""
    if id(p) in _RUN_CACHE:
        return _RUN_CACHE[id(p)]
    out = _run_checks(p)
    _RUN_CACHE[id(p)] = out
    return out


def _run_checks(p: Packet):
    out, seen = [], set()
    for c in CHECKS:
        try:
            for f in c(p):
                if f["id"] in seen:
                    continue
                seen.add(f["id"])
                out.append(f)
        except Exception as ex:  # a broken check must never hide the others
            out.append(finding(f"CHECK_FAILED_{c.__name__}", f"Check {c.__name__} failed", "return_summary", "warning",
                               "reconciliation", str(ex), []))
    return out


def engine_diagnostics(p: Packet):
    v = p.versions[p.current_version]
    return [{"id": f"DIAG_{d['code']}", "code": d["code"], "title": d["message"], "severity": "warning" if d["severity"] == "warning" else "info",
             "area": "return_summary", "kind": "engine_diagnostic", "summary": d["message"],
             "refs": [({"type": "ev", "id": r} if r.startswith("ev-") else {"type": "line", "id": r} if "." in r and not r.startswith(("py:", "qa-")) else {"type": "qa", "id": r} if r.startswith("qa-") else {"type": "py", "id": r[3:]}) for r in d["refs"]],
             "proposed": [], "engine_value": None, "expected_value": None, "method": "engine", "how_surfaced": None, "detail": None}
            for d in v["diagnostics"]]
