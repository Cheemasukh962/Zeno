"""External ticket source adapter. Proves the perception layer is source-agnostic:
a queued ticket runs the SAME classify() path as a live call, just without audio/vision.

Today this reads a mock JSON/CSV file; a real ITSM connector implements TicketSource.fetch
the same way and nothing downstream changes.
"""
import csv
import json
from pathlib import Path
from typing import Iterable, Protocol

from . import perception
from .perception import asdict


class TicketSource(Protocol):
    """Anything that yields tickets as {"id","text","user"?,"channel"?,"ts"?}."""
    def fetch(self) -> Iterable[dict]:
        ...


class MockTicketQueue:
    """Reads a .json (list of tickets) or .csv (DictReader) file and normalizes rows."""

    def __init__(self, path: str):
        self.path = Path(path)

    def fetch(self) -> list[dict]:
        if self.path.suffix.lower() == ".csv":
            with self.path.open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        else:
            rows = json.loads(self.path.read_text(encoding="utf-8"))
        return [self._normalize(i, row) for i, row in enumerate(rows)]

    @staticmethod
    def _normalize(i: int, row: dict) -> dict:
        return {
            "id": row.get("id") or f"T-{i + 1:04d}",
            "text": row.get("text", ""),
            "user": row.get("user"),
            "channel": row.get("channel"),
            "ts": row.get("ts"),
        }


def triage_ticket(ticket: dict) -> dict:
    """Classify one ticket and enrich it with the routing decision."""
    p = perception.perceive(ticket["text"], source="queue", ticket_id=ticket.get("id"))
    return {**ticket, "level": p.level, "route": p.route,
            "scenario_key": p.scenario_key, "perception": asdict(p)}
