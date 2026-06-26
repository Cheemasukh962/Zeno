"""Lightweight checks for the perception layer. No pytest, no API keys, no Redis needed.
L1/L2/L3 is driven solely by task complexity; retrieval is normalized + confidence-banded.
Run:

    python -m backend.test_perception
"""
from . import gmi, perception


def _force_offline():
    """Make the LLM path unavailable so the keyword scorer is exercised deterministically."""
    gmi.diagnose = lambda *a, **k: {"_error": "offline-test"}  # noqa: E731


def test_normalize():
    n = perception._normalize("Won't OPEN, can't access!")
    assert "wont open" in n and "cant access" in n
    assert "'" not in n


def test_complexity_to_level():
    """Complexity maps 1:1 to level. Deterministic, no LLM. risk:'high' -> 3."""
    sc = perception._score_complexity
    assert sc(None, False, 0.0, False) == 3                        # unknown -> escalate
    assert sc("shared_drive_not_opening", True, 0.2, False) == 3   # below floor -> escalate
    assert sc("shared_drive_not_opening", True, 0.9, False) == 2   # known, uncached -> guided
    assert sc("shared_drive_not_opening", True, 0.9, True) in (1, 3)  # cached -> auto (or pinned)
    assert sc("account_compromised", True, 0.9, False) == 3        # risk:'high' -> escalate


def test_known_drive_locks_l2():
    _force_offline()
    p = perception.perceive("my files wont open from the shared network drive")
    assert p.locked and p.scenario_key == "shared_drive_not_opening"
    assert p.level == 2 and p.route == "guided"


def test_apostrophe_free_still_matches():
    _force_offline()
    p = perception.perceive("cant open files on the network drive")  # no apostrophes
    assert p.locked and p.scenario_key == "shared_drive_not_opening" and p.level == 2


def test_account_compromise_escalates_l3():
    _force_offline()
    p = perception.perceive("i think my account got hacked, suspicious login")
    assert p.locked and p.scenario_key == "account_compromised"
    assert p.level == 3 and p.route == "escalate"


def test_vpn_distinct_from_drive():
    _force_offline()
    p = perception.perceive("the vpn wont connect, no remote access")
    assert p.locked and p.scenario_key == "vpn_not_connecting"
    assert p.level == 2 and p.route == "guided"


def test_unrelated_is_unknown_l3():
    _force_offline()
    p = perception.perceive("my laptop fan is making a grinding noise")
    assert not p.match and p.level == 3 and p.route == "escalate"


def test_vague_does_not_lock():
    _force_offline()
    p = perception.perceive("my stuff wont open")
    assert not p.locked  # weak/ambiguous signal -> stay in intake, ask


def main():
    checks = [test_normalize, test_complexity_to_level, test_known_drive_locks_l2,
              test_apostrophe_free_still_matches, test_account_compromise_escalates_l3,
              test_vpn_distinct_from_drive, test_unrelated_is_unknown_l3, test_vague_does_not_lock]
    for check in checks:
        check()
        print(f"PASS  {check.__name__}")
    print(f"\n{len(checks)} checks passed.")


if __name__ == "__main__":
    main()
