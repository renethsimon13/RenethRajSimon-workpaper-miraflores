# Video walkthrough — script (about 8 minutes)

Record the screen at 1440×900 with the deployed link. Before you start, open **Firm → Load demo season** so the data matches this script.

## 0:00 — The problem and the idea (45s)

"The brief asks what a workpaper has to *prove*. Where each number came from, what was done to it, who checked it, and what's still open. Those are facts with authors and timestamps. So I didn't build a grid. I built an append-only ledger of facts about the return. The pipeline's packet is loaded exactly as delivered and never modified. Every human action is an event, and every screen is a view computed from those events."

## 0:45 — Overview (45s)

- Show the four totals: engine v3 vs the workpaper. "Federal goes from about 4,220 owed to about a 4,400 refund after approved corrections; lines that need the engine are flagged rather than guessed."
- **Ready to file?** "These are the firm's required steps, evaluated live. Nothing files until they're green."
- **Work areas:** sign-offs per area, plus time against budget.

## 1:30 — Findings: checks that don't trust the engine (1m30)

- "The engine's own diagnostics caught none of the material errors. These checks read the printed pages, the prior year and the IRS and FTB records directly."
- Open **RSU shares taxed twice**:
  - Click the evidence chip: the 1099-B page opens with **"(not reported)" highlighted red**. The pipeline read that blank as 0.00 at 98% confidence.
  - "The supplement gives the basis. One click proposes the fix with its tax effect: about −15.5k federal."
- Briefly show **1099-K double count**, **mileage duplicate page** and **CA wages**. Point out "used but landed nowhere": the engine marked the paystub as used, but no number moved.

## 3:00 — Trace any number (1m)

- Return → Schedule C → click **Gross receipts**.
- Walk the drawer: engine vs workpaper, the rule text, "how this number was built" (the input tree), and the sources down to a document page and field with confidence.
- Then show "across versions and years" and the related returns.
- Documents → D23: page 3 says "second scan". "Every document lands somewhere or says why not."

## 4:00 — Change, review and people (1m15)

- Review → **Sign-offs**: "Investments shows reopened. Priya fixed the Meridian page-32 lot in June, after Daniel signed in April. A sign-off is pinned to a hash of what it attests to, so it reopens on its own."
- Switch the role to **Priya** and try to approve her own adjustment: the server refuses. Above 1,000 of tax effect, a partner must approve.
- Review notes: the two blocking notes (crypto basis, mileage log). "Open review notes block filing."
- People: a question to the client, and the client's answer kept as evidence.
- Switch to **Marcus** (no clearance) → Firm → reveal an SSN: refused and logged. Switch to **Jo** (admin): show the view log.

## 5:00 — Ask the workpaper (30s)

- Click **✦ Ask** → "Why did Schedule C gross receipts change?" Every sentence carries a clickable citation, and anything cited outside the evidence would be flagged red.
- On a finding, click **✦ Draft client question** → **Send to client**. A person always approves before anything is saved.
- "It's logged on the timeline like every other action."
- Mention the **? Tour** for a new hire's first day.

## 5:30 — Schedules (45s)

Sales: 282 lots grouped and reconciled to the broker statements; the Meridian difference is explained. Books to tax foots to the engine. Then the state split, basis by year (the 2023 K-1 filled the gap) and prior preparer vs us.

## 6:00 — Filing and after (1m15)

- As **Helen**: send to the client (the gates block it unless she overrides with a reason).
- Switch to **Ngozi** (client portal): approve and sign 8879.
- Back to Helen: transmit, and the server **refuses** because the two review notes are still open. Switch to **Daniel**, resolve them with the due diligence recorded, then Helen transmits and the return is frozen.
- Record the rejection (Theo's SSN), correct it from the SS card, then transmit and accept. "The amounts didn't change, so the 8879 still covers the return."
- Open **Letter 566** export: "the 2028 exam letter questions exactly two areas we corrected. The answer is one self-contained record with the reconciliation, the source pages and the trail."
- Show the roll-forward and next year's safe harbor.

## 7:15 — Technical decisions and trade-offs (45s)

- **Event sourcing.** Undo, versions, "since you last looked", reopening sign-offs and the freeze all come from one log.
- **No engine re-run.** Tax effects are linear at the packet's rates, with the engine's what-ifs used where they exist. Labeled honestly.
- **Deterministic checks**, not an LLM, for findings: auditable and repeatable.
- **Server-enforced roles and masking.** Simulated documents use a `{render, anchors}` contract, so real PDFs drop in.
- **Stack:** FastAPI, Postgres (Neon) and React on free tiers.
- **AI usage:** Claude did the deep read, the error hunt in code and most of the implementation under my direction. A blind CPA-briefed agent cross-checked the error list.
