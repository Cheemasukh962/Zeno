"""Accuracy harness for the perception layer — the provable bar for "near-perfect"
classification. Forces the OFFLINE keyword path (no API keys, no Redis, instant and
deterministic) and checks a labeled set of real-sounding utterances. Run:

    python -m backend.eval_classification

Exits non-zero if accuracy < 100%, so it can gate a commit. Expectation grammar:
  "scenario:LEVEL"  -> must lock that scenario at that level (e.g. shared_drive...:2)
  "escalate"        -> unknown/risky -> not locked-as-guided; route must be escalate (L3)
  "clarify"         -> too vague/ambiguous -> must NOT lock (stay in intake)
"""
from . import gmi, perception

# (utterance, expectation)
CASES: list[tuple[str, str]] = [
    # --- shared drive -> L2 guided (paraphrases, apostrophe-free, screenshots of real phrasing) ---
    ("my files won't open from the shared drive", "shared_drive_not_opening:2"),
    ("cant open files on the network drive", "shared_drive_not_opening:2"),
    ("the shared folder is gone and my files wont open", "shared_drive_not_opening:2"),
    ("i cant access the mapped drive anymore", "shared_drive_not_opening:2"),
    ("network drive is disconnected, cant reach my files", "shared_drive_not_opening:2"),
    ("the shared network drive wont open", "shared_drive_not_opening:2"),

    # --- vpn -> L2 guided (distinct scenario, must not collide with drive) ---
    ("my vpn wont connect", "vpn_not_connecting:2"),
    ("cant connect to vpn from home", "vpn_not_connecting:2"),
    ("vpn is down and i have no remote access", "vpn_not_connecting:2"),
    ("the vpn keeps failing to connect", "vpn_not_connecting:2"),

    # --- account compromise -> L3 escalate (pinned risky) ---
    ("i think i got hacked", "escalate"),
    ("there was a suspicious login on my account", "escalate"),
    ("someone changed my password without me", "escalate"),
    ("i think someone is in my account, possible phishing", "escalate"),

    # --- genuinely unknown -> L3 escalate ---
    ("my laptop fan is making a grinding noise", "escalate"),
    ("the printer is jammed again", "escalate"),
    ("my screen keeps flickering", "escalate"),
    ("excel keeps crashing when i open a big file", "escalate"),

    # --- vague / ambiguous -> clarify (must NOT lock) ---
    ("my stuff wont open", "clarify"),
    ("its broken", "clarify"),
    ("nothing is working today", "clarify"),
    ("i need some help with my computer", "clarify"),
]


def _check(p, expectation: str) -> tuple[bool, str]:
    got = f"L{p.level}/{p.route}/{p.scenario_key or '-'}/locked={p.locked}"
    if expectation == "clarify":
        return (not p.locked), got
    if expectation == "escalate":
        return (p.route == "escalate" and p.level == 3), got
    key, lvl = expectation.split(":")
    return (p.locked and p.scenario_key == key and p.level == int(lvl)), got


def main() -> int:
    gmi.diagnose = lambda *a, **k: {"_error": "offline-eval"}  # force keyword path  # noqa: E731
    passed = 0
    for text, expectation in CASES:
        p = perception.perceive(text)
        ok, got = _check(p, expectation)
        passed += ok
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {expectation:<28} <- {text!r}")
        if not ok:
            print(f"         got: {got}")
    total = len(CASES)
    acc = passed / total * 100
    print(f"\nAccuracy: {passed}/{total} = {acc:.1f}%")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
