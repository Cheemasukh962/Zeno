# Tier Zero — Technical Architecture

Web-widget voice + vision IT support agent. Built on GMI Cloud models, deployed on AgentBox.

---

## 1. One-paragraph overview

A browser widget lets a user **talk** to the agent (Deepgram STT) and **upload a screenshot** of their screen. The agent's brain (a fast LLM on GMI) decides the next step using a curated IT playbook in **Redis**. A **vision model** reads the uploaded screenshot to confirm what the user is actually looking at. The agent replies by **voice** (Deepgram TTS) and, when useful, sends back the user's own screenshot **with an arrow/box drawn on the exact control**. When the issue is resolved, a **Walkthrough Generator** assembles the user's own annotated screenshots plus narrated, numbered steps (pulled from the call transcript) into a personalized guide the user keeps and can replay. That walkthrough is cached in Redis, so the **next** user with the same symptom gets a real, human-validated guide instantly at ~zero cost — the knowledge base builds itself out of real resolutions.

## 2. Component diagram (text)

```
┌──────────────────────── Browser widget (you build) ────────────────────────┐
│  • Mic capture + audio playback                                            │
│  • "Send screenshot" upload button                                         │
│  • Transcript + annotated-image display                                    │
│  • Tiny "tickets deflected / $ saved" counter (the demo money shot)        │
└───────────────┬───────────────────────────────────────────┬───────────────┘
                │ audio / image / text (WebSocket)            │
                ▼                                             ▼
┌──────────────────────── Agent backend (Docker on AgentBox) ────────────────┐
│                                                                            │
│   Deepgram STT  ──►  ORCHESTRATOR  ──►  Deepgram TTS  ──► back to browser   │
│   (your credits)        │  ▲                (your credits)                 │
│                         │  │                                               │
│             ┌───────────┘  └─────────────┐                                 │
│             ▼                            ▼                                  │
│      LLM BRAIN (GMI)              VISION (GMI)                              │
│      Gemini 3 Flash /             Qwen3-VL-235B /                           │
│      GPT-5.4-mini                 Gemini 3 Flash (image→text)               │
│      • INTAKE: chats first &      • "what's on this screen?"               │
│        diagnoses before step 1    • confirms a step is actually done       │
│      • per turn picks ONE of:     • drives the stay-vs-advance call        │
│        clarify / stay / advance /                                          │
│        annotate / resolve / escalate                                       │
│             │                  │                    │                       │
│             ▼                  ▼                    ▼                       │
│        ANNOTATOR          WALKTHROUGH GEN          REDIS                    │
│        (Pillow)           • orders the              • per-call state        │
│        • draw box/arrow     annotated shots         • playbook symptom→steps│
│          on user's shot   • brain → numbered        • learned-fix cache     │
│        • instant, free      steps from transcript   • WALKTHROUGH LIBRARY   │
│        • returns URL       • TTS narration            (real guides, reused) │
│                           • illustrated guide                              │
│                             (MP4 = stretch)                                 │
└────────────────────────────────────────────────────────────────────────────┘
```

## 3. Request/response flow (one turn)

1. **User speaks** → browser streams audio → **Deepgram STT** → text.
2. **Orchestrator** loads call state from Redis, sends `{transcript, state, last_screenshot_reading}` to the **LLM brain**.
3. Brain returns a structured action, e.g.:
   ```json
   { "say": "Let's check the sharing tab. Can you send me a screenshot of what you see now?",
     "action": "request_screenshot",
     "step_id": "drive_map_03" }
   ```
4. If the user uploads an image → **Vision model** returns a description ("Finder window, sidebar shows no network drive, top tab 'General' selected"). Brain uses it to pick the next step and may call the **Annotator** to draw an arrow on the right control.
5. Orchestrator sends `say` text → **Deepgram TTS** → audio back to browser; sends annotated image URL when one was produced.
6. **On resolution** (brain returns `action: "resolved"`, or user asks "send me that as a guide"), the orchestrator calls the **Walkthrough Generator**: it takes the ordered annotated screenshots from this call + the transcript, asks the brain to distill clean numbered steps, adds TTS narration, and returns an illustrated guide (HTML/PDF; MP4 is a stretch). Action shape:
   ```json
   { "action": "generate_walkthrough",
     "title": "Reconnect your shared drive",
     "steps": [ {"text": "Open Finder", "image": "shot_01_annotated.png"}, ... ] }
   ```
7. Write the finished walkthrough + `symptom_hash → walkthrough_id` to the Redis **walkthrough library**. On a future call, the orchestrator checks this **first** — a hit returns the real guide in one turn at ~zero cost.

## 3.5 Conversation model — it is NOT lock-step

A real, frustrated user rambles, gives a vague symptom, and asks "wait, which one?" mid-step. The agent must hold a conversation, not read a script. So the playbook is a *spine the brain walks at the user's pace*, not a fixed sequence advanced one notch per turn. Three phases:

- **Intake / diagnose (before step 1).** On the first messages the brain's job is to *understand the problem*, not to start instructing. It can ask 1–3 clarifying questions ("Is this on your work laptop or phone? What exactly do you see?") and only commits to a playbook once it's confident. A vague "my stuff won't open" → the agent narrows it down first.
- **Within a step — stay and answer follow-ups.** While on a step, the user can ask anything ("I don't see that button," "what's a sidebar?"). The brain **stays on the same step** and answers, re-explaining or sending another annotated screenshot. It does **not** advance just because a turn happened.
- **Advance only on confirmation.** The brain moves to the next step only when the user (or the vision model reading a fresh screenshot) confirms the current step is actually done. If the user is stuck after 2 tries, it offers a clip/escalates.

