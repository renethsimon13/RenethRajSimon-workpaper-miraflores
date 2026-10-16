# Miraflores — web-native tax workpaper (Okafor-Lindqvist 2025)

**Live app:** _add Render URL_ · **Video walkthrough:** _add video link_

A working workpaper for one complex household's 2025 return, built from the purpose rather than the spreadsheet. The packet is loaded as delivered; every human action is an append-only event; every screen is a view of packet + events.

- **Core idea and data model:** [`docs/CORE_IDEA.md`](docs/CORE_IDEA.md)
- **Errors found and how the design surfaced them:** [`docs/ERRORS.md`](docs/ERRORS.md)
- **How AI was used:** [`docs/AI_USAGE.md`](docs/AI_USAGE.md)
- **Video script:** [`docs/VIDEO_SCRIPT.md`](docs/VIDEO_SCRIPT.md)

## What's in it

| Area | Where |
|---|---|
| Trace any number to its source field; any document to every line it landed on (or why not) | Click any number · Documents |
| Independent checks that don't trust the engine (31 findings, one-click fixes with tax effect) | Findings |
| Calculation trees, reconciliations, 282-lot sales detail, books→tax, state split, depreciation, basis by year, carryovers, K-1s, payments, prior preparer vs us | Return · Schedules |
| Adjustments that keep the original (who, why, federal/CA effect), version compare, what-ifs, bulk actions with undo | Return · Compare · Review |
| Review notes that block filing, sign-offs that reopen when what was signed changes, enforced roles, live updates | Review · role switcher |
| Questions that become evidence, assignments, deadlines, notifications, time vs budget, client portal & 8879 | People · client view |
| Extension, e-file rejection and fix, freeze, amendment, notice-response record, client copy, roll-forward | Filing & after |
| Firm standards (editable by the administrator), masking with view log, retention, search | Firm · search bar |

Use the **Viewing as** switcher to act as preparer (Priya), uncleared preparer (Marcus), reviewer (Daniel), partner (Helen), administrator (Jo), quality reviewer (Sam) or the clients (Ngozi, Erik). Rules are enforced by the server, not the UI.

## Run locally

```bash
# API (SQLite by default)
cd backend && pip install -r requirements.txt
SEED_ON_EMPTY=1 uvicorn app.main:app --reload --port 8000
# UI (dev server proxies /api)
cd frontend && npm install && npm run dev      # http://localhost:5173
```

Or build once and let FastAPI serve everything from one URL: `cd frontend && npm run build`, then open http://localhost:8000.

## Deploy (free)

1. **Database:** create a free project on [Neon](https://neon.tech) and copy the `postgresql://…` connection string.
2. **Web service:** on [Render](https://render.com) → New → Blueprint → this repo (uses `render.yaml`, Docker, free plan). Set `DATABASE_URL` to the Neon string.
3. Open the service URL. The first load after idle takes ~30–60 s (free tier). The demo season loads automatically on an empty database; **Firm → Reset** returns to the bare packet.

## Layout

```
data/okafor_lindqvist_2025_packet.json   the packet, unmodified (sha256 shown in the app)
backend/app/packet.py    read-only indexes over the packet (evidence graph)
backend/app/checks.py    independent checks → findings with evidence and proposed adjustments
backend/app/store.py     append-only event store (Postgres / SQLite)
backend/app/state.py     projection: adjustments, sign-off hashes, gates, inbox, filing state
backend/app/views.py     schedules and document view ({render, anchors} contract)
backend/app/exports.py   notice response, client copy, roll-forward, full record
backend/app/main.py      API, server-side rules, masking, live updates (SSE)
frontend/src/            React + TypeScript UI
```
