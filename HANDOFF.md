# Zeno — Phase 2 Handoff (Orchestration)

> For the teammate picking up **orchestration**. Paste this to your Claude Code so it has context.
> The **perception layer** (problem retrieval + L1/L2/L3 classification) is done, tested, and on `main`.

## What Zeno is
A voice + vision IT-support agent ("Tier Zero") that resolves repetitive Tier-1 tickets before a
human. Browser widget → Deepgram STT → an LLM brain (GMI, Gemini 3 Flash) diagnoses & guides one
vetted playbook step at a time → Deepgram TTS speaks back. A vision model reads the user's uploaded
screenshot; Pillow draws an arrow on it; resolved tickets become walkthroughs cached in Redis so the
next identical ticket is served instantly. See `README.md` and `docs/` for the full pitch/architecture.

## How the backend is split (two phases in `backend/orchestrator.py`)
- **Phase 1 — Perception (DONE, owned by teammate A).** `perception.perceive(transcript)` matches the
  problem to a known scenario and classifies it **L1/L2/L3 by complexity**, returning a `Perception`
  object. The orchestrator routes on it.
- **Phase 2 — Orchestration (YOUR JOB).** Actually *solving* the problem: walking the playbook steps,
  the real human escalation, and polishing vision/annotation/walkthrough.

## The interface you build on: the `Perception` object
Returned by perception and stored in `state["perception"]`. **Do not change these field names** — they
are the contract. If you need a new field, ask teammate A.
```
scenario_key  str|None    matched known-issue key
match         bool        a known scenario was identified
confidence    float       0.0-1.0
locked        bool        True = scenario committed; orchestrator may act
say           str         clarifying question (when not locked) / routing line
complexity    int         1 | 2 | 3
level         int         1 | 2 | 3  (== complexity)
route         str         "auto_resolve" (L1) | "guided" (L2) | "escalate" (L3)
source        str         "live" | "queue"
cached        bool        a cached walkthrough exists
degraded      bool        LLM was unavailable, rule fallback used
ticket_id     str|None    set when source == "queue"
```
Routing already wired in `orchestrator.handle_turn`:
- `escalate` (L3) → returns `action="escalate"` — **currently a stub line; you implement the real hand-off.**
- `auto_resolve` (L1) → serves the cached walkthrough instantly (the "money shot").
- `guided` (L2) → falls through to **Phase 2 guided steps (your code).**

## Your Phase 2 tasks
1. **Guided steps** (`gmi.decide` + the Phase 2 block in `orchestrator.py`): stay on a step for
   follow-ups, advance only on confirmation, end in `resolve`. Already scaffolded — refine it.
2. **Real escalation** behind `action="escalate"`: right now it just speaks a line. Implement the
   actual human hand-off (create a ticket / forward the transcript / notify). High-severity security
   issues (`account_compromised`) route here.
3. **Vision + annotation + walkthrough** polish: `gmi.read_screen`, `annotator.annotate`
   (coordinates are hardcoded per scenario for the demo), `walkthrough.build`.
4. The **`vpn_not_connecting`** scenario has only a 2-step stub flow — flesh it out if you want a
   second full demo flow.

## Rules of engagement (so we don't collide)
- **Don't edit `backend/perception.py`** — teammate A owns it. Consume the `Perception` object only.
- **Frontend is teammate A's** (they'll do it later) — leave `frontend/` alone.
- You own: `orchestrator.py` Phase 2, `gmi.decide`/`read_screen`, `annotator.py`, `walkthrough.py`,
  and the escalation hand-off.

## Setup
```bash
git clone https://github.com/Cheemasukh962/Zeno && cd Zeno
git checkout main && git pull
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then add your GMI_API_KEY and DEEPGRAM_API_KEY
docker run -p 6379:6379 redis    # you have Redis; the app needs it
uvicorn backend.app:app --reload --port 8000
# open frontend/index.html in a browser
```
**Model IDs are already correct** in `.env.example` (`google/gemini-3-flash-preview` for brain + vision —
your GMI account has no Qwen3-VL). If models 404, list yours with `GET /v1/models` on the GMI base URL.

## Verify the handoff works (no UI needed)
```bash
python -m backend.eval_classification          # classification accuracy -> 22/22 = 100%
python -m backend.test_perception              # unit tests -> 8 pass
python -m backend.triage_queue backend/data/tickets.json   # batch triage demo
```

## Key files
| File | What |
|---|---|
| `backend/perception.py` | Phase 1 — retrieval + classification (A's; read-only for you) |
| `backend/orchestrator.py` | `handle_turn`: Phase 1 routes, **Phase 2 is yours** |
| `backend/gmi.py` | LLM brain + vision (`diagnose`, `decide`, `read_screen`, `summarize_steps`) |
| `backend/annotator.py` | Pillow arrow on screenshot (hardcoded coords for demo) |
| `backend/walkthrough.py` | builds the kept illustrated guide |
| `backend/store.py` | Redis: state, playbook, walkthrough library, metrics |
| `backend/playbook.json` | 3 scenarios; each `guided` entry needs non-empty `steps` |

## Gotchas
- **Redis required** for the live app (state + the L1 cache "money shot"). No Redis = it can't run live.
- **Windows + Deepgram**: TTS tempfile bug already fixed in `deepgram_client.py`.
- Keyless mode runs via fallbacks (canned lines, no voice/vision) — fine for testing logic, but the
  real demo needs the GMI + Deepgram keys.

Status: perception layer is green end-to-end with real keys (brain, vision, voice round-trip, L1/L2/L3
routing, cache money shot all pass). Build Phase 2 on top.

---

## One small ask for Phase 2: the `GET /admin/activity` endpoint (for the live dashboard)

Teammate A built an **admin dashboard** (`frontend/admin.html`) that visualizes L1/L2/L3 live. It
already works standalone (falls back to `frontend/sample-activity.json`) and will **go live with zero
frontend changes** once you add this endpoint. Please add it during Phase 2 — it's additive (a new
route in `app.py` + a small Redis history list in `store.py`; no changes to perception or the widget).

```
GET /admin/activity ->
{ "agent_status": "live" | "paused",
  "metrics": { "deflected", "saved_usd", "library_size", "cache_hits", "active" },   # store.metrics() + active count
  "active":  [ { "call_id", "started_at", "updated_at", "status": "active",
                 "scenario_title", "step_idx", "step_total", "complexity", "cache_hit" } ],
  "history": [ { "call_id", "started_at", "updated_at", "status": "resolved" | "escalated",
                 "scenario_title", "step_idx", "step_total", "complexity", "cache_hit" } ] }
```
- `complexity` = the perception **level**: send `1/2/3` or `"low"/"medium"/"high"` (the dashboard
  accepts either; `1→low (auto)`, `2→medium (guided)`, `3→high (escalate)`).
- `status`: `escalate` route → `"escalated"`; resolved → `"resolved"`; mid-guided → `"active"`.
- **Source**: `active` from the live `state:{call_id}` keys in Redis (you already store `step_idx`,
  `scenario`, `perception`); `history` from a new Redis list you append to on resolve/escalate.
- `scenario_title` = `store.get_scenario(key)["title"]`; `step_total` = `len(scenario["steps"])`.
