"""Perception layer: RETRIEVE (match a problem to the known-issues catalog) +
CLASSIFY it into L1/L2/L3 purely by task COMPLEXITY (who can resolve it):

    L1 = auto_resolve  -> we've solved this exact issue before (cached guide, ~$0)
    L2 = guided        -> a known playbook, not solved before -> guide step by step
    L3 = escalate      -> unknown / risky problem -> hand to a human

The level is computed deterministically from retrieval (no LLM in the scoring), so the
classification is reliable even with NO API keys and NO Redis — important for the demo.
Retrieval itself uses the LLM when available and degrades to keyword matching otherwise.

The orchestrator consumes exactly ONE thing from here: the `Perception` object.
"""
import re
from dataclasses import dataclass, asdict  # noqa: F401  (asdict re-exported for callers)

from . import gmi, store

# confidence bands (tuned against backend/eval_classification.py)
CONF_LLM_LOCK = 0.95   # the LLM explicitly committed to a scenario
LOCK_THRESHOLD = 0.6   # offline confidence at/above which we lock a scenario
FLOOR = 0.3            # below this there is no real match -> unknown -> L3
MARGIN = 0.15          # top two scenarios within this -> ambiguous -> ask which one
CONF_FLOOR = FLOOR     # _score_complexity treats < this (with a match) as unknown

# keyword scorer weights
W_PHRASE = 0.5         # each distinct match_phrase hit
W_KEYWORD = 0.2        # each distinct keyword token hit

ROUTE_BY_LEVEL = {1: "auto_resolve", 2: "guided", 3: "escalate"}


@dataclass
class Perception:
    """The single hand-off contract between perception and orchestration."""
    # --- retrieval ---
    scenario_key: str | None   # matched catalog key, or None
    match: bool                # a known scenario was identified
    confidence: float          # 0.0-1.0 retrieval confidence
    locked: bool               # ready: scenario committed, orchestrator may act
    say: str                   # clarifying question when not locked; routing line when locked
    # --- classification (driven solely by complexity) ---
    complexity: int            # 1=auto-resolvable, 2=guidable, 3=too complex/unknown/risky
    level: int                 # 1 | 2 | 3  -- the L1/L2/L3 (== complexity)
    route: str                 # "auto_resolve" | "guided" | "escalate"
    # --- provenance (demo / dashboard / explainability) ---
    source: str = "live"       # "live" (transcript) | "queue" (external ticket)
    cached: bool = False       # a cached walkthrough exists for scenario_key
    degraded: bool = False     # LLM unavailable -> rule fallback was used
    ticket_id: str | None = None


CLARIFY = "Tell me a bit more about what's happening and I'll help."


def _normalize(text: str) -> str:
    """Lowercase, drop apostrophes (won't -> wont), strip punctuation, pad with spaces so
    phrases/keywords match on whole-word boundaries. Apostrophe-insensitive matching is the
    key accuracy fix: real users type 'wont open' / 'cant access' without the apostrophe."""
    t = text.lower().replace("’", "'").replace("`", "'").replace("'", "")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return f" {t.strip()} "


def _keyword_retrieve(text: str, scenarios: list[dict]) -> list[tuple[str, float]]:
    """Score every scenario by normalized phrase + keyword hits; return [(key, conf), ...]
    sorted high to low. confidence = min(1.0, 0.5*phrase_hits + 0.2*keyword_hits)."""
    padded = _normalize(text)
    ranked: list[tuple[str, float]] = []
    for s in scenarios:
        pb = store.get_scenario(s["key"]) or {}
        phrases = {_normalize(p).strip() for p in pb.get("match_phrases", [])}
        keywords = {_normalize(k).strip() for k in pb.get("keywords", [])}
        phrase_hits = sum(1 for p in phrases if p and f" {p} " in padded)
        keyword_hits = sum(1 for k in keywords if k and f" {k} " in padded)
        conf = min(1.0, W_PHRASE * phrase_hits + W_KEYWORD * keyword_hits)
        if conf > 0:
            ranked.append((s["key"], conf))
    ranked.sort(key=lambda kv: kv[1], reverse=True)
    return ranked


def _friendly(scenario_key: str) -> str:
    pb = store.get_scenario(scenario_key) or {}
    return pb.get("title") or pb.get("symptom") or scenario_key.replace("_", " ")


