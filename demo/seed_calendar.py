"""Synthetic calendar for the public demo.

Dates are generated relative to today so the demo never goes stale, and they
line up with the seeded inbox: the postmortem Dana scheduled, the window
Tomas proposed, the roof work at Kent.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

OUT = Path("data/demo_calendar.json")
TZ = ZoneInfo("America/Los_Angeles")

# (days_from_today, start hour, duration hours, title)
EVENTS = [
    (0, 10, 1.0, "Incident 4471 postmortem"),
    (0, 14, 0.5, "1:1 - Priya Raman"),
    (1, 9, 1.0, "Ops staff meeting"),
    (1, 13, 1.5, "Atlas kickoff call"),
    (2, 11, 1.0, "Port of Seattle - dock allocation review"),
    (3, 9, 0.5, "1:1 - Dana Osei"),
    (3, 15, 1.0, "Q4 review prep"),
    (7, 10, 2.0, "Tacoma site walkthrough"),
    (8, 9, 1.0, "Finance sync - Q1 capital"),
    (15, 10, 1.0, "Forklift certification session - Kent"),
    (21, 18, 3.0, "Holiday party - Maritime Hall"),
]


def main():
    base = datetime.now(TZ).replace(minute=0, second=0, microsecond=0)
    out = []
    for offset, hour, dur, title in EVENTS:
        start = (base + timedelta(days=offset)).replace(hour=hour)
        out.append({
            "summary": title,
            "start": start.isoformat(),
            "end": (start + timedelta(hours=dur)).isoformat(),
        })
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print(f"Wrote {len(out)} synthetic calendar events to {OUT}")


if __name__ == "__main__":
    main()
