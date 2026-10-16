# Video script (about 5 minutes)

CLICK = do it. POINT = hold the mouse there while saying the line.

## 1 · What this is (0:00)

- **CLICK:** Overview page, viewing as Priya

- **POINT:** The title "Okafor-Lindqvist household - tax year 2025"

> Hi, I'm Reneth. This is my workpaper for the Okafor-Lindqvist 2025 return.

> At Miraflores, software reads the documents and computes the return. The workpaper proves that return is right: where every number came from, what was done to it, who checked it, and what is still open.

- **POINT:** The grey line under the title ending "loaded as delivered"

> So I didn't build a spreadsheet. I built a ledger. The packet is loaded exactly as delivered and never changed. Every action — an adjustment, a note, a sign-off — is saved as a permanent event, and every screen is calculated from those events.

## 2 · The return at a glance (0:36)

- **POINT:** First box, "Federal balance due (engine v3) 4,220"

> Here's the headline. The engine says the couple owe forty-two hundred dollars federally.

- **POINT:** Second box, "(4,392)", then the fourth box, "(14,153)"

> After the workpaper's corrections, they're due a refund of about forty-four hundred, and California's refund grows to about fourteen thousand.

- **POINT:** "Ready to file?" card — the "5/13" badge in its corner

> The firm's required steps are checked live. Five of thirteen are done, so nothing can be filed yet — and the server enforces that, not the screen.

- **POINT:** Middle card "Findings" (the red/yellow chips), then the right card "For Priya Raman" — its "signoff reopened" row

> Then the findings, and Priya's inbox — including a sign-off that reopened on its own.

## 3 · Finding the errors (1:04)

- **CLICK:** Left menu → Findings → "resolved" tab

> The engine's own warnings missed the serious errors, so the workpaper runs its own checks against the printed documents, last year's return and the IRS records.

- **CLICK:** First card, "Blank basis read as $0.00" → click the chip D28 ev-0498

- **POINT:** On the page: the boxed "(not reported)" after "basis" on the N1 line

> The biggest one: on this broker form, the cost of three stock sales is blank — "not reported".

- **POINT:** Card below the page: "Extracted value 0", "nothing printed — blank" and "confidence 0.98"

> The software read that blank as zero, with ninety-eight percent confidence.

- **POINT:** Same card: "Landed on F8949.B.N1"

> That zero landed on the return, so forty-seven thousand dollars of stock pay was taxed twice — as salary and as a gain. About fifteen and a half thousand dollars of extra tax.

- **CLICK:** Close → left menu Return → "Schedule C" in the form list → click 163,700 on the "Gross receipts" row

- **POINT:** Top boxes: "Engine 163,700" then "Workpaper 151,300"

> Any number traces the same way: how it was built, the exact source fields, every version and last year.

- **POINT:** Sources list: "D14 Total income 151,300", then "D21 Box 1a gross amount 12,400"

> Gross receipts was too high: twelve thousand four hundred dollars of card payments counted twice — once in the books, and again from the card processor's form.

- **CLICK:** Close → left menu Documents → "not applied" tab

- **POINT:** The four red "not applied" chips in the Status column

> It works in reverse: every document lands on the return or says why not. These four were marked "used" but never changed a number — that's where errors were hiding.

## 4 · The records a CPA expects (2:13)

- **CLICK:** Left menu Schedules → "Books to tax" tab

- **POINT:** Right card: "Less: Atlas card payments reported on both (12,400)", then the green "every receipt dollar explained"

> All the schedules a CPA expects are here. Books to tax walks the bookkeeping to Schedule C — there's that twelve thousand four hundred, removed once, and every receipt dollar explained.

- **CLICK:** "Sales detail" tab

- **POINT:** Top table, Meridian row: the red "✗ 250.00"

> Nearly three hundred sales, grouped and checked against each broker's totals. One doesn't agree, by two hundred fifty dollars.

- **CLICK:** Same row → click the chip "D31 p32"

- **POINT:** Grey line at the top: "extraction partial — Page 32 … was not read by the pipeline", then the page text "M18 Ironwood REIT … proceeds 250.00"

> The document record says page thirty-two was never read. And there's the missing sale — two hundred fifty dollars, with no highlights, because nothing was extracted.