# ---------------------------------------------------------------- retrieval ----
def retrieve(text: str, scenarios: list[dict] | None = None,
             screen_reading: str | None = None) -> dict:
    """Identify which known issue this is.

    Primary path is gmi.diagnose (the LLM, when GMI_API_KEY is present). When the brain is
    down it degrades to a normalized keyword scorer with confidence bands. `text` may be a
    joined live transcript OR a single ticket body. Returns a dict the classifier consumes.
    """
    if scenarios is None:
        scenarios = store.list_scenarios()
    keys = {s["key"] for s in scenarios}
    convo = text if not screen_reading else f"{text}\n[screen: {screen_reading}]"

    dec = gmi.diagnose([convo], scenarios)
    if not dec.get("_error"):
        # LLM is up: trust its commit decision; otherwise keep its clarifying question.
        key = dec.get("scenario_key")
        if dec.get("scenario_locked") and key in keys:
            return {"scenario_key": key, "match": True, "locked": True,
                    "confidence": CONF_LLM_LOCK, "say": dec.get("say", ""), "degraded": False}
        # The LLM hedged. If the words CLEARLY match a known issue, lock anyway so the demo
        # doesn't waste a turn on an unnecessary clarifying question.
        ranked = _keyword_retrieve(convo, scenarios)
        if ranked and ranked[0][1] >= LOCK_THRESHOLD:
            return {"scenario_key": ranked[0][0], "match": True, "locked": True,
                    "confidence": ranked[0][1], "say": "", "degraded": False}
        return {"scenario_key": key if key in keys else None,
                "match": key in keys, "locked": False,
                "confidence": LOCK_THRESHOLD - 0.01 if key in keys else 0.0,
                "say": dec.get("say") or CLARIFY, "degraded": False}

    # ---- offline: normalized keyword scorer + confidence bands ----
    ranked = _keyword_retrieve(convo, scenarios)
    if not ranked:
        return {"scenario_key": None, "match": False, "locked": False, "confidence": 0.0,
                "say": CLARIFY, "degraded": True}

    top_key, top_conf = ranked[0]
    second_conf = ranked[1][1] if len(ranked) > 1 else 0.0

    # two scenarios too close to call -> ask which one (don't guess)
    if len(ranked) > 1 and (top_conf - second_conf) < MARGIN and second_conf >= FLOOR:
        a, b = _friendly(top_key), _friendly(ranked[1][0])
        return {"scenario_key": None, "match": False, "locked": False, "confidence": top_conf,
                "say": f"Just to make sure I help with the right thing — is this about "
                       f"{a.lower()}, or {b.lower()}?", "degraded": True}

    if top_conf >= LOCK_THRESHOLD:
        return {"scenario_key": top_key, "match": True, "locked": True,
                "confidence": top_conf, "say": "", "degraded": True}

    if top_conf >= FLOOR:
        # a weak single signal -> stay in intake and ask one targeted question
        return {"scenario_key": top_key, "match": True, "locked": False,
                "confidence": top_conf,
                "say": f"Got it — is this about {_friendly(top_key).lower()}?",
                "degraded": True}

    return {"scenario_key": None, "match": False, "locked": False,
            "confidence": top_conf, "say": CLARIFY, "degraded": True}


# ------------------------------------------------------------- classification ----
def _score_complexity(scenario_key: str | None, match: bool,
                      confidence: float, cached: bool) -> int:
    """1 = auto-resolvable, 2 = guidable, 3 = too complex/unknown/risky. Deterministic,
    no LLM, so the L1/L2/L3 label is reliable even when the brain is flaky."""
    if not match or confidence < CONF_FLOOR:
        return 3  # unknown problem -> human
    scenario = store.get_scenario(scenario_key) or {}
    if scenario.get("risk") == "high" or scenario.get("complexity") == 3:
        return 3  # operator pinned this scenario as risky
    if cached:
        return 1  # we've solved this exact issue before -> serve the cached guide
    return 2      # known playbook, not solved before -> guide interactively


def _has_cached_walkthrough(scenario_key: str) -> bool:
    """True if a cached guide exists. Degrades to False if Redis is unreachable, so the
    perception layer still classifies (just never picks the L1 auto_resolve fast-path)."""
    try:
        return store.find_cached_walkthrough(scenario_key) is not None
    except Exception:  # noqa: BLE001 - no Redis in a keyless demo -> treat as no cache
        return False


# ----------------------------------------------------------- classify / entry ----
def classify(text: str, retrieval: dict, source: str = "live",
             ticket_id: str | None = None) -> Perception:
    """Turn a retrieval dict into a full Perception. Source-agnostic: used by both
    live intake and the ticket queue. Level is driven solely by complexity."""
    scenario_key = retrieval["scenario_key"]
    match = retrieval["match"]
    confidence = retrieval["confidence"]

    cached = bool(scenario_key) and _has_cached_walkthrough(scenario_key)
    complexity = _score_complexity(scenario_key, match, confidence, cached)
    level = complexity
    route = ROUTE_BY_LEVEL[level]

    return Perception(
        scenario_key=scenario_key, match=match, confidence=confidence,
        locked=retrieval["locked"], say=retrieval["say"],
        complexity=complexity, level=level, route=route,
        source=source, cached=cached,
        degraded=retrieval["degraded"], ticket_id=ticket_id,
    )


def perceive(transcript, screen_reading: str | None = None,
             source: str = "live", ticket_id: str | None = None) -> Perception:
    """Combined entry point the orchestrator calls each intake turn.

    `transcript` may be a list of lines (live call) or a string (a ticket body).
    """
    text = "\n".join(transcript) if isinstance(transcript, (list, tuple)) else str(transcript)
    retrieval = retrieve(text, screen_reading=screen_reading)
    return classify(text, retrieval, source=source, ticket_id=ticket_id)
