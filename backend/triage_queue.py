"""CLI: batch-triage a ticket file through the perception layer.

    python -m backend.triage_queue backend/data/tickets.json

Prints one line per ticket: id, retrieved scenario, merged level, and route.
Runs with NO API keys (perception degrades to rule fallbacks).
"""
import sys

from .ticket_queue import MockTicketQueue, triage_ticket


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 1
    queue = MockTicketQueue(argv[0])
    for ticket in queue.fetch():
        r = triage_ticket(ticket)
        p = r["perception"]
        flags = []
        if p["cached"]:
            flags.append("cached")
        if p["degraded"]:
            flags.append("no-LLM")
        suffix = f" [{', '.join(flags)}]" if flags else ""
        print(f"{r['id']:>8}  L{r['level']}  {r['route']:<12} "
              f"scenario={r['scenario_key'] or '-':<28} "
              f"(complexity={p['complexity']}){suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
