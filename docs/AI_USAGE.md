# How I used AI

I built this with Claude (Anthropic) as a pair working in an agentic environment: shell, file system, headless browser, and sub-agents. I set direction, constraints and acceptance criteria. Claude did most of the reading, scripting and code, and I reviewed what came back.

*(Edit this page in your own words before submitting. It should describe what you actually did.)*

## Workflow

1. **Read everything before designing.** Claude read the brief and every section of the packet. It dumped all 74 documents' printed pages and walked the README, engine rules, three return versions, timeline and agency records. It also checked the PDF and JSON for hidden text or planted instructions and found none.
2. **Hunt errors with code, not intuition.** Throwaway scripts did the following:
   - compared every extracted value with its printed page;
   - re-parsed all 260 Brightpath lots and reconciled them to the summary;
   - recomputed every summed engine line;
   - mapped every document to the lines it lands on;
   - diffed v1 → v2 → v3.

   The error list in `ERRORS.md` came from that data, and each item cites its evidence ids.
3. **Turn findings into product.** Each script that found an error became a deterministic check in `backend/app/checks.py`, so the app finds the same errors live and shows its evidence. I chose deterministic checks over LLM judgment on purpose: they're auditable and repeatable.
4. **Choose the architecture.** We designed it together. I asked for a Python backend and free hosting; Claude proposed the append-only event ledger. We talked through the trade-offs: no engine re-run, so tax effects are linear estimates; masking at the API boundary; server-side rules; sign-offs pinned to a content hash.
5. **Build and verify.** Claude wrote the FastAPI backend and the React frontend. It drove the app in a headless browser to screenshot each page and fix what looked wrong. A scripted test pushed the full filing lifecycle through the server rules: self-review refused, partner threshold, blocking notes, freeze, rejection and fix, acceptance, amendment.
6. **Get an independent review.** A separate agent, briefed as a senior CPA and barred from reading our conclusions, reviewed the packet blind. Its list was compared with ours, and the differences were resolved and recorded.

## What I checked myself

- *(Fill in: e.g. spot-checked the RSU basis, 1099-K and mileage findings against the source pages in the app; walked the filing flow as each role; read the core-idea page and errors list end to end.)*

## AI inside the product

The "Ask the workpaper" panel answers and drafts only from retrieved workpaper evidence. Its citations are verified against that evidence, it saves nothing without a person, and every call is logged. I chose to keep AI out of error detection, which needs to be deterministic, and to put it where wording and synthesis help: explaining a number, drafting a client question, drafting the notice response.

## Where AI was not trusted

- **The return.** The engine's numbers are never edited in place. Every change is a human-approved adjustment with a reason.
- **Tax law.** Any position taken (SE health insurance eligibility, capitalizing the HVAC, the vehicle donation limit, charitable substantiation) cites its authority in the finding or judgment note, so a CPA can check it.
- **Client facts.** Documents and third-party records override client answers. Contradictions are kept as evidence, not resolved silently.
