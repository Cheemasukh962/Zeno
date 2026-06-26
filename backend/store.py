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


# ---------- dashboard metrics (the money shot) ----------
COST_PER_TICKET = 20  # industry avg L1 resolution cost, USD

def record_deflection(cache_hit: bool):
    _r.incr("metric:deflected")
    if cache_hit:
        _r.incr("metric:cache_hits")


def metrics() -> dict:
    deflected = int(_r.get("metric:deflected") or 0)
    cache_hits = int(_r.get("metric:cache_hits") or 0)
    return {
        "deflected": deflected,
        "cache_hits": cache_hits,
        "saved_usd": deflected * COST_PER_TICKET,
        "library_size": len(_r.keys("walkthrough:*")),
    }
