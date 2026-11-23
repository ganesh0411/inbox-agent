"""Pull Gmail messages, clean them, and save to data/messages.jsonl."""
import argparse
import base64
import html as htmllib
import json
import random
import re
import time
from pathlib import Path

from googleapiclient.errors import HttpError

from auth import get_gmail_service

OUT = Path("data/messages.jsonl")

# --- rate limiting ----------------------------------------------------------

RETRYABLE = {403, 429, 500, 502, 503}


def with_retry(request, attempts=8):
    """Gmail's quota window is a full minute, so back off well past it."""
    for i in range(attempts):
        try:
            return request.execute()
        except HttpError as e:
            if e.resp.status in RETRYABLE and i < attempts - 1:
                wait = min(64, 2**i) + random.random()
                print(f"    throttled ({e.resp.status}) - waiting {wait:.0f}s")
                time.sleep(wait)
                continue
            raise


# --- body extraction --------------------------------------------------------

def _decode(data):
    return base64.urlsafe_b64decode(data.encode()).decode("utf-8", errors="replace")


TAG = re.compile(r"<[^>]+>")


def _html_to_text(raw):
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?i)</p>", "\n\n", raw)
    return htmllib.unescape(TAG.sub(" ", raw))


def extract_body(payload):
    """Walk the MIME tree. Prefer text/plain, fall back to stripped HTML."""
    plain, rich = [], []

    def walk(part):
        if part.get("parts"):
            for p in part["parts"]:
                walk(p)
            return
        data = part.get("body", {}).get("data")
        if not data:
            return
        mime = part.get("mimeType", "")
        if mime == "text/plain":
            plain.append(_decode(data))
        elif mime == "text/html":
            rich.append(_decode(data))

    walk(payload)
    if plain:
        return "\n".join(plain)
    if rich:
        return _html_to_text("\n".join(rich))
    return ""


# --- cleaning ---------------------------------------------------------------

QUOTE_START = [
    re.compile(r"^On\b.{0,160}\bwrote:\s*$", re.I),
    re.compile(r"^-{2,}\s*Original Message\s*-{2,}", re.I),
    re.compile(r"^(From|Sent|To|Subject):\s", re.I),
    re.compile(r"^_{10,}$"),
    re.compile(r"^Sent from my \w+", re.I),
]


def strip_quoted(text):
    """Cut at the first sign of a quoted reply or signature."""
    kept = []
    for line in text.splitlines():
        s = line.strip()
        if s == "--" or s.startswith("-- "):
            break
        if any(p.match(s) for p in QUOTE_START):
            break
        if s.startswith(">"):
            continue
        kept.append(line)
    return "\n".join(kept)


def collapse(text):
    text = text.replace("\u200c", "").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --- main -------------------------------------------------------------------

def list_ids(service, query, limit):
    ids, page = [], None
    while len(ids) < limit:
        resp = with_retry(
            service.users().messages().list(
                userId="me", q=query, maxResults=min(500, limit - len(ids)), pageToken=page
            )
        )
        ids.extend(m["id"] for m in resp.get("messages", []))
        page = resp.get("nextPageToken")
        if not page:
            break
    return ids[:limit]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--query", default="-in:spam -in:trash -in:chats")
    args = ap.parse_args()

    service = get_gmail_service()

    ids = list_ids(service, args.query, args.limit)
    print(f"Found {len(ids)} message ids")

    OUT.parent.mkdir(exist_ok=True)

    # Resume: never refetch what we already have.
    done = set()
    if OUT.exists():
        with OUT.open() as f:
            for line in f:
                try:
                    done.add(json.loads(line)["id"])
                except (ValueError, KeyError):
                    pass
    if done:
        print(f"Resuming - {len(done)} already saved")

    written = skipped = 0

    with OUT.open("a") as f:
        for i, mid in enumerate(ids, 1):
            if mid in done:
                continue
            time.sleep(0.15)  # stay under the per-second quota
            msg = with_retry(
                service.users().messages().get(userId="me", id=mid, format="full")
            )
            h = {x["name"].lower(): x["value"] for x in msg["payload"].get("headers", [])}
            body = collapse(strip_quoted(extract_body(msg["payload"])))

            if len(body) < 20:
                skipped += 1
                continue

            f.write(
                json.dumps(
                    {
                        "id": mid,
                        "thread_id": msg.get("threadId"),
                        "subject": h.get("subject", "(no subject)"),
                        "from": h.get("from", ""),
                        "date": h.get("date", ""),
                        "body": body[:8000],
                    }
                )
                + "\n"
            )
            written += 1
            f.flush()  # survive a crash mid-run

            if i % 25 == 0:
                print(f"  {i}/{len(ids)}")

    print(f"\nWrote {written} messages to {OUT} ({skipped} skipped as empty)")


if __name__ == "__main__":
    main()
