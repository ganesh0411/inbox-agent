# Inbox Agent

Ask questions about a mailbox and calendar in plain language, and have the
assistant act on them. It combines retrieval over indexed email with live tool
calls against a calendar, and ships with an evaluation harness that measures
whether retrieval is actually finding the right messages.

**[Live demo](https://inbox-agent-b7r2.onrender.com)** &nbsp;·&nbsp; runs on a seeded inbox, not a real mailbox. Free tier, so the first request may take ~50s to wake.

---

## What it does

Two kinds of question need two different mechanisms, and the agent picks:

**Questions about what was said** go to retrieval. Email is chunked, embedded
and indexed ahead of time; a question retrieves the most relevant excerpts and
the model answers from them.

**Questions about live state** go to tools. "Am I free December 9?" cannot be
answered from an index — it is stale the moment it is written — so the agent
calls the calendar directly.

It chains them when needed. *"Am I free when Tomas suggested meeting?"* searches
email to find the proposed date, then checks the calendar for that date, then
answers.

The model never executes anything. It returns a structured request —
`{"name": "create_event", "input": {...}}` — and application code decides whether
to run it. That boundary is what makes write tools safe to expose.

---

## Results

Retrieval quality is measured against a 25-question golden set with known
correct source emails (`evals/golden.jsonl`). No model in the loop, so the
numbers are fast, free and deterministic.

| | vector only | hybrid |
|---|---|---|
| recall@5 | 0.800 | **0.920** |
| MRR | 0.880 | **0.960** |
| questions fully answered | 17/25 | **21/25** |
| questions with no correct hit | 2/25 | **0/25** |

The harness is what found the problem. Asked what could put a project at risk,
vector search ranked a conference invitation first — it contained the exact
phrase "Tacoma retrofit" — while the email actually titled "timeline risk" fell
outside the top 10, because its body never names the project. Embeddings match
meaning; they blur the identifiers that make a document *the* right one.

The fix was hybrid retrieval: run BM25 keyword search alongside vector search
and fuse the two rankings with Reciprocal Rank Fusion. RRF uses rank rather than
score, which matters because cosine similarity and BM25 are not on comparable
scales.

```
python evals/run_evals.py -k 5 --method vector
python evals/run_evals.py -k 5 --method hybrid
```

---

## Architecture

```
OFFLINE                                        LIVE
Gmail API                                      React UI
   ↓  OAuth, pagination, quota backoff            ↓  SSE
ingest.py    → clean text                      server.py  (FastAPI)
   ↓  MIME walk, quote + signature stripping       ↓
index_build.py → chunks + vectors              agent.py   (tool loop)
   ↓                                              ↓
SQLite (vectors + FTS5)  ←──── hybrid.py ────→ tools.py  → Calendar API
```

| File | Role |
|---|---|
| `auth.py` | Google OAuth, token persistence, automatic re-consent |
| `ingest.py` | Fetch and clean mail: pagination, quota backoff, resumable |
| `index_build.py` | Chunk, embed, write the SQLite index |
| `retrieve.py` | Vector search |
| `hybrid.py` | BM25 + vector, fused with RRF |
| `agent.py` | The tool-calling loop |
| `tools.py` | Tool schemas and implementations |
| `server.py` | FastAPI, SSE streaming, demo sandbox |
| `web/` | React + TypeScript chat UI |
| `evals/` | Golden set and the harness |

**Stack:** Python, FastAPI, SQLite, fastembed (BAAI/bge-small-en-v1.5, local),
Claude API, React + TypeScript + Vite.

---

## Engineering notes

**Ingestion is the hard part, not the model.** Gmail's `list` endpoint returns
only message IDs, so fetching N messages costs N+1 API calls. At a few hundred
messages that hits the per-minute quota. The fix was exponential backoff past
the one-minute quota window plus a resumable run — a crash at message 150
restarts at 151 rather than at zero.

**Real email is hostile to indexing.** Bodies arrive as a MIME tree that has to
be walked, base64url-decoded, and stripped of quoted replies and signatures.
Without that, a twenty-message thread indexes the same text twenty times.

**Brute-force search is the correct choice at this scale.** A few hundred
vectors is a single matrix multiply. An ANN index earns its complexity when the
data stops fitting comfortably in memory, which this does not.

**Local embeddings, deliberately.** Embedding runs on CPU via ONNX. No API
latency, no per-call cost, and no email text leaving the machine during
indexing.

**Privacy shaped the deploy.** The public demo runs on a generated inbox and
calendar (`demo/`), never a real account. Real mail is indexed locally and never
committed. `DEMO_MODE` swaps the calendar tools for a seeded file, so the
deployed agent cannot reach a Google account at all.

---

## Running it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
```

**Demo data** (no Google account needed):

```bash
python demo/seed_inbox.py
python demo/seed_calendar.py
python index_build.py --src data/demo_messages.jsonl --db data/demo_index.db
uvicorn server:app --port 8000
cd web && npm install && npm run dev        # http://localhost:5173
```

**Your own mail** — add OAuth credentials as `credentials.json`
([setup](https://developers.google.com/workspace/guides/create-credentials)),
then:

```bash
python ingest.py --limit 200
python index_build.py
python agent.py "what do I need to sign off on this week?"
```

## Known limitations

- Ingestion is a full re-fetch; incremental sync via Gmail's history API is not implemented.
- Chunking is fixed-size with overlap. Thread-aware chunking would likely help the four questions still at partial recall.
- Evals measure retrieval only. Answer faithfulness is not scored automatically.
- The demo is single-user with no auth; conversation history is not persisted.
