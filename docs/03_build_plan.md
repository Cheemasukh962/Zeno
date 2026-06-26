# Tier Zero — Hour-by-Hour Build Plan

Beta Fund Hackathon · Fri June 26 · AWS Builder Loft · **Hard submission 4:30 PM** · 3-min demo

**Golden rule:** build ONE flow end-to-end and make it real. A single ticket resolved live — voice in, screenshot read, arrow drawn, voice out, "$ saved" counter ticks — beats five half-features. Cut ruthlessly toward that.

---

## Before you arrive (commute / 9:30 check-in)

- [ ] Join GMI Discord (#agentbox) — get API key, AgentBox deploy steps, credits. (discord.gg/mbYhCJSbF6)
- [ ] Confirm Deepgram key + credits work (quick STT curl test on your phone).
- [ ] Pick the ONE demo scenario. Recommended: **"My files won't open from the shared drive."** Visual, non-technical, perfect for screenshot-annotation.
- [ ] Bring a valid **physical photo ID** (digital not accepted). No bike/scooter parking inside.

## 9:30–11:10 — Check-in, workshops, setup (no real coding yet)

- [ ] Team formation if solo and you want a second builder.
- [ ] Attend the **GMI/AgentBox workshop (10:40)** — this is your mandatory integration; learn the deploy path now.
- [ ] During talks, scaffold the repo: empty FastAPI backend, one HTML page, `.env` with GMI + Deepgram keys, `redis` running locally.
- [ ] **De-risk the hard part first:** get a "hello world" Docker container deployed to AgentBox *before* the agent works. If AgentBox fights you, you want to know at 11, not 4.

## 11:10–12:00 — Build Phase 1: the voice loop (the spine)

Goal: **talk to it and hear it talk back**, no intelligence yet.
- [ ] Browser: mic capture → WebSocket → backend.
- [ ] Backend: Deepgram STT → echo text to **Gemini 3 Flash** with a stub system prompt → Deepgram TTS → audio back to browser.
- [ ] Success = you say "hello," it replies in voice. **If this works, you have a demo skeleton.**

## 12:00–1:00 — Lunch (working lunch — keep it half-on)

- [ ] Seed the **playbook in Redis**: write out the 4–6 vetted steps for the shared-drive scenario as a `symptom → steps` chain. This is your "knowledge," do it by hand, no fancy retrieval.
- [ ] Capture the **2–3 real screenshots** of each step of the scenario (the "before" broken screen + the screens for each fix step). These are the frames your walkthrough will be built from — get clean ones now.

## 1:00–2:30 — Build Phase 2: vision + the brain

Goal: agent reads a screenshot and picks the right step.
- [ ] Add "send screenshot" upload to the widget.
- [ ] Backend: image → **Qwen3-VL** (or Gemini 3 Flash vision) → description string.
- [ ] Brain prompt: given transcript + screen description + current playbook step, return `{say, action, step_id}` as JSON. Walk through the playbook step by step.
- [ ] Wire state into Redis so it remembers which step the call is on.

## 2:30–3:00 — Build Phase 3: the annotation payoff

Goal: the visual wow — agent draws on the user's own screenshot.
- [ ] Pillow: draw a red box/arrow at a target location on the uploaded image, return URL, display in widget.
- [ ] For the demo you can hardcode the target coordinates for your one scenario — **this is allowed and smart.** It looks magical; nobody checks if the box position is computed or fixed.

## 3:00–3:35 — Build Phase 4: the walkthrough generator (the centerpiece)

Goal: at resolution, hand the user a personalized guide made of their own screenshots. **Build the illustrated version, not video.**
- [ ] On `action: "resolved"`, collect the ordered annotated screenshots from the call + the transcript.
- [ ] Brain call: transcript → clean numbered steps. Pair each step with its screenshot.
- [ ] Render an **illustrated guide** (single HTML page or PDF): step text + annotated image + a "play narration" button (Deepgram/MiniMax TTS of the steps). Display it in the widget with a download link.
- [ ] Cache it in Redis under `symptom_hash → walkthrough_id`. **Stretch only if ahead:** stitch frames + TTS into an MP4 with ffmpeg. Do NOT generate UI footage with a video model.

## 3:35–4:00 — Build Phase 5: the money shot

Goal: make the value undeniable on screen.
- [ ] Dashboard counter: **"Tickets deflected: 1 · Est. saved: $20"** + line "At 4,000 tickets/mo, 40% deflection = ~$384K/yr."
- [ ] The **cache-hit demo**: run the same ticket twice. Second time, the orchestrator finds the cached walkthrough and serves it instantly — "that one cost ~$0; the library wrote itself."

## 4:00–4:15 — Deploy + freeze

- [ ] Final Docker build → push to **AgentBox**, confirm it runs there (required to qualify).
- [ ] **Freeze code at 4:15.** Do not add features after this. Stability > features for a live demo.
- [ ] Submit before 4:30 hard deadline. Submit early; you can't submit late.

## 4:15–4:30 — Demo rehearsal

- [ ] Run the full 3-min script twice. Time it. Have a **pre-recorded screen capture** as backup in case live audio/wifi fails on stage.

---

## The 3-minute demo script

> **0:00–0:20 — Hook (the money).** "Half to 80% of IT tickets are stuff users could fix themselves — and each one costs about $20 of an engineer's time. The two companies that solved this for technical users, Moveworks and Aisera, just got acquired for billions. But text chatbots still fail the people who need help most: the non-technical ones who can't even describe the problem."
>
> **0:20–2:00 — Live demo (one flow, real).** Pick up your phone, call into the widget, sound frustrated: *"Hi, my files won't open from the shared drive and I have a meeting in ten minutes."* Agent responds calmly by voice, asks for a screenshot. You send it. Agent: *"I can see it — your network drive isn't mounted. Tap the button I've circled."* — annotated screenshot appears. One more step. **Resolved.** Counter ticks: *Deflected: 1 · Saved: $20.*
>
> **2:00–2:30 — The walkthrough + the compounding twist.** As the call resolves, the agent says "I've turned that into a guide you can keep" — a personalized walkthrough made of *their own screenshots* with numbered steps appears. Then: "And watch what happens for the next person with this issue." Re-run → the agent serves that same real guide instantly from the Redis library. "That one cost essentially nothing. Every ticket either reuses a guide or writes a new one — the knowledge base builds itself."
>
> **2:30–3:00 — The ask.** "Tier Zero — the agent that resolves tickets before Tier 1. Voice and vision for the frontline worker text bots abandon. Live on AgentBox today, hireable per resolution. At one mid-size customer that's ~$384K a year saved. We're raising to put a Tier Zero in front of every helpdesk that lost Moveworks."

## Scope cuts if you fall behind (in order)

1. Drop MP4 entirely — the illustrated HTML/PDF walkthrough is the deliverable. (Already the plan; never reverse this.)
2. Drop the second vision model / fallbacks — one model for brain + vision.
3. Drop real symptom-embedding cache → fake the cache hit with a hardcoded match for the demo.
4. Drop multi-step → make the one scenario 2 steps instead of 4.
5. Drop live mic → type the user input, keep TTS voice out. (Last resort — voice is the wow.)

**Never cut, in priority order:** voice reply → screenshot + annotation → the walkthrough → the cache-hit money shot. That sequence *is* the demo.

## Things that will bite you (pre-empt them)

- **Wifi at venues is unreliable** → pre-record a backup demo video. Non-negotiable.
- **Browser mic permissions** → test in the exact browser you'll demo in, early.
- **AgentBox deploy friction** → that's why it's the 9:30 task, not the 4:00 task.
- **TTS latency feels slow** → stream audio as text generates; keep replies short (1–2 sentences).
- **3-min limit is strict** → rehearse with a timer; cut words, not the money shot.
