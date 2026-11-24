"""Tools the agent can call.

Each tool is two things: a JSON schema Claude sees (the only description it
gets, so the wording matters), and a Python function that actually runs.
"""
import os
from datetime import datetime, timedelta

from zoneinfo import ZoneInfo

from retrieve import search as vector_search

TZ = ZoneInfo(os.environ.get("AGENT_TZ", "America/Los_Angeles"))
INDEX_DB = os.environ.get("INDEX_DB", "data/index.db")


def now():
    return datetime.now(TZ)


# --- schemas Claude sees -----------------------------------------------------

TOOLS = [
    {
        "name": "search_email",
        "description": (
            "Search the user's email archive and return the most relevant excerpts, "
            "each with subject, sender and date. Use this for any question about what "
            "was said, asked, agreed, promised or decided in email. The search matches "
            "on meaning, not keywords, so pass a natural description of what you want. "
            "Results are ranked by relevance but may include messages that are related "
            "to the topic yet do not answer the question - read them before relying on them."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to look for, in plain language."},
                "k": {"type": "integer", "description": "How many excerpts to return. Default 6, max 12."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "check_calendar",
        "description": (
            "List the user's calendar events between two dates. Use this for anything "
            "about availability, what is scheduled, or whether a proposed time is free. "
            "Email cannot answer these - the calendar is the live source of truth."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Inclusive start, YYYY-MM-DD."},
                "end_date": {"type": "string", "description": "Inclusive end, YYYY-MM-DD."},
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "create_event",
        "description": (
            "Create an event on the user's calendar. Only call this when the user has "
            "clearly asked for something to be scheduled or blocked. Check availability "
            "first if there is any doubt about a conflict."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start": {"type": "string", "description": "Local start time, YYYY-MM-DDTHH:MM."},
                "end": {"type": "string", "description": "Local end time, YYYY-MM-DDTHH:MM."},
                "description": {"type": "string"},
            },
            "required": ["title", "start", "end"],
        },
    },
]


# --- implementations ---------------------------------------------------------

def search_email(query, k=6):
    hits = vector_search(query, k=min(int(k or 6), 12), db=INDEX_DB)
    if not hits:
        return "No matching email found."
    out = []
    for h in hits:
        body = " ".join(h["text"].split())[:700]
        out.append(
            f"--- relevance {h['score']:.2f}\n"
            f"Subject: {h['subject']}\nFrom: {h['sender']}\nDate: {h['date']}\n\n{body}"
        )
    return "\n\n".join(out)


def check_calendar(start_date, end_date):
    from auth import get_calendar_service

    svc = get_calendar_service()
    lo = datetime.fromisoformat(start_date).replace(tzinfo=TZ)
    hi = datetime.fromisoformat(end_date).replace(tzinfo=TZ) + timedelta(days=1)

    resp = svc.events().list(
        calendarId="primary",
        timeMin=lo.isoformat(),
        timeMax=hi.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        maxResults=50,
    ).execute()

    items = resp.get("items", [])
    if not items:
        return f"No events between {start_date} and {end_date}."

    lines = []
    for e in items:
        start = e["start"].get("dateTime", e["start"].get("date"))
        end = e["end"].get("dateTime", e["end"].get("date"))
        lines.append(f"{start} to {end}: {e.get('summary', '(no title)')}")
    return "\n".join(lines)


def create_event(title, start, end, description=""):
    from auth import get_calendar_service

    svc = get_calendar_service()
    body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": datetime.fromisoformat(start).replace(tzinfo=TZ).isoformat()},
        "end": {"dateTime": datetime.fromisoformat(end).replace(tzinfo=TZ).isoformat()},
    }
    ev = svc.events().insert(calendarId="primary", body=body).execute()
    return f"Created '{title}' from {start} to {end}. Link: {ev.get('htmlLink', 'n/a')}"


# Tools that change state. The agent loop asks before running these.
WRITE_TOOLS = {"create_event"}

RUN = {
    "search_email": search_email,
    "check_calendar": check_calendar,
    "create_event": create_event,
}