## 5 · Changing, reviewing, signing (2:48)

- **CLICK:** Close → left menu Review → "Adjustments" tab

- **POINT:** Top card "SchD.2 −60 proposed — Add M18 … from unread page 32"

> Corrections never overwrite the engine. Here's the fix for that sale: who, why, and its tax effect.

- **POINT:** Third card "F8949.B.N1 −19,100": the purple "partner sign-off (>1,000 effect)" chip, then "Proposed by Priya … approved by Daniel … approved by Helen"

> Anything over a thousand dollars of tax needs the partner, and nobody approves their own work.

- **CLICK:** "Sign-offs" tab

- **POINT:** Row "Investments & digital assets": the red "reopened Daniel Ortiz · 2026-04-07"

> Sign-offs are pinned to a fingerprint of what was signed. Daniel signed Investments in April; that June fix changed it, so his sign-off reopened by itself.

- **CLICK:** "Notes" tab

- **POINT:** The red "blocks filing" chip on the first card

> And review notes like these block filing until they're cleared.

- **CLICK:** Viewing as → Marcus Bell → left menu Firm → click "SSN Ngozi: •••• reveal"

- **POINT:** The black message at the bottom: "No sensitive-data clearance. This attempt was logged."

> Marcus hasn't cleared his background check, so sensitive data is masked before it leaves the server. His attempt is refused, and logged.

## 6 · AI inside the product (3:30)

- **CLICK:** Viewing as → Priya → top bar "✦ Ask" → click "What is still blocking filing?"

- **POINT:** Once it answers: one of the citation chips inside the answer

> AI is used where wording helps, not where accuracy is decided. It answers only from this workpaper's evidence, every sentence cites a source, invented sources are flagged, and every call is logged.

- *If AI is busy, say instead:* The provider is busy right now, so it falls back to showing the cited evidence instead of guessing.

## 7 · Filing and after (3:44)

- **CLICK:** Close → Viewing as → Helen Strand → left menu Filing & after → "Partner: send to client for approval and 8879"

- **POINT:** The pop-up "Not ready to send" and its list of missing steps

> When Helen tries to send the return to the client, the gates stop her. She can override only with a written reason. Once filed, the return freezes, and any change becomes an amendment on top.

- **CLICK:** Cancel → under Records click "Answer Letter 566 (2028) — self-contained record"

- **POINT:** "Item 1": the car line, engine 6,000 → workpaper 2,900. Then scroll to "Item 2": "Less duplicate reporting (12,400)"

> In 2028 the IRS questions the car donation and the business receipts — both already corrected. There's our twelve thousand four hundred again. The answer is one self-contained record: reconciliation, source pages, and the full trail.

- **CLICK:** Back to the app tab → Viewing as → Ngozi Okafor

- **POINT:** "About 4,392 refund", then "Questions from your CPA team"

> And the client sees only her own portal: her estimated refund, her questions, her documents.

## 8 · Decisions and trade-offs (4:22)

- **CLICK:** Viewing as → Priya → Overview

> A few decisions, and what they cost.

> One. An event ledger. Undo, version compare, "what changed since I last looked", reopening sign-offs, the filing freeze and live updates all come from that one design. The cost: screens are rebuilt from the events — instant for one household, but firm scale needs snapshots.

> Two. I can't re-run the engine, so sums recalculate exactly, anything needing tax rules is marked "pending recompute", and totals are estimates from the packet's rates.

> Three. The error checks are plain code, not AI, so they're repeatable and tested.

> Four. Login is stubbed behind the role switcher, but every rule runs on the server, so real sign-in changes who you are, not what you may do. And simulated documents use the same anchors a real PDF would.

> It's Python with FastAPI, Postgres and React, on free hosting — the price is a slow first load — with twenty-eight automated tests on every push.

## 9 · Close (5:23)

- **POINT:** Back on the Overview — on the last sentence about new hires, point at "? Tour" in the top bar

> So that's the idea: the workpaper doesn't trust the engine, it proves it. Every number traces to a page, every change has a name and a reason, and a new hire can press Tour on day one.

> The design page and the full list of errors are in the repo. Thanks for watching — I'd be glad to go deeper on any part.
