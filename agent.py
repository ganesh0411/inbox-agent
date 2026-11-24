"""The agent loop: Claude decides which tools to call, this code runs them."""
import argparse
import json
import os
from datetime import datetime

from anthropic import Anthropic
from dotenv import load_dotenv

from tools import RUN, TOOLS, WRITE_TOOLS, now

load_dotenv()

MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-5-5")
MAX_TURNS = 8

SYSTEM = """You are an operations assistant with access to the user's email archive and calendar.

Today is {today}.

How to work:
- Reach for search_email whenever a question touches what was said or agreed in email.
- Read what comes back critically. The search ranks by topical similarity, so a result
  can be about the right subject while answering a different question. If the user asks
  what is still pending, a rejection or a cancellation is not a pending item.
- Use check_calendar for anything about availability or what is scheduled. Never guess at it.
- Chain tools when one answer feeds the next.
- Cite what you used: name the sender and subject of messages you relied on.
- If the retrieved material does not answer the question, say so plainly rather than
  filling the gap. Say what you did find.
- Be concise. No preamble."""


def run(question, on_event=None, allow_writes=True, confirm=None):
    """Run one question to completion. Returns the final text answer.

    on_event: optional callback for progress, so a UI can show tool calls.
    confirm:  optional callable(name, args) -> bool, gating state-changing tools.
    """
    client = Anthropic()
    messages = [{"role": "user", "content": question}]

    def emit(kind, payload):
        if on_event:
            on_event(kind, payload)

    for _ in range(MAX_TURNS):
        reply = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM.format(today=now().strftime("%A, %B %d, %Y")),
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": reply.content})

        if reply.stop_reason != "tool_use":
            text = "".join(b.text for b in reply.content if b.type == "text")
            emit("answer", text)
            return text

        results = []
        for block in reply.content:
            if block.type != "tool_use":
                continue
            emit("tool_call", {"name": block.name, "input": block.input})

            if block.name in WRITE_TOOLS and not allow_writes:
                out = "Refused: this assistant is running in read-only mode."
            elif block.name in WRITE_TOOLS and confirm and not confirm(block.name, block.input):
                out = "The user declined this action."
            else:
                try:
                    out = RUN[block.name](**block.input)
                except Exception as e:                      # surface errors to Claude
                    out = f"Tool failed: {type(e).__name__}: {e}"

            emit("tool_result", {"name": block.name, "output": out[:400]})
            results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": out}
            )

        messages.append({"role": "user", "content": results})

    return "Stopped after too many steps without reaching an answer."


def _cli_confirm(name, args):
    print(f"\n  Claude wants to run {name} with:")
    print("   " + json.dumps(args, indent=2).replace("\n", "\n   "))
    return input("  Allow? [y/N] ").strip().lower() == "y"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?")
    ap.add_argument("--read-only", action="store_true")
    args = ap.parse_args()

    def show(kind, payload):
        if kind == "tool_call":
            print(f"  -> {payload['name']}({json.dumps(payload['input'])[:110]})")
        elif kind == "tool_result":
            first = payload["output"].split("\n")[0][:100]
            print(f"  <- {first}")

    def ask(q):
        print()
        answer = run(q, on_event=show,
                     allow_writes=not args.read_only, confirm=_cli_confirm)
        print(f"\n{answer}\n")

    if args.question:
        ask(args.question)
        return

    print("Ask a question, or Ctrl-C to quit.\n")
    while True:
        try:
            q = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if q:
            ask(q)


if __name__ == "__main__":
    main()
