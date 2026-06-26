"""One turn of a call. Two phases:
  1. INTAKE — converse and diagnose until a scenario is locked (no fix steps yet).
  2. GUIDED STEPS — walk the vetted playbook, staying on a step for follow-ups and
     advancing ONLY when the user/screenshot confirms the step is done.
Ties together brain, vision, annotator, walkthrough, and Redis."""
from dataclasses import asdict

from . import annotator, deepgram_client, gmi, perception, store, walkthrough

RESOLVE_ACTIONS = {"resolve", "resolved"}
MAX_INTAKE_ATTEMPTS = 2  # after this many tries with no identifiable issue → escalate (L3)


def handle_turn(call_id: str, user_text: str, image_bytes: bytes | None) -> dict:
    state = store.load_state(call_id)
    if user_text:
        state["transcript"].append(f"User: {user_text}")

    # ---------- PHASE 1: perception — retrieve + classify (L1/L2/L3), then route ----------
    if not state.get("locked"):
        p = perception.perceive(state["transcript"], source="live")

        if not p.locked:
            state["intake_attempts"] = state.get("intake_attempts", 0) + 1
            # An unidentifiable problem (L3) that we still can't place after a couple of
            # tries → stop looping and escalate to a human. A known-but-unconfirmed issue
            # (route != escalate) keeps clarifying.
            if p.route == "escalate" and state["intake_attempts"] >= MAX_INTAKE_ATTEMPTS:
                state["locked"] = True
                state["perception"] = asdict(p)
                store.save_state(state)
                return _resp(state, action="escalate",
                             say="I'm not able to place this one — let me hand you to a "
                             "human with everything you've told me so far.")
            # still vague → ask one clarifying question and stay in intake
            store.save_state(state)
            return _resp(state, action="clarify",
                         say=p.say or "Tell me a bit more about what's "
                         "happening and I'll walk you through it.")

        state["scenario"] = p.scenario_key
        state["locked"] = True
        state["perception"] = asdict(p)  # persist the classification for routing + dashboard

        if p.route == "escalate":
            # L3 → hand to a human. The orchestration teammate fills in the real hand-off.
            store.save_state(state)
            return _resp(state, action="escalate",
                         say=p.say or "This one needs a human — I'm handing it over with "
                         "your details so you don't have to repeat yourself.")

        if p.route == "auto_resolve":
            # L1 MONEY SHOT: if we've solved this before, serve the real guide instantly (~$0).
            cached = store.find_cached_walkthrough(p.scenario_key)
            if cached:
                store.record_deflection(cache_hit=True)
                store.save_state(state)
                return _resp(state, say="I've seen this exact issue before — here's the "
                             "guide that fixed it, ready to go.", cache_hit=True,
                             walkthrough=cached)
            # cache miss → fall through and deliver the first guided step this same turn

        # route == "guided" (or auto_resolve cache-miss) → fall through to Phase 2

    # ---------- PHASE 2: guided steps (scenario locked) ----------
    scenario = store.get_scenario(state["scenario"])
    steps = scenario["steps"]
    step = steps[min(state["step_idx"], len(steps) - 1)]

    # vision: read a screenshot if the user sent one
    screen_reading = None
    if image_bytes:
        screen_reading = gmi.read_screen(image_bytes)
        state["transcript"].append(f"[screen: {screen_reading}]")

    # brain decides what to say/do AND whether to advance
    decision = gmi.decide(step, state["transcript"], screen_reading)
    say = decision.get("say", step["say"])
    action = decision.get("action", step.get("action", "say"))
    advance = bool(decision.get("advance", False))
    state["transcript"].append(f"Agent: {say}")

    # annotate the screenshot when asked (and one was sent)
    annotated_url = None
    if action == "annotate" and image_bytes:
        target = decision.get("annotate_target") or step.get("annotate_target", "default")
        annotated_url = annotator.annotate(image_bytes, target)["url"]
        state["shots"].append(annotated_url)

    # resolved → build + cache the personalized walkthrough (the centerpiece)
    if action in RESOLVE_ACTIONS:
        guide = walkthrough.build(scenario, state["transcript"], state["shots"])
        store.save_walkthrough(state["scenario"], guide)
        store.record_deflection(cache_hit=False)
        store.save_state(state)
        return _resp(state, say=say, walkthrough=guide)

    # safety rail: never advance off a "send a screenshot" step until we've actually seen one
    if step.get("action") == "request_screenshot" and not image_bytes:
        advance = False

    if advance:
        state["step_idx"] = min(state["step_idx"] + 1, len(steps) - 1)
    store.save_state(state)

    wants_shot = action == "request_screenshot" or (
        step.get("action") == "request_screenshot" and not image_bytes)
    return _resp(state, say=say, action=action, annotated_url=annotated_url,
                 request_screenshot=wants_shot)


def _resp(state, say="", action="say", annotated_url=None, walkthrough=None,
          cache_hit=False, request_screenshot=None):
    audio = deepgram_client.synthesize(say)  # None if TTS unavailable
    return {
        "say": say,
        "action": action,
        "annotated_url": annotated_url,
        "walkthrough": walkthrough,
        "cache_hit": cache_hit,
        "metrics": store.metrics(),
        "has_audio": audio is not None,
        "_audio": audio,  # app.py streams this out separately
        "request_screenshot": (action == "request_screenshot"
                               if request_screenshot is None else request_screenshot),
        "locked": state.get("locked", False),
    }
