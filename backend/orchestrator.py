"""One turn of a call. Two phases:
  1. INTAKE — converse and diagnose until a scenario is locked (no fix steps yet).
  2. GUIDED STEPS — walk the vetted playbook, staying on a step for follow-ups and
     advancing ONLY when the user/screenshot confirms the step is done.
Ties together brain, vision, annotator, walkthrough, and Redis."""
from . import annotator, deepgram_client, gmi, store, walkthrough

RESOLVE_ACTIONS = {"resolve", "resolved"}


def handle_turn(call_id: str, user_text: str, image_bytes: bytes | None) -> dict:
    state = store.load_state(call_id)
    if user_text:
        state["transcript"].append(f"User: {user_text}")

    # ---------- PHASE 1: intake / diagnose (runs until a scenario is locked) ----------
    if not state.get("locked"):
        scenarios = store.list_scenarios()
        keys = {s["key"] for s in scenarios}
        dec = gmi.diagnose(state["transcript"], scenarios)
        key = dec.get("scenario_key")

        if dec.get("_error"):  # brain down → fall back to keyword matching
            kw, _ = store.match_playbook(" ".join(state["transcript"]))
            if kw:
                key, dec = kw, {"scenario_locked": True}

        if dec.get("scenario_locked") and key in keys:
            state["scenario"] = key
            state["locked"] = True
            # MONEY SHOT: if we've solved this before, serve the real guide instantly (~$0).
            cached = store.find_cached_walkthrough(key)
            if cached:
                store.record_deflection(cache_hit=True)
                store.save_state(state)
                return _resp(state, say="I've seen this exact issue before — here's the "
                             "guide that fixed it, ready to go.", cache_hit=True,
                             walkthrough=cached)
            # otherwise fall through and deliver the first guided step this same turn
        else:
            # still vague → ask one clarifying question and stay in intake
            store.save_state(state)
            return _resp(state, action="clarify",
                         say=dec.get("say") or "Tell me a bit more about what's "
                         "happening and I'll walk you through it.")

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
