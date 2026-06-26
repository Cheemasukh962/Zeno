"""One turn of a call.

Phase 1: perception retrieves and classifies the issue.
Phase 2: guided steps walk a vetted playbook at the user's pace.
"""
from dataclasses import asdict

from . import annotator, deepgram_client, gmi, perception, store, walkthrough

RESOLVE_ACTIONS = {"resolve", "resolved"}
VALID_ACTIONS = {"say", "clarify", "annotate", "request_screenshot", "resolve", "escalate"}
MAX_INTAKE_ATTEMPTS = 2

CONFIRMATION_PHRASES = (
    "done", "did it", "finished", "it worked", "works now", "fixed", "all set",
    "connected", "signed in", "logged in", "opened", "i see it", "files are back",
    "yes", "yeah", "yep",
)
BLOCKING_PHRASES = (
    "not done", "not working", "doesn't work", "doesnt work", "can't", "cant",
    "cannot", "failed", "still", "stuck", "error", "which", "where", "what do i",
    "don't see", "dont see", "no ",
)


def handle_turn(call_id: str, user_text: str, image_bytes: bytes | None) -> dict:
    state = store.load_state(call_id)
    state.setdefault("transcript", [])
    state.setdefault("shots", [])
    state.setdefault("step_idx", 0)

    if user_text:
        state["transcript"].append(f"User: {user_text}")

    if state.get("escalation"):
        ticket = state["escalation"]
        say = ("Your handoff is open. A human specialist has the transcript and "
               f"ticket {ticket['id']}.")
        return _resp(state, say=say, action="escalate", escalation=ticket)

    # ---------- Phase 1: perception and route ----------
    if not state.get("locked"):
        p = perception.perceive(state["transcript"], source="live")

        if not p.locked:
            state["intake_attempts"] = state.get("intake_attempts", 0) + 1
            if p.route == "escalate" and state["intake_attempts"] >= MAX_INTAKE_ATTEMPTS:
                state["locked"] = True
                state["perception"] = asdict(p)
                return _escalate(
                    state,
                    "I'm not able to place this one. Let me hand you to a human with "
                    "everything you've told me so far.",
                    reason="intake could not classify the issue",
                )

            store.save_state(state)
            return _resp(
                state,
                action="clarify",
                say=p.say or "Tell me a bit more about what's happening and I'll help.",
            )

        state["scenario"] = p.scenario_key
        state["locked"] = True
        state["perception"] = asdict(p)

        if p.route == "escalate":
            return _escalate(
                state,
                p.say or "This one needs a human. I'm handing it over with your details "
                "so you don't have to repeat yourself.",
                reason=f"L3 route for {p.scenario_key or 'unknown issue'}",
            )

        if p.route == "auto_resolve":
            cached = store.find_cached_walkthrough(p.scenario_key)
            if cached:
                store.record_deflection(cache_hit=True)
                store.save_state(state)
                return _resp(
                    state,
                    say="I've seen this exact issue before. Here's the guide that fixed it.",
                    cache_hit=True,
                    walkthrough=cached,
                )

    # ---------- Phase 2: guided steps ----------
    scenario = store.get_scenario(state.get("scenario"))
    if not scenario:
        return _escalate(state, "I can't find the right playbook, so I'm handing this to IT.",
                         reason="locked scenario missing from playbook")

    steps = scenario.get("steps") or []
    if not steps:
        return _escalate(state, "This playbook has no guided steps yet, so IT should take it.",
                         reason="scenario has no guided steps")

    step = steps[min(state["step_idx"], len(steps) - 1)]

    screen_reading = None
    if image_bytes:
        screen_reading = gmi.read_screen(image_bytes)
        state["last_screen_reading"] = screen_reading
        state["transcript"].append(f"[screen: {screen_reading}]")

    decision = gmi.decide(step, state["transcript"], screen_reading)
    say = decision.get("say") or step.get("say") or "Let me help with that."
    action = _normalize_action(decision.get("action"), step.get("action", "say"))
    advance = bool(decision.get("advance", False))
    state["transcript"].append(f"Agent: {say}")

    if action == "escalate":
        return _escalate(state, say,
                         reason=f"guided step escalation at {step.get('id')}",
                         agent_recorded=True)

    annotated_url = None
    if action == "annotate" and image_bytes:
        target = decision.get("annotate_target") or step.get("annotate_target", "default")
        annotated_url = annotator.annotate(image_bytes, target)["url"]
        state["shots"].append(annotated_url)

    if action in RESOLVE_ACTIONS:
        guide = walkthrough.build(scenario, state["transcript"], state["shots"])
        store.save_walkthrough(state["scenario"], guide)
        store.record_deflection(cache_hit=False)
        state["resolved"] = True
        store.save_state(state)
        return _resp(state, say=say, action="resolve", walkthrough=guide)

    if step.get("action") == "request_screenshot" and not image_bytes:
        advance = False
    elif advance and not _can_advance(step, user_text, screen_reading, image_bytes):
        advance = False

    if advance:
        state["step_idx"] = min(state["step_idx"] + 1, len(steps) - 1)

    store.save_state(state)

    wants_shot = action == "request_screenshot" or (
        step.get("action") == "request_screenshot" and not image_bytes
    )
    return _resp(
        state,
        say=say,
        action=action,
        annotated_url=annotated_url,
        request_screenshot=wants_shot,
    )


def _resp(state, say="", action="say", annotated_url=None, walkthrough=None,
          cache_hit=False, request_screenshot=None, escalation=None):
    audio = deepgram_client.synthesize(say)
    return {
        "say": say,
        "action": action,
        "annotated_url": annotated_url,
        "walkthrough": walkthrough,
        "escalation": escalation,
        "cache_hit": cache_hit,
        "metrics": store.metrics(),
        "has_audio": audio is not None,
        "_audio": audio,
        "request_screenshot": (action == "request_screenshot"
                               if request_screenshot is None else request_screenshot),
        "locked": state.get("locked", False),
    }


def _escalate(state: dict, say: str, reason: str,
              agent_recorded: bool = False) -> dict:
    if say and not agent_recorded:
        state["transcript"].append(f"Agent: {say}")
    ticket = store.create_escalation(
        call_id=state["call_id"],
        scenario_key=state.get("scenario"),
        transcript=state["transcript"],
        reason=reason,
        perception=state.get("perception"),
    )
    state["escalation"] = ticket
    store.save_state(state)
    return _resp(state, say=say, action="escalate", escalation=ticket)


def _normalize_action(action: str | None, fallback: str = "say") -> str:
    normalized = (action or fallback or "say").strip().lower()
    if normalized in RESOLVE_ACTIONS:
        return "resolve"
    if normalized in {"stay", "advance"}:
        return "say"
    if normalized not in VALID_ACTIONS:
        return fallback if fallback in VALID_ACTIONS else "say"
    return normalized


def _can_advance(step: dict, user_text: str, screen_reading: str | None,
                 image_bytes: bytes | None) -> bool:
    if step.get("action") == "request_screenshot":
        return image_bytes is not None

    text = f" {user_text or ''} {screen_reading or ''} ".lower()
    if not text.strip():
        return False
    if any(phrase in text for phrase in BLOCKING_PHRASES):
        return False
    return any(phrase in text for phrase in CONFIRMATION_PHRASES)
