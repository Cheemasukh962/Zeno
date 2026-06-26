"""Redis-backed memory: call state, the vetted playbook, learned fixes,
and the walkthrough library (the moat)."""
import hashlib
import json
import os
import time
from pathlib import Path

import redis

_r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)
_PLAYBOOK = json.loads((Path(__file__).parent / "playbook.json").read_text())


# ---------- playbook (vetted instructions only) ----------
def match_playbook(transcript: str):
    """Pick the scenario whose phrases best match what the user said.
    Deliberately simple keyword match — swap for embeddings if time allows."""
    t = transcript.lower()
    best, best_hits = None, 0
    for key, pb in _PLAYBOOK.items():
        hits = sum(1 for p in pb["match_phrases"] if p in t)
        if hits > best_hits:
            best, best_hits = key, hits
    return (best, _PLAYBOOK[best]) if best else (None, None)


def get_scenario(key: str):
    return _PLAYBOOK.get(key)


def list_scenarios() -> list[dict]:
    """Catalog the brain sees during intake, so it can pick (or keep diagnosing)."""
    return [{"key": k, "symptom": pb["symptom"]} for k, pb in _PLAYBOOK.items()]


def symptom_hash(scenario_key: str) -> str:
    return hashlib.sha1(scenario_key.encode()).hexdigest()[:12]


# ---------- per-call state ----------
def load_state(call_id: str) -> dict:
    raw = _r.get(f"state:{call_id}")
    return json.loads(raw) if raw else {"call_id": call_id, "scenario": None,
                                         "step_idx": 0, "transcript": [], "shots": []}


def save_state(state: dict):
    _r.set(f"state:{state['call_id']}", json.dumps(state), ex=3600)


# ---------- walkthrough library (self-building knowledge base) ----------
def find_cached_walkthrough(scenario_key: str):
    """Check this FIRST on a new call. A hit = real guide, instant, ~$0."""
    wid = _r.get(f"symptom:{symptom_hash(scenario_key)}")
    if not wid:
        return None
    raw = _r.get(f"walkthrough:{wid}")
    return json.loads(raw) if raw else None


def save_walkthrough(scenario_key: str, walkthrough: dict) -> str:
    wid = f"wt_{symptom_hash(scenario_key)}"
    walkthrough["id"] = wid
    walkthrough["created"] = time.time()
    _r.set(f"walkthrough:{wid}", json.dumps(walkthrough))
    _r.set(f"symptom:{symptom_hash(scenario_key)}", wid)
    return wid


# ---------- human handoff / escalation queue ----------
def create_escalation(call_id: str, scenario_key: str | None, transcript: list[str],
                      reason: str, perception: dict | None = None) -> dict:
    """Create the human handoff packet an IT specialist can pick up.

    This is intentionally generic: a real Jira/ServiceNow connector can read the same
    Redis ticket payload, while the demo can show the returned id immediately.
    """
    created = time.time()
    seed = f"{call_id}:{created}:{scenario_key or 'unknown'}"
    ticket_id = f"esc_{hashlib.sha1(seed.encode()).hexdigest()[:10]}"
    scenario = get_scenario(scenario_key) if scenario_key else None
    priority = "urgent" if (scenario or {}).get("risk") == "high" else "normal"
    handoff = {
        "id": ticket_id,
        "status": "open",
        "priority": priority,
        "call_id": call_id,
        "scenario_key": scenario_key,
        "scenario_title": (scenario or {}).get("title"),
        "reason": reason,
        "created": created,
        "perception": perception or {},
        "summary": _handoff_summary(transcript, scenario, reason),
        "transcript": transcript[-30:],
    }
    _r.set(f"escalation:{ticket_id}", json.dumps(handoff))
    _r.lpush("escalations:open", ticket_id)
    _r.incr("metric:escalated")
    return handoff


def list_escalations(limit: int = 20) -> list[dict]:
    """Return recent open handoffs for an admin surface or demo check."""
    ids = _r.lrange("escalations:open", 0, max(0, limit - 1))
    tickets = []
    for ticket_id in ids:
        raw = _r.get(f"escalation:{ticket_id}")
        if raw:
            tickets.append(json.loads(raw))
    return tickets


def _handoff_summary(transcript: list[str], scenario: dict | None, reason: str) -> str:
    user_lines = [line.removeprefix("User: ").strip()
                  for line in transcript if line.startswith("User: ")]
    latest = user_lines[-1] if user_lines else "No user description captured."
    title = (scenario or {}).get("title") or "Unknown issue"
    return f"{title}. Reason: {reason}. Latest user detail: {latest}"


# ---------- dashboard metrics (the money shot) ----------
COST_PER_TICKET = 20  # industry avg L1 resolution cost, USD

def record_deflection(cache_hit: bool):
    _r.incr("metric:deflected")
    if cache_hit:
        _r.incr("metric:cache_hits")


def metrics() -> dict:
    deflected = int(_r.get("metric:deflected") or 0)
    cache_hits = int(_r.get("metric:cache_hits") or 0)
    escalated = int(_r.get("metric:escalated") or 0)
    return {
        "deflected": deflected,
        "cache_hits": cache_hits,
        "escalated": escalated,
        "saved_usd": deflected * COST_PER_TICKET,
        "library_size": len(_r.keys("walkthrough:*")),
    }
