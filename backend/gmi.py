"""LLM brain + vision via GMI Cloud (OpenAI-compatible endpoint).
One API key, swap models by name from the GMI catalog."""
import base64
import json
import os

from openai import OpenAI

_client = OpenAI(
    api_key=os.getenv("GMI_API_KEY", "missing"),
    base_url=os.getenv("GMI_BASE_URL", "https://api.gmi-serving.com/v1"),
)
BRAIN = os.getenv("GMI_BRAIN_MODEL", "google/gemini-3-flash-preview")
VISION = os.getenv("GMI_VISION_MODEL", "google/gemini-3-flash-preview")

INTAKE_SYSTEM = """You are Tier Zero, a calm, patient IT helpdesk agent for non-technical users.
A user just contacted you with a problem. Your FIRST job is to UNDERSTAND it - do NOT give fix steps yet.
You are given the conversation so far and a list of known issues you can resolve.
- If you are confident which known issue this is, commit to it (lock it).
- If it is still vague, ask exactly ONE short, friendly clarifying question.
Never ask for passwords. Speak in 1-2 short, plain sentences.
Return STRICT JSON:
{"say": "<what to speak>",
 "scenario_key": "<the matching key from the list, or null if not sure yet>",
 "scenario_locked": <true ONLY if you are committing to that scenario now>}"""

STEP_SYSTEM = """You are Tier Zero, a calm, patient IT helpdesk agent for non-technical users.
You are guiding the user through a known fix, ONE vetted step at a time. NEVER invent steps -
only guide the current step you are given. Never ask for passwords; the user types those.
A real user gets confused and asks follow-up questions. When they do, STAY on the current step
and re-explain - do not move on. Speak in 1-2 short, plain sentences.
You are given: the current step, the conversation, and the latest screen reading. Decide THIS turn:
- action say or clarify: answer a question or re-explain. advance is false.
- action request_screenshot: ask for a screenshot. advance is false until one arrives.
- action annotate: draw on their screenshot to point at the control. advance is false unless also done.
- action resolve: the whole problem is now fixed.
- action escalate: user is stuck after retries, or asking something off-script.
Set advance to true ONLY when the user or the screen reading confirms the CURRENT step is
actually done and you should move to the next one. Otherwise advance is false.
Return STRICT JSON:
{"say": "<what to speak>",
 "action": "say | clarify | request_screenshot | annotate | resolve | escalate",
 "advance": <bool>,
 "annotate_target": "<label of the control to circle, or null>"}"""

CONFIRMATION_PHRASES = (
    "done", "did it", "finished", "it worked", "works now", "fixed", "all set",
    "connected", "signed in", "logged in", "opened", "yes", "yeah", "yep",
)
BLOCKING_PHRASES = (
    "not working", "doesn't work", "doesnt work", "can't", "cant", "cannot",
    "failed", "still", "stuck", "error", "which", "where", "don't see", "dont see",
)


def diagnose(transcript: list[str], scenarios: list[dict]) -> dict:
    """Intake phase: decide whether we know the issue yet, or ask a clarifying question."""
    convo = "\n".join(transcript[-8:])
    catalog = "\n".join(f"- {s['key']}: {s['symptom']}" for s in scenarios)
    user = (f"KNOWN ISSUES YOU CAN RESOLVE:\n{catalog}\n\n"
            f"CONVERSATION SO FAR:\n{convo}\n\nReturn the JSON.")
    try:
        resp = _client.chat.completions.create(
            model=BRAIN,
            messages=[{"role": "system", "content": INTAKE_SYSTEM},
                      {"role": "user", "content": user}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:  # noqa: BLE001 - caller falls back to keyword match
        return {"say": "", "scenario_key": None, "scenario_locked": False, "_error": str(e)}


def decide(step: dict, transcript: list[str], screen_reading: str | None) -> dict:
    """One guided-step brain turn. Returns {say, action, advance, annotate_target}."""
    convo = "\n".join(transcript[-8:])
    user = (f"CURRENT PLAYBOOK STEP:\n{json.dumps(step)}\n\n"
            f"CONVERSATION SO FAR:\n{convo}\n\n"
            f"LATEST SCREEN READING: {screen_reading or 'none'}\n\n"
            f"Return the JSON decision.")
    try:
        resp = _client.chat.completions.create(
            model=BRAIN,
            messages=[{"role": "system", "content": STEP_SYSTEM},
                      {"role": "user", "content": user}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:  # noqa: BLE001 - never let the call die mid-demo
        act = step.get("action", "say")
        confirmed = _looks_confirmed(transcript, screen_reading)

        if act == "request_screenshot":
            if screen_reading:
                return {"say": "Thanks, I can see your screen. Let's keep going.",
                        "action": "say",
                        "advance": True,
                        "annotate_target": None,
                        "_error": str(e)}
            return {"say": step.get("say", "Can you send me a screenshot?"),
                    "action": "request_screenshot",
                    "advance": False,
                    "annotate_target": None,
                    "_error": str(e)}

        if act in ("resolve", "resolved"):
            return {"say": step.get("say", "You're all set."),
                    "action": "resolve",
                    "advance": False,
                    "annotate_target": None,
                    "_error": str(e)}

        return {"say": step.get("say", "Let me help with that."),
                "action": act,
                "advance": confirmed,
                "annotate_target": step.get("annotate_target"),
                "_error": str(e)}


def _looks_confirmed(transcript: list[str], screen_reading: str | None) -> bool:
    last_user = next((line for line in reversed(transcript)
                      if line.startswith("User: ")), "")
    text = f" {last_user} {screen_reading or ''} ".lower()
    if not text.strip():
        return False
    if any(phrase in text for phrase in BLOCKING_PHRASES):
        return False
    return any(phrase in text for phrase in CONFIRMATION_PHRASES)


def read_screen(image_bytes: bytes) -> str:
    """Vision: describe what's on the user's screenshot."""
    b64 = base64.b64encode(image_bytes).decode()
    try:
        resp = _client.chat.completions.create(
            model=VISION,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": "Describe this computer screen for an IT agent: "
                 "which app/window, what's selected, and any error. Be concise."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ]}],
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:  # noqa: BLE001
        return f"(vision unavailable: {e})"


def summarize_steps(transcript: list[str], scenario_title: str) -> list[str]:
    """Distill the resolved conversation into clean numbered steps for the guide."""
    convo = "\n".join(transcript)
    try:
        resp = _client.chat.completions.create(
            model=BRAIN,
            messages=[{"role": "system", "content":
                       "Turn this resolved IT support call into 3-6 short numbered steps a "
                       "non-technical person can follow next time. Return JSON: {\"steps\": [\"...\"]}"},
                      {"role": "user", "content": f"Title: {scenario_title}\n\n{convo}"}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content).get("steps", [])
    except Exception:  # noqa: BLE001
        title = scenario_title.lower()
        if "vpn" in title:
            return ["Open your VPN app and check the connection screen",
                    "Sign out completely, then sign back in with your work account",
                    "Select your company profile and press Connect",
                    "If it still fails, toggle Wi-Fi off and on once, then retry"]
        return ["Open Finder or File Explorer",
                "Reconnect the network drive from the sidebar",
                "Sign in when prompted using your usual work account",
                "Open the shared folder to confirm your files are back"]
