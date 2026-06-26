import copy
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from backend import orchestrator
from backend.perception import Perception


class FakeStore:
    def __init__(self):
        self.states = {}
        self.escalations = []
        self.scenarios = {
            "account_compromised": {
                "title": "Possible account compromise",
                "risk": "high",
                "steps": [{"id": "sec_01", "say": "Escalating.", "action": "escalate"}],
            },
            "vpn_not_connecting": {
                "title": "Reconnect your VPN",
                "steps": [
                    {"id": "vpn_01", "say": "Send a screenshot.", "action": "request_screenshot"},
                    {"id": "vpn_02", "say": "Sign out and back in.", "action": "say"},
                    {"id": "vpn_03", "say": "Press Connect.", "action": "say"},
                ],
            },
        }

    def load_state(self, call_id):
        return copy.deepcopy(self.states.get(call_id, {
            "call_id": call_id,
            "scenario": None,
            "step_idx": 0,
            "transcript": [],
            "shots": [],
        }))

    def save_state(self, state):
        self.states[state["call_id"]] = copy.deepcopy(state)

    def get_scenario(self, key):
        return copy.deepcopy(self.scenarios.get(key))

    def find_cached_walkthrough(self, _scenario_key):
        return None

    def record_deflection(self, cache_hit):
        return None

    def save_walkthrough(self, scenario_key, guide):
        return f"wt_{scenario_key}"

    def metrics(self):
        return {"deflected": 0, "cache_hits": 0, "escalated": len(self.escalations)}

    def create_escalation(self, call_id, scenario_key, transcript, reason, perception=None):
        scenario = self.scenarios.get(scenario_key, {})
        ticket = {
            "id": f"esc_{len(self.escalations) + 1}",
            "status": "open",
            "priority": "urgent" if scenario.get("risk") == "high" else "normal",
            "call_id": call_id,
            "scenario_key": scenario_key,
            "reason": reason,
            "summary": transcript[-1] if transcript else "",
            "transcript": transcript[-30:],
            "perception": perception or {},
        }
        self.escalations.append(ticket)
        return ticket


class OrchestratorTests(unittest.TestCase):
    def _common_patches(self, fake):
        stack = ExitStack()
        stack.enter_context(patch.object(orchestrator.store, "load_state", fake.load_state))
        stack.enter_context(patch.object(orchestrator.store, "save_state", fake.save_state))
        stack.enter_context(patch.object(orchestrator.store, "get_scenario", fake.get_scenario))
        stack.enter_context(patch.object(orchestrator.store, "find_cached_walkthrough",
                                         fake.find_cached_walkthrough))
        stack.enter_context(patch.object(orchestrator.store, "record_deflection",
                                         fake.record_deflection))
        stack.enter_context(patch.object(orchestrator.store, "save_walkthrough",
                                         fake.save_walkthrough))
        stack.enter_context(patch.object(orchestrator.store, "metrics", fake.metrics))
        stack.enter_context(patch.object(orchestrator.store, "create_escalation",
                                         fake.create_escalation))
        stack.enter_context(patch.object(orchestrator.deepgram_client, "synthesize",
                                         lambda _say: None))
        return stack

    def test_l3_route_creates_escalation_ticket(self):
        fake = FakeStore()

        def perceive(_transcript, source="live"):
            return Perception(
                scenario_key="account_compromised",
                match=True,
                confidence=0.95,
                locked=True,
                say="This needs a security specialist.",
                complexity=3,
                level=3,
                route="escalate",
                source=source,
            )

        with self._common_patches(fake), patch.object(orchestrator.perception, "perceive", perceive):
            result = orchestrator.handle_turn("call-sec", "I think my account got hacked", None)

        self.assertEqual(result["action"], "escalate")
        self.assertEqual(result["escalation"]["priority"], "urgent")
        self.assertEqual(result["escalation"]["scenario_key"], "account_compromised")
        self.assertEqual(fake.states["call-sec"]["escalation"]["id"], "esc_1")

    def test_followup_does_not_advance_but_confirmation_does(self):
        fake = FakeStore()
        fake.states["call-vpn"] = {
            "call_id": "call-vpn",
            "scenario": "vpn_not_connecting",
            "locked": True,
            "step_idx": 1,
            "transcript": [],
            "shots": [],
        }
        decision = {"say": "Try signing out and back in.", "action": "say", "advance": True}

        with self._common_patches(fake), patch.object(orchestrator.gmi, "decide",
                                                      lambda *_args: decision):
            result = orchestrator.handle_turn("call-vpn", "Where is that button?", None)
            self.assertEqual(result["action"], "say")
            self.assertEqual(fake.states["call-vpn"]["step_idx"], 1)

            orchestrator.handle_turn("call-vpn", "Done, I signed in.", None)
            self.assertEqual(fake.states["call-vpn"]["step_idx"], 2)

    def test_screenshot_step_can_advance_after_image(self):
        fake = FakeStore()
        fake.states["call-shot"] = {
            "call_id": "call-shot",
            "scenario": "vpn_not_connecting",
            "locked": True,
            "step_idx": 0,
            "transcript": [],
            "shots": [],
        }

        with self._common_patches(fake), \
                patch.object(orchestrator.gmi, "read_screen", lambda _img: "VPN app screen"), \
                patch.object(orchestrator.gmi, "decide",
                             lambda *_args: {"say": "Thanks, I can see it.",
                                             "action": "say",
                                             "advance": True}):
            result = orchestrator.handle_turn("call-shot", "", b"fake image")

        self.assertFalse(result["request_screenshot"])
        self.assertEqual(fake.states["call-shot"]["step_idx"], 1)


if __name__ == "__main__":
    unittest.main()
