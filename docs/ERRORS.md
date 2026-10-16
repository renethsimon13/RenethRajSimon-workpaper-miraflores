# Errors found and how the design surfaced them

Ground truth: `printed_content` beats `extracted_values`, which beat the engine. Effects are change × v3 tax-effect rate, or the engine's own what-if where one exists. Negative means less tax.

All of these come from the **Findings** page, whose independent checks run on load. Each finding has evidence chips that open the exact page and field, plus one-click adjustments.

## A. Errors in the computed return (v3)

| # | Error | Engine → correct | Evidence | Fed | CA | How the design surfaced it |
|---|---|---|---|---|---|---|
| 1 | RSU shares taxed twice: the 1099-B left basis blank (noncovered) and the pipeline read the blank as **0.00 at 0.98 confidence**. The supplement was matched to the ESPP lot but not to the three RSU lots. | basis 0 → 19,100 + 19,100 + 9,420 | D28 p3, D11 p2, W-2 box 14 RSU 38,200 | −15,536 | −2,765 (two lots sold while a CA resident are fully CA-source) | Blank-read-as-zero check; the D11 row in the document index shows it landed on 1 of 4 lots; in the document view the blank is highlighted red. |
| 2 | Schedule C gross receipts include the 1099-K, yet those card payments are already in the books and on Atlas's 1099-NEC | 163,700 → 151,300 | D15 p3, D21, D17, D14 | −4,402 | −384 | Books-to-tax reconciliation ties every receipt dollar: 1099-NECs 142,000 + 9,300 from clients without 1099s = books. |
| 3 | Self-employed health insurance deducted although Erik could join his spouse's employer plans (IRC 162(l)(2)(B)) | 14,400 → 0 | qa-25; 2024 note on Sch1.17 | +4,464 (about +3,570 after the larger QBI deduction) | +605 | Client answers are evidence linked to lines; the prior-year view shows the 2024 treatment. |
| 4 | HVAC replacement (full system, permit) expensed as a repair; must be capitalized over 27.5 years | repair 11,000 → asset | D47, D46, call-01 | +3,633 | +896 | D47 is "used, landed nowhere"; the engine's own what-if supplies the exact effect. |
| 5 | Mileage page 3 is a second scan of page 2; the engine rule adds every page total | 11,800 → 8,100 miles | D23 p2/p3 | +919 | +80 | Duplicate-page detector across every document. |
| 6 | Home property tax ignores the seller's 6,912 proration credit at closing | 13,420 → 6,508 | D54, D57, D58 | ≈0 (the return is in AMT, where taxes are an add-back) | +332 | D54 landed nowhere. Total state and local tax drops under the cap, but the federal effect is nil because of AMT. |
| 7 | Mortgage payoff interest added on top of the Form 1098 that already includes it | 21,847 → 19,697 | D55, D56 | +559 | +103 | Lender-statement check; D56 says the interest is on the 1098. |
| 8 | Donated car claimed at the client's Kelley Blue Book value; the 1098-C sale caps it (IRC 170(f)(12)) | 6,000 → 2,900 | D66 box 4c, qa-39 | +806 | +149 | A third-party form overrides a client estimate. Item 1 of the 2028 exam letter. |
| 9 | Northlake sweep interest reported twice (composite 1099 and the bank's 1099-INT, same account 7731) | 3,680 → 1,840 | D28 p1, D29 | −640 | −127 | Same account and amount across two forms. |
| 10 | Swedish interest converted at the 2024 average rate | 1,747 → 1,871 | D36, fx 2025_average | +43 | +9 | Reference-year check on the rate used. |
| 11 | Phone (70%) and internet (50%) deducted at 100%; personal Spotify booked as business software | 3,480 → 2,172; −216 | call-01, D15 | +541 | +48 | Call notes are evidence; the line shows an unapplied client statement. |
| 12 | Federal estimates take Q4 from the questionnaire ("4,000 I think"); the IRS shows 3,000 | 13,000 → 12,000 | IRS transcript, qa-41, D67 | balance +1,000 | | The "estimated payments agreed to IRS records" gate can't pass until it matches. |
| 13 | California estimates count a 3,500 payment that was designated to tax year 2024, which the FTB holds as a 2024 credit | 14,000 → 10,500 | D68, ftb_account | | balance +3,500 | Same gate; partner decision: request a transfer or claim 10,500. |
| 14 | California taxes Texas wages: Halvorsen's payroll kept California as the work state to 9/30 | CA-source wages 218,400 → 129,569 | D73 paystub, D09 note, qa-03, qa-45 | | −5,685 | D73 is "used, landed nowhere"; the state-split view shows wages by work location. |
| 15 | Theo's SSN typed wrong in the organizer (digits transposed); the e-file will be rejected | 666-74-3309 → 3390 | D06 p1, D71, agency e-file R0000-504-02 | | | Identity is checked against the prior-year return at intake, *before* the 7/13 rejection. |
| 16 | Meridian lot M18 sits on page 32, which the pipeline didn't read | missing → −60 short-term | D31 p32; summary 71,965 vs detail 71,715 | −21 | −2 | Broker summary-vs-lots reconciliation. |
| 17 | Bitcoin lot C6 taxed with zero basis and the transfer-in date; the client later says it was bought 3/2021 for 3,050 | short-term 5,325 → long-term 2,275 (if substantiated) | D35, msg-07 | about −1,300 | | Judgment finding plus a blocking review note; substantiation is a single bank line. |
| 18 | Child-care provider: Little Sprouts' tax ID has two digits swapped, and Bright Oak's name is wrong on the return | 74-3829516 → 74-3829156 | D62, D61 | 0 | | Extracted value not found on its page. |
| 19 | SEP deduction: the 20% limit is computed on the engine's Schedule C. On the corrected Schedule C (net profit about 73,570) the limit falls to about 13,674, leaving about 4,326 of the 18,000 in excess. It must be withdrawn by 10/15/2026 or a 6% excise applies (Form 5329). | 15,214 → 13,674 | D26, Sch1.16 | +477 | +65 | Findings can depend on each other: this limit is recomputed from the corrected Schedule C, not the engine's. |
| 20 | California Schedule S credit claimed for the Oregon composite tax. Oregon is a reverse-credit state: California residents claim that credit on the Oregon return instead. | 844 → 0 | D39 p2, ScheduleS.credit | | +844 | State-credit rule check. |

**Net of the approved demo-season fixes (the SEP item still pending):** federal tax falls by about 9,600 and the return goes from about 4,220 owed to about a 4,390 refund; California tax falls by about 5,900. These are linear estimates at v3 rates. Several changes cross thresholds (CTC phase-out, SALT cap, QBI, AMT), so the engine recompute is final. In the app, lines built by plain sums recompute exactly; tax-rule lines show *pending engine recompute*.

One consequence: the scripted 7/20 "federal balance paid" event and the IRS interest and penalty assessment wouldn't happen on the corrected return. The Filing page flags this for the partner.

## B. Extraction mistakes (pipeline vs printed page)

- ev-0498, ev-0516, ev-0525: RSU basis values are blank on the page but were read as 0.00 at 0.98 confidence.
- ev-1045: provider tax ID transposed, at 0.97 confidence.
- ev-0022: a W-2 box 10 value of "0.00" was read, but no box 10 is printed.
- The C6 crypto basis is missing (0.6 confidence), and the St. Brigid amount was read at 0.41 confidence (the receipt shows "$?,500").
- D30/D31 page 32 was never extracted.
- **Verified clean:** all 1,826 Brightpath values (260 lots), the mileage trips, and the 2024 return values all match their printed pages.

## C. Judgment and due-diligence items (recorded, not auto-fixed)

- **Donor-advised fund gift (14,500):** the acknowledgment lacks the statement that the sponsor has exclusive legal control, which IRC 170(f)(18) requires. This is item 1 of the 2028 exam, so get a compliant letter.
- **S corp excess-distribution gain (21,215):** the engine sources it to California by residency days (about 11,300). As gain on an intangible recognized after the move, it is arguably Texas-source, which would lower California tax by about 725. Partner call.
- **St. Brigid 1,500:** the receipt lacks the "no goods or services" statement required for gifts of 250 or more.
- **Mileage log:** it was rebuilt in January (client answer). Page totals are round and local trips run 150–240 miles.
- **California AMT** on the ISO exercise isn't computed by the engine (grant date in California, exercise date in Texas).
- **Possible wash sales the broker didn't report** (M5 → M11, M12 → M16, M3 → M4/M6), from an independent ±30-day screen.
- **Contradictory client answers:** qa-14 says no sales against 294 actual sales (282 broker lots plus 12 crypto); qa-15, qa-31, qa-39 and qa-41 also conflict with documents.
- **Outside filings:** FBAR due 10/15/2026; Form 3520 for the 2023 inheritance (the prior preparer's open item, never resolved); late 1099-NECs. All three are outside the engagement, and the partner advisory is recorded with its authority.

## D. Engine results independently verified as correct

Checks that found nothing wrong matter, because they show the checks aren't just generating false positives.

- All 85 summed lines foot.
- Condo sale: gain 105,040 and unrecaptured §1250 gain 50,340.
- Woodworks S corp basis: using the 2023 K-1, end-2024 basis is 2,300, so 21,215 of distributions in excess of basis is gain.
- Form 8606: both 7,000 contributions converted, so only 26 is taxable.
- Every prior asset's depreciation.
- Excess Social Security credit 3,342; Additional Medicare tax 500.
- The full Social Security portion of SE tax is correct: Erik's SE tax is per person, so Ngozi's wages don't cap it.
- The broker 1099-B summaries agree with their lots, except Meridian page 32.

## E. Decoys

- Engine diagnostics flag the easy items and miss every material error above.
- "Used" isn't "applied": D11, D15, D47, D54, D69 and D73 are all marked used, but none changed a number.
- The brief says "two brokerages"; the data has three.
- Several client answers are confidently wrong, and the organizer SSN for Theo is wrong.

## F. Independent verification

As a cross-check, I had a separate AI agent, briefed as a senior CPA, review the packet without access to this list or the code.
- **Confirmed:** it independently found every error in section A.
- **Corrected two points:** the federal effect of the property-tax fix is nil (AMT), and the SEP limit falls rather than rises.
- **Added:** the Oregon reverse-credit issue, the donor-advised fund acknowledgment, the sourcing of the S corp gain, and California sourcing on the RSU lots.

The corrections and additions are built into the checks.
