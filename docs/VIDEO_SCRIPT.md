# Video script (about 5 minutes)

Spoken lines are plain text. **[CLICK: …]** lines are actions, not spoken. Teleprompter version: published as a private page.

Before recording: Jo → Firm → Load demo season; switch to Priya → Overview; warm up ✦ Ask once.


## 1 · What this is (0:00)

**[CLICK: Overview page, viewing as Priya]**

Hi, I'm Reneth. This is my workpaper for the Okafor-Lindqvist 2025 return.

At Miraflores, software reads the documents and computes the return. The workpaper has one job: prove that return is right. Where every number came from, what was done to it, who checked it, and what is still open.

So I didn't build a spreadsheet. I built a ledger. The client's data is loaded exactly as delivered and never changed. Every action — an adjustment, a review note, a sign-off — is saved as a permanent event, and every screen is calculated from those events.


## 2 · The return at a glance (0:35)

**[CLICK: Point at the four money boxes]**

Here's the headline. The engine says the couple owe forty-two hundred dollars federally. After the corrections the workpaper found, they're actually due a refund of about forty-four hundred, and California's refund grows to about fourteen thousand.

**[CLICK: Point at "Ready to file?"]**

On the left are the firm's required steps, checked live. Five of thirteen are done, so nothing can be filed yet. The server enforces that, not the screen.

**[CLICK: Point at Findings, then the inbox on the right]**

In the middle are the findings, and on the right is Priya's inbox, including a sign-off that reopened on its own.


## 3 · Finding the errors (1:10)

**[CLICK: Findings → "resolved" tab]**

The engine's own warnings missed every serious error, so the workpaper runs its own checks against the printed documents, last year's return and the tax agency records. They never trust the engine.

**[CLICK: First card, "Blank basis read as $0.00" → click the chip D28 ev-0498]**

Here's the biggest one. On this broker form, the cost of three stock sales is blank: "not reported". The software read that blank as zero, with ninety-eight percent confidence.

**[CLICK: Point at "Landed on F8949.B.N1" at the bottom]**

That zero went straight onto the return. Forty-seven thousand dollars of stock pay was taxed twice — once as salary and once as a gain. About fifteen thousand five hundred dollars of extra tax.

**[CLICK: Close → Return → Schedule C → click 163,700 next to Gross receipts]**

Any number traces the same way: how it was built, the exact source fields, every version and last year. Gross receipts was too high because a twelve-thousand-dollar card payment was counted twice.

**[CLICK: Close → Documents → "not applied" tab]**

It works in reverse too. Every document lands on the return or says why not. These four were marked "used" but never changed a number — that's where several errors were hiding.


## 4 · Changing, reviewing, signing (2:15)

**[CLICK: Review → "Adjustments" tab]**

Corrections never overwrite the engine. Each adjustment records who, why, and its tax effect. Anything over a thousand dollars needs the partner, and nobody approves their own work.

**[CLICK: "Sign-offs" tab]**

Sign-offs are pinned to a fingerprint of what was signed. Daniel signed Investments in April. A fix came in June, so his sign-off reopened by itself.

**[CLICK: "Notes" tab]**

And review notes like these block filing until they're cleared.

**[CLICK: Viewing as → Marcus Bell → Firm → click "SSN Ngozi reveal"]**

Roles are enforced on the server. Marcus hasn't cleared his background check, so sensitive data stays masked. His attempt to see it is refused, and logged.


## 5 · The records a CPA expects (3:00)

**[CLICK: Viewing as → Priya → Schedules → "Books to tax"]**

The schedules a CPA expects are here. Books to tax walks the bookkeeping to Schedule C, with every receipt dollar matched to the tax forms.

**[CLICK: "Sales detail" tab]**

Nearly three hundred sales, grouped and checked against each broker's totals. The one mismatch is a sale on a page the software never read.


## 6 · AI inside the product (3:20)

**[CLICK: ✦ Ask → click "What is still blocking filing?"]**

I used AI where wording helps, not where accuracy is decided. "Ask the workpaper" answers only from this workpaper's evidence, every sentence cites a clickable source, made-up sources are flagged, nothing is saved without a person, and every call is logged.

_If the AI is busy:_ The provider is busy right now, so it falls back to showing the cited evidence instead of guessing.


## 7 · Filing and after (3:45)

**[CLICK: Close → Viewing as → Helen Strand → Filing & after → "Partner: send to client"]**

When Helen tries to send the return to the client, the gates stop her and list what's missing. Once it's filed, the return freezes, and any change becomes an amendment on top.

**[CLICK: Cancel → click "Answer Letter 566 (2028)"]**

In 2028 the IRS questions the car donation and the business receipts — two things the workpaper had already corrected. The answer is one self-contained record: the reconciliation, the source pages, and the full trail.

**[CLICK: Back to the app → Viewing as → Ngozi Okafor]**

And the client sees only her own portal: her estimated refund, her questions, and her documents.


## 8 · Decisions and trade-offs (4:15)

**[CLICK: Viewing as → Priya → Overview]**

A few decisions, and what they cost.

One. The event ledger. Undo, version comparison, "what changed since I last looked", reopening sign-offs and the freeze at filing all come from that one design.

Two. The engine can't be re-run. Simple sums recalculate exactly. Anything that needs tax rules is marked "pending recompute" instead of guessed, and totals are estimates from the packet's tax rates.

Three. The error checks are plain code, not AI, so they're repeatable and auditable.

Four. Login is stubbed behind the role switcher the brief asks for, but every rule runs on the server, so real sign-in changes who you are, not what you're allowed to do. And the simulated documents use the same format a real PDF would, so real ones can drop in.

It runs on FastAPI, Postgres and React on free hosting, with twenty-eight automated tests on every push.


## 9 · How I used AI, and close (4:55)

I built this with Claude as a pair. It read the packet, hunted errors with code and wrote most of the implementation, while I set the direction and checked the results. A separate agent, briefed as a senior CPA, reviewed the packet blind — it confirmed the errors and corrected two of mine, which are now built in.

The full list of errors, and how the design surfaced each one, is in the repo. Thanks for watching.
