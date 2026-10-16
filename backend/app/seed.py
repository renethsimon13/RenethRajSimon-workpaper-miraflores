"""Demo season: replays a plausible March-June 2026 of work by the engagement team so a
reviewer can open the link and see a workpaper mid-flight (approved fixes, a reopened
sign-off, blocking review notes, client questions). Reset returns to the bare packet."""
from __future__ import annotations

from . import store

PRI, DAN, HEL, MAR, JO = "st-01", "st-02", "st-03", "st-04", "st-05"
REASONS = {
    "SCHC_1099K_DOUBLE": "Paywell 1099-K is Atlas's card payments, already deposited gross in books and on Atlas's 1099-NEC (D15 p3).",
    "MILEAGE_DUP_PAGE": "D23 page 3 is a second scan of page 2; business miles are 8,100.",
    "INTEREST_DOUBLE": "D29 is the sweep bank's 1099-INT for the same account 7731 already on the Northlake composite.",
    "FX_WRONG_YEAR": "2025 interest converts at the 2025 average rate (9.86).",
    "MORTGAGE_PAYOFF_DOUBLE": "Payoff statement says the interest is on the 1098.",
    "HOME_TAX_PRORATION": "Seller credited 6,912 for 1/1-7/7 at closing (D54); buyers deduct their share only.",
    "RSU_BASIS_ZERO": "Supplemental statement D11 gives adjusted basis; vest income already in W-2 box 1.",
    "FED_ESTIMATES_VS_IRS": "IRS transcript: Q4 paid 1/15/2026, 3,000 (client recalled 4,000).",
    "SEHI_NOT_ALLOWED": "Eligible for subsidized coverage through spouse's employers all year (qa-25); IRC 162(l)(2)(B).",
    "VEHICLE_DONATION_VALUE": "1098-C box 4c gross proceeds 2,900 caps the deduction (IRC 170(f)(12)).",
    "SCHC_BUSINESS_USE": "Client call 3/26: phone 70% business, internet 50%.",
    "SCHC_PERSONAL_SPOTIFY": "Client call 3/26: Spotify Family is personal.",
    "CA_WAGES_SOURCE": "Paystub D73: CA wages 22,469 to 7/15; Halvorsen payroll kept CA to 9/30 in error.",
    "HVAC_CAPITALIZE": "Full system replacement with permit — restoration of a building system, Reg. 1.263(a)-3(k).",
    "MERIDIAN_UNREAD_PAGE": "Lot M18 on D31 page 32 (not read by the pipeline); summary agrees after adding it.",
}


