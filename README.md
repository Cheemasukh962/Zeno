# Zeno

**A voice + vision IT support agent.** You talk to it like a helpdesk; it sees your screen,
circles exactly where to click, walks you through the fix at your pace — and hands you a
personalized guide you keep for next time.

> The planning docs call the concept **"Tier Zero"** — the agent that resolves tickets
> *before* they ever reach a Tier-1 human. Same project, just the working name.

---

## The idea in 30 seconds

- 50–80% of IT tickets are repetitive Tier-1 stuff (drive mapping, sign-in loops, "how do I export"). Each one costs ~$20 of an engineer's time.
- Text chatbots fail the people who need help most — non-technical users who can't describe the problem or follow written steps.
- Zeno is **voice-first** (you just talk) and **vision-aware** (you send a screenshot, it reads your *actual* screen and draws an arrow on the right button).
- When it's fixed, it builds a **walkthrough from your own screenshots** and caches it. The next person with the same issue gets that real guide instantly — **the knowledge base writes itself.**

Full pitch, market sizing and comparables: [`docs/01_market_research.md`](docs/01_market_research.md).

## How it works

The only thing on the user's machine is a **browser widget**. Everything else is a cloud
agent (Docker on AgentBox):

- **Deepgram** — speech-to-text + text-to-speech (voice in/out)
- **LLM brain** (GMI, e.g. Gemini 3 Flash) — diagnoses, then guides one vetted step at a time
- **Vision** (GMI, e.g. Qwen3-VL) — reads the user's screenshot
- **Annotator** (Pillow) — draws the arrow/box on their screenshot
- **Walkthrough generator** — assembles the kept guide from real screenshots + narration
- **Redis** — call state, the vetted playbook, learned fixes, and the walkthrough library

**It is NOT a lock-step script.** Two phases: (1) *intake* — it converses and asks clarifying
questions until it's confident what's wrong; (2) *guided steps* — it stays on a step to answer
follow-ups ("which button?") and only advances when the user or a fresh screenshot confirms the
step is done. Details: [`docs/02_architecture.md`](docs/02_architecture.md).

## Repo layout

```
Zeno/
├── README.md              ← you are here
├── docs/                  ← planning (read these first)
│   ├── 01_market_research.md   market, sizing, comparables, pitch numbers
│   ├── 02_architecture.md      full architecture + the conversation model
│   └── 03_build_plan.md        hour-by-hour plan + 3-minute demo script
├── backend/
│   ├── app.py             FastAPI + WebSocket entry point
│   ├── orchestrator.py    one turn: intake → guided steps (advance-gated)
│   ├── gmi.py             brain (diagnose + decide) and vision, via GMI
│   ├── deepgram_client.py STT + TTS (falls back to text if no key)
│   ├── store.py           Redis: state, playbook, learned fixes, walkthrough library
│   ├── annotator.py       Pillow: draw the arrow on the user's screenshot
│   ├── walkthrough.py     build the kept illustrated guide
│   └── playbook.json      seeded "shared drive won't open" scenario
├── frontend/index.html    single-page widget (mic, screenshot upload, transcript, guide)
├── requirements.txt
├── .env.example
└── Dockerfile             for AgentBox
```

## Run locally

```bash
cp .env.example .env          # fill in GMI + Deepgram keys
pip install -r requirements.txt
docker run -p 6379:6379 redis # or any local redis
uvicorn backend.app:app --reload --port 8000
# then open frontend/index.html in a browser
```

Without keys it still runs: no Deepgram → typed input + no audio; no GMI → it speaks the
scripted playbook line instead of crashing. So you can poke at the flow before wiring APIs.

## Status

**Built:** voice-loop spine, intake + advance-gated stepping, vision read, annotator,
walkthrough generator, Redis memory + walkthrough library, dashboard metrics, web widget.
All backend modules compile; the conversation flow is unit-smoke-tested.

**TODO on the day** (see the build plan): confirm the GMI base URL + keys, deploy the
container to AgentBox (mandatory integration — do it early), capture the demo screenshots,
and — stretch goal — render the walkthrough as a narrated MP4.

## Hackathon context

Beta Fund AI Agents Hackathon · Track: **Agents for Hire**. Mandatory integration: **AgentBox
by GMI**. All models run through GMI's single OpenAI-compatible API, so swapping models
(brain or vision) is a one-line env-var change.
