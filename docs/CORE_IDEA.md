# Core idea and data model

## The idea: a workpaper is a ledger of claims, not a grid of numbers

A spreadsheet workpaper stores numbers and hopes the ticks and comments around them stay true. This one starts from what the brief says the workpaper must *prove*: where each number came from, what was done to it, who checked it, and what is still open. Each of those is a fact with an author and a timestamp, so the workpaper is built as an **append-only ledger of facts about the return**. Every screen is a view computed from that ledger.

Three layers, never mixed:

1. **The packet (immutable inputs).** Loaded exactly as delivered and fingerprinted by SHA-256. It covers the documents and their printed pages, the 3,012 extracted values, the three engine versions, client answers, prior years and agency records. Nothing in the app ever writes to it.
2. **The evidence graph (derived, read-only).** Every return line points to the lines it was built from (`inputs`) and to its sources: an extracted value, then the document page, then a position on that page; or a client answer, a prior-year pointer, an agency record or an engine parameter. The graph is indexed both ways, so you can trace a number down to the exact field on a page and trace a document up to every line it landed on. A document that lands nowhere must give a reason, or the "all documents accounted for" gate stays red.
3. **The workpaper ledger (append-only events).** Every human act is an event: proposing, approving or reversing an adjustment, a verification, a note, a question and its answer, a sign-off, a finding accepted or dismissed, a filing step, a time entry, a sensitive-data view, an undo. Nothing is ever updated or deleted.

**Independent checks** sit beside the engine, not on top of it. They are pure functions that take the packet and return findings: they read printed pages, the prior year and agency records, and never trust the engine's answer. Each finding carries its evidence and, where the fix is mechanical, ready-made adjustments with a tax-effect category.

## Data model

```
Packet          sha256, documents[], extracted_values[], return_versions[], client, prior_years, agency, firm
Line (engine)   key, form, line, label, value, rule, inputs[] -> Line, sources[] -> Source
Source          ev:<id> -> Document.page + anchor | qa:<id> | py:<pointer> | agency:<pointer> | ref:<param>
Document page   render {kind: simulated_text | image, content|url}, anchors[{ev, start,end | bbox}]
Event           id, ts, actor, type, entity, batch, payload            (append-only table)
Finding         id, severity, kind, area, summary, refs[], proposed[{line, delta, category}]   (computed)
```

The event types are `adjustment.proposed/approved/reversed`, `verification.added/removed`, `note.created/replied/resolved/reopened` (kinds: review note, judgment, election, due diligence, penalty decision, variance explanation, post-filing), `question.asked/answered`, `signoff.signed`, `finding.accepted/dismissed/reopened`, `fact.corrected`, `filing.*` (extension, approval requested, client approved, e-file submitted/rejected/accepted, amendment started), `standards.updated`, `assignment.set`, `time.logged`, `file.attached`, `link.added`, `view.sensitive`, `view.seen`, and `batch.undo/redo`.

**Projection.** The app folds the event log over the packet to get the current state: adjustments with status and tax effect, verifications, notes, questions, sign-offs, finding dispositions, the filing state, each person's inbox, time against budget and the view log.

## Requirements that fall out of the ledger

| Requirement | How it is met |
|---|---|
| Adjust without losing the original (who, why, tax effect) | An adjustment is a change against the engine line, never an overwrite. Its reason is mandatory, and its federal and California effect is computed at proposal. |
| What changed since I last looked | Show the events after your last `view.seen` marker. |
| Compare versions | v1, v2, v3 and "workpaper" are all diffable views. |
| Act on many items at once, with undo | A bulk action is one batch, and `batch.undo` is itself an event, so redo is possible and history stays complete. |
| Sign-offs that reopen when what was signed changes | A sign-off stores a hash of what it attests to: the area's numbers including pending adjustments, its active verifications and its finding dispositions. If the current hash differs, the sign-off shows as reopened. Approvals and conversation don't reopen it. |
| Freeze at filing; amend on top | Once the return is transmitted or accepted, the server refuses mutations. `filing.amendment_started` reopens it, and later adjustments are tagged with the amendment number. |
| Answer a notice with a self-contained record | Export the relevant lines, source pages, verifications, the audit trail and sign-offs into one HTML file, stamped with the packet and return hashes. |
| Carry forward with history | A roll-forward export holds carryovers, basis by year, assets, open items, judgments and the safe-harbor plan. |

## Decisions and trade-offs

- **The engine can't be re-run.** Workpaper totals are the engine total plus each approved adjustment's effect at the packet's per-dollar rates. Where the packet has an engine what-if, the exact figure is used instead (for example the HVAC capitalization). The UI says plainly that large changes cross thresholds (CTC phase-out, SALT cap, QBI) and the engine recompute is final.
- **Checks are deterministic code, not an LLM.** They need to be auditable and repeatable, and a reviewer must be able to see *why* something was flagged. A language model would fit elsewhere: drafting client questions and summarizing notices, with a human approving.
- **Rules are enforced on the server.** These are: no reviewing your own work, a partner over $1,000 of tax effect, an authority on every judgment, blocking review notes, the freeze at filing, and client approval tied to the return hash. The role switcher only chooses who you are; the server decides what you may do.
- **Masking happens at the response boundary.** Every API response is masked. A cleared person can reveal one value at a time, and every reveal or refused attempt is logged. The uncleared preparer (Marcus) can't reveal anything.
- **Simulated documents use a swappable contract.** A page is served as `{render, anchors}`. Today the render is the printed text and anchors are character offsets. A real PDF swaps in an image URL with bounding boxes from the same `position` fields; the trace, landed-on lists and highlights don't change.
- **Storage is Postgres in production and SQLite locally**, with a single append-only table plus a file table for attachments. Live collaboration uses server-sent events: every write notifies open browsers, which refresh their view.