def seed(P, state):
    findings = {f["id"]: f for f in state().findings_base}

    def ev(actor, t, payload, ts, batch=None, entity=None):
        return store.append(actor, t, payload, entity, batch, ts=ts)

    def accept(fid, actor, ts):
        f = findings[fid]
        b = store.new_id("batch")
        ev(actor, "finding.accepted", {"id": fid, "reason": REASONS[fid]}, ts, b, f"finding:{fid}")
        ids = []
        for i, x in enumerate(f["proposed"]):
            aid = f"adj-{fid.lower()[:18]}-{i}"
            ids.append(aid)
            ev(actor, "adjustment.proposed", {"id": aid, "line": x["line"], "delta": x["delta"], "category": x["category"],
                                              "description": x["description"], "reason": REASONS[fid], "finding": fid,
                                              "evidence": [r for r in f["refs"]][:4]}, ts, b, f"line:{x['line']}")
        return ids

    def verify(actor, target, vtype, note, ts, batch=None):
        ev(actor, "verification.added", {"id": store.new_id("veri"), "target": target, "vtype": vtype, "note": note}, ts, batch, target)

    def time(actor, area, hours, ts, note=""):
        ev(actor, "time.logged", {"id": store.new_id("time"), "area": area, "hours": hours, "note": note}, ts)

    def note(actor, kind, target, text, ts, blocking=False, authority=None, nid=None):
        nid = nid or store.new_id("note")
        ev(actor, "note.created", {"id": nid, "kind": kind, "target": target, "text": text, "blocking": blocking, "authority": authority}, ts, None, target)
        return nid

    # ---- March: preparer starts
    time(PRI, "intake_and_engagement", 1.2, "2026-03-09T16:10:00Z", "Engagement, identity, prior-year review")
    b = store.new_id("batch")
    for d, t in (("D03", "IP PIN notice matches organizer (Ngozi)"), ("D04", "Texas DL; DOB agrees to organizer"), ("D05", "Texas DL; DOB agrees to organizer")):
        verify(PRI, f"doc:{d}", "agreed_to_source_document", t, "2026-03-09T16:20:00Z", b)
    verify(PRI, "doc:D06", "agreed_to_prior_year", "2024 return agrees to prior_years data; dependents and carryovers noted", "2026-03-09T16:40:00Z")
    note(PRI, "preparer_note", "doc:D07", "Prior preparer open items: 2023 Woodworks K-1 (requested), 2024 5498 (D42 in file — agrees), home office sq ft (D24: 220/260), Form 3520 for 2023 (raise with partner).", "2026-03-09T16:55:00Z")
    accept("FED_ESTIMATES_VS_IRS", PRI, "2026-03-12T16:30:00Z")
    verify(PRI, "line:F1040.26", "agreed_to_third_party_record", "Agreed to IRS account transcript (as of 3/12): 4 x 3,000", "2026-03-12T16:35:00Z")
    verify(PRI, "line:SchD.6", "agreed_to_prior_year", "2024 Sch D: ST carryover 3,200", "2026-03-12T17:00:00Z")
    verify(PRI, "line:SchD.14", "agreed_to_prior_year", "2024 Sch D: LT carryover 11,000", "2026-03-12T17:01:00Z")
    verify(PRI, "line:F8582.1c", "agreed_to_prior_year", "2024 F8582 unallowed 6,300 + 9,850", "2026-03-12T17:02:00Z")
    verify(PRI, "line:F8606.2", "agreed_to_third_party_record", "2024 Form 5498 (D42): 7,000 contributed 2/12/2025 for 2024", "2026-03-12T17:03:00Z")
    time(PRI, "payments_and_penalties", 0.6, "2026-03-12T17:10:00Z")

    for fid, ts in (("RSU_BASIS_ZERO", "2026-03-16T15:00:00Z"), ("INTEREST_DOUBLE", "2026-03-16T15:20:00Z"), ("FX_WRONG_YEAR", "2026-03-16T15:25:00Z")):
        accept(fid, PRI, ts)
    time(PRI, "wages_and_stock_compensation", 2.1, "2026-03-16T15:40:00Z", "RSU/ESPP basis, ISO AMT")
    time(PRI, "investments_and_digital_assets", 2.8, "2026-03-17T18:00:00Z", "282 lots; broker reconciliations")
    for fid, ts in (("SCHC_1099K_DOUBLE", "2026-03-18T15:00:00Z"), ("MILEAGE_DUP_PAGE", "2026-03-18T15:30:00Z"), ("SEHI_NOT_ALLOWED", "2026-03-18T16:00:00Z")):
        accept(fid, PRI, ts)
    time(PRI, "business", 3.1, "2026-03-18T17:00:00Z")
    for fid, ts in (("MORTGAGE_PAYOFF_DOUBLE", "2026-03-19T15:00:00Z"), ("HOME_TAX_PRORATION", "2026-03-19T15:10:00Z"), ("VEHICLE_DONATION_VALUE", "2026-03-19T15:30:00Z"), ("HVAC_CAPITALIZE", "2026-03-19T16:00:00Z")):
        accept(fid, PRI, ts)
    time(PRI, "deductions_and_credits", 1.6, "2026-03-19T16:20:00Z")
    time(PRI, "rentals_and_sale", 2.4, "2026-03-19T17:30:00Z")

    # Marcus joins without clearance and tries to see an SSN
    ev(MAR, "view.sensitive", {"what": "ssn:theo", "context": "Form 8812 dependent check", "granted": False}, "2026-03-25T14:05:00Z")

    # Questions to the client (they become evidence)
    q1 = store.new_id("ques")
    ev(PRI, "question.asked", {"id": q1, "to": "client", "target": "doc:D23", "text": "Was the mileage log kept during the year (when, in what), or rebuilt afterwards? Several Sacramento trips are 150-240 miles."}, "2026-03-20T15:00:00Z")
    q2 = store.new_id("ques")
    ev(PRI, "question.asked", {"id": q2, "to": "client", "target": "line:SchA.11", "text": "Could St. Brigid send a letter that states the amount and that no goods or services were provided for your 12/21 gift?"}, "2026-03-20T15:05:00Z")
    ev(PRI, "time.logged", {"id": store.new_id("time"), "area": "business", "hours": 0.5, "note": "Client call (call-01)"}, "2026-03-26T17:40:00Z")
    accept("SCHC_BUSINESS_USE", PRI, "2026-03-26T18:00:00Z")
    accept("SCHC_PERSONAL_SPOTIFY", PRI, "2026-03-26T18:05:00Z")
    accept("CA_WAGES_SOURCE", PRI, "2026-03-27T17:00:00Z")
    time(PRI, "california", 1.4, "2026-03-27T17:30:00Z")
    ev("cu-02", "question.answered", {"id": q1, "text": "I wrote trips on a notepad in the car and copied them into the sheet in January. Some days had several stops so the miles add up."}, "2026-03-28T02:10:00Z")
    ev(PRI, "signoff.signed", {"id": store.new_id("sign"), "area": "business", "level": "preparer", "hash": state().area_hash("business")}, "2026-03-27T18:00:00Z")
    ev(PRI, "signoff.signed", {"id": store.new_id("sign"), "area": "investments_and_digital_assets", "level": "preparer", "hash": state().area_hash("investments_and_digital_assets")}, "2026-03-27T18:01:00Z")

    # ---- Review
    for a in [x for x in state().adjustments.values() if x["status"] == "proposed"]:
        ev(DAN, "adjustment.approved", {"id": a["id"], "role": "reviewer"}, "2026-04-06T15:00:00Z", None, f"line:{a['line']}")
    note(DAN, "review_note", "line:SchC.44a", "Mileage log was rebuilt from notes in January (client answer). Document the due diligence or reduce to trips we can corroborate with invoices/1099 payers before I sign business.", "2026-04-06T15:30:00Z", blocking=True)
    note(DAN, "review_note", "finding:CRYPTO_C6_BASIS", "C6: client's basis rests on one bank line to a closed exchange. Decide: accept with documented due diligence, or report zero basis. Partner call.", "2026-04-06T15:40:00Z", blocking=True)
    note(PRI, "variance_explanation", "line:SchC.1", "Gross receipts up from 128,400: three new clients in Austin (Riverbend, Quill) after the move; agrees to 1099-NECs + 9,300 non-1099.", "2026-04-06T16:00:00Z")
    note(PRI, "variance_explanation", "line:F1040.1a", "Wages up: Ngozi changed employers mid-year; RSU vest income 38,200 in Corvane box 1.", "2026-04-06T16:05:00Z")
    ev(DAN, "signoff.signed", {"id": store.new_id("sign"), "area": "investments_and_digital_assets", "level": "reviewer", "hash": state().area_hash("investments_and_digital_assets")}, "2026-04-07T15:00:00Z")
    ev(DAN, "signoff.signed", {"id": store.new_id("sign"), "area": "payments_and_penalties", "level": "reviewer", "hash": state().area_hash("payments_and_penalties")}, "2026-04-07T15:05:00Z")
    time(DAN, "partner_review", 0.0, "2026-04-07T15:10:00Z")
    time(DAN, "business", 0.8, "2026-04-07T15:20:00Z", "Review")
    for a in [x for x in state().adjustments.values() if x["status"] == "proposed" and x["requires_partner"]]:
        ev(HEL, "adjustment.approved", {"id": a["id"], "role": "partner"}, "2026-04-08T16:00:00Z", None, f"line:{a['line']}")
    note(HEL, "judgment", "finding:OUTSIDE_FILINGS", "Form 3520 (2023 inheritance) and FBAR are outside this engagement. Send the client a written advisory today; offer a separate engagement for late 3520 with reasonable-cause statement.", "2026-04-08T16:20:00Z", authority="Engagement letter scope (D01); IRC 6039F; 31 CFR 1010.350")
    time(HEL, "partner_review", 0.6, "2026-04-08T16:30:00Z")

    # ---- Extension
    ev(DAN, "filing.extension_filed", {"federal_form": "4868", "federal_paid": 36000, "california_form": "FTB 3519", "california_paid": 0,
                                       "basis": "Estimate from v2 (what_if.extension)", "timeline": "extension-2026-04-14"}, "2026-04-14T15:00:00Z")

    # ---- June: late documents; a later fix reopens the investments sign-off
    accept("MERIDIAN_UNREAD_PAGE", PRI, "2026-06-24T15:00:00Z")
    ev(PRI, "question.asked", {"id": store.new_id("ques"), "to": "st-03", "target": "finding:CA_ESTIMATES_VS_FTB",
                              "text": "FTB holds the 9/15/2025 3,500 as a 2024 credit. Request a transfer to 2025 before filing, or claim 10,500?"}, "2026-06-24T15:30:00Z")
    time(PRI, "pass_throughs_and_basis", 1.5, "2026-06-24T16:00:00Z", "Ridgeline K-1 (late), Woodworks basis with 2023 K-1")