Concretely, the brain returns a **decision, not a step pointer**. Each turn it picks exactly one action and whether to move:
```json
{ "say": "No worries — the sidebar is the strip down the left side. See it?",
  "action": "clarify",                       // clarify | stay | advance | annotate | resolve | escalate
  "advance": false,                          // orchestrator only bumps step_idx when true
  "scenario_locked": true,                   // false during intake, before a playbook is chosen
  "annotate_target": "sidebar" }
```
The orchestrator's loop becomes: *give the brain the full transcript + current step + any screen reading → do what it says → bump `step_idx` only if `advance` is true.* The transcript (already stored in Redis per call) is what gives the brain memory of the back-and-forth, so follow-ups have context.

> **Starter-code note:** `orchestrator.py` implements this model. Phase 1 (`gmi.diagnose`) converses and only locks a scenario once the brain is confident — otherwise it asks one clarifying question and stays in intake. Phase 2 (`gmi.decide`) returns an `advance` flag, and the orchestrator bumps `step_idx` **only** when `advance` is true (with a safety rail that never advances off a "send a screenshot" step until an image actually arrives). Both phases fall back gracefully if the brain is unreachable — intake drops to keyword matching, steps drop to the scripted line.

## 4. Model choices (from the GMI catalog you have)

| Job | Pick | Why | ~Price |
|---|---|---|---|
| Brain / step logic | **Gemini 3 Flash** | fast, cheap, strong instruction-following | $0.50 in / $3.00 out per 1M |
| Brain (fallback) | **GPT-5.4-mini** | reliable structured output | $0.75 / $4.50 |
| Vision (read screenshot) | **Qwen3-VL-235B-Instruct** | strong image→text, cheap | $0.30 / $1.40 |
| Vision (fallback) | **Gemini 3 Flash** (image-to-text) | one model for brain+vision if you want to simplify | — |
| Voice STT + TTS | **Deepgram** | you have credits; lowest latency | credits |
| Memory / state / cache | **Redis** | state + symptom→fix cache + clip index | infra |
| Annotation | **Pillow** (server) or canvas (client) | draw arrows — no model, instant, free | $0 |
| Walkthrough — steps | **Gemini 3 Flash** (reuse brain) | distill transcript → clean numbered steps | (brain) |
| Walkthrough — narration | **Deepgram TTS** or MiniMax TTS | voice over the real screenshots | credits |
| Walkthrough — render | HTML/PDF now; **ffmpeg** + frames for MP4 (stretch) | assemble real screenshots, not generated UI | $0 / infra |

**Latency budget per turn (target < 2.5s):** STT ~300ms + brain ~600ms + (vision ~800ms only when an image is sent) + TTS ~400ms. Keep the brain prompt small; stream TTS as text arrives.

## 5. The Redis "learning" loop (your differentiator — make it visible)

Four Redis structures:

- `playbook:*` — curated, vetted step chains you seed at the start (the only source of instructions; prevents hallucinated IT advice).
- `state:{call_id}` — current step, history, last screenshot reading. TTL on call end.
- `learned:{symptom_hash}` — after a successful resolution, cache the winning step chain keyed by a normalized/embedded symptom.
- `walkthrough:{walkthrough_id}` + `symptom_hash → walkthrough_id` — the **walkthrough library**: the finished personalized guides (real annotated screenshots + steps + narration). On a new call, check this **first**; a hit serves a real, human-validated guide in one turn at ~zero cost.

**Why it's the moat:** the walkthrough library is a knowledge base that writes itself out of real resolutions. Every solved ticket either reuses an existing guide (instant, ~free) or produces a new one that makes the next ticket free. Deflection rate climbs and unit cost falls the longer a customer runs it. Show the cache-hit counter and the growing library size on the demo dashboard.

## 6. Safety rails (say these out loud in the demo)

- **Closed playbook, not open generation.** The brain selects from vetted steps; it cannot invent destructive IT actions. Anything outside the library → **escalate to a human** with the transcript.
- **Vision confirms state before each consequential step** ("I see you're about to delete — that's not the fix, let's back up").
- **No credentials handled.** Agent guides the user to do auth/password actions themselves; never asks for or stores secrets.

## 7. AgentBox deployment (mandatory integration)

- Package backend as a **Docker** image (orchestrator + Redis client; Redis as a managed/side container or GMI-provided).
- Define the agent's input/output contract for the AgentBox listing (audio + image in, audio + annotated image out).
- Publish to **AgentBox** → usage-based, zero idle cost. Confirm details in the GMI Cloud Discord (#agentbox). This is required to qualify — get a "hello world" deploy working early, before the agent is finished.

## 8. Tech stack summary

- **Frontend:** single HTML/JS page — WebAudio for mic, WebSocket to backend, `<img>` for annotated screenshots, a counter div. Keep it one file.
- **Backend:** Python (FastAPI + websockets) or Node — Deepgram SDK, GMI API (one key, OpenAI-compatible), `redis-py`, Pillow.
- **Infra:** Docker → AgentBox. Redis local container for the demo.
- **Secrets:** GMI API key, Deepgram key in env vars.
