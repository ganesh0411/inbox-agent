"""HTTP API in front of the agent.

The browser never talks to Claude, Gmail or the index directly: the API key
can't ship to a client, and tool execution has to happen somewhere trusted.

Answers stream as server-sent events so the UI can show tool calls as they
happen rather than a fifteen second spinner.
"""
import asyncio
import json
import os
import queue
import threading
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

# The deployed demo runs on the synthetic inbox. Real mail stays local.
os.environ.setdefault("INDEX_DB", "data/demo_index.db")
os.environ.setdefault("DEMO_MODE", "true")

import agent  # noqa: E402  - imported after INDEX_DB is set

app = FastAPI(title="Agentic Ops Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Calendar tools need Google credentials, which the public demo doesn't have.
# Safe to allow in demo mode: writes land in an in-memory demo calendar.
ALLOW_WRITES = os.environ.get("ALLOW_WRITES", "true").lower() == "true"

SUGGESTIONS = [
    "What's the deadline on the Tacoma retrofit and what could put it at risk?",
    "What's happening with the ops analyst hiring?",
    "Is the maintenance underspend real savings?",
    "What compliance deadlines are coming up?",
    "What do I need to sign off on this week?",
    "Am I free when Tomas suggested meeting?",
]


class Ask(BaseModel):
    question: str


@app.get("/api/health")
def health():
    return {"ok": True, "index": os.environ["INDEX_DB"], "writes": ALLOW_WRITES}


@app.get("/api/suggestions")
def suggestions():
    return {"suggestions": SUGGESTIONS}


@app.post("/api/chat")
async def chat(body: Ask):
    """Run the agent, streaming each tool call and the final answer as SSE."""
    events: queue.Queue = queue.Queue()

    def on_event(kind, payload):
        events.put({"type": kind, "data": payload})

    def work():
        try:
            agent.run(body.question, on_event=on_event, allow_writes=ALLOW_WRITES)
        except Exception as e:
            events.put({"type": "error", "data": f"{type(e).__name__}: {e}"})
        finally:
            events.put(None)

    threading.Thread(target=work, daemon=True).start()

    async def stream():
        loop = asyncio.get_event_loop()
        while True:
            item = await loop.run_in_executor(None, events.get)
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Serve the built React app in production, if it has been built.
_dist = Path(__file__).parent / "web" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="web")
