"""Chunk the ingested messages, embed them, and build a SQLite vector index."""
import json
import multiprocessing as mp
import sqlite3
from pathlib import Path

mp.set_start_method("spawn", force=True)

import numpy as np
from fastembed import TextEmbedding

import argparse
SRC = Path("data/messages.jsonl")
DB = Path("data/index.db")
MODEL = "BAAI/bge-small-en-v1.5"   # 384 dims, runs on CPU
CHUNK, OVERLAP = 900, 150


def chunk_text(text, size=CHUNK, overlap=OVERLAP):
    """Split on natural boundaries where possible, with a little overlap."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]

    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            window = text[start:end]
            for sep in ("\n\n", "\n", ". "):
                idx = window.rfind(sep)
                if idx > size * 0.5:          # don't make a tiny chunk
                    end = start + idx + len(sep)
                    break
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def build_records(rows):
    out = []
    for r in rows:
        for i, piece in enumerate(chunk_text(r["body"])):
            out.append(
                {
                    "message_id": r["id"],
                    "subject": r["subject"],
                    "sender": r["from"],
                    "date": r["date"],
                    "chunk_index": i,
                    "text": piece,
                    # Subject and sender go into the embedded text so a chunk
                    # from the middle of a thread still carries its context.
                    "embed_text": f"Subject: {r['subject']}\nFrom: {r['from']}\n\n{piece}",
                }
            )
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(SRC))
    ap.add_argument("--db", default=str(DB))
    args = ap.parse_args()
    src_path, db_path = Path(args.src), Path(args.db)

    rows = [json.loads(l) for l in src_path.open()]
    records = build_records(rows)
    print(f"{len(rows)} messages -> {len(records)} chunks")

    print(f"Loading {MODEL} (first run downloads ~130MB)...")
    model = TextEmbedding(MODEL)

    print("Embedding...", flush=True)
    texts = [r["embed_text"] for r in records]
    out = []
    B = 32
    for i in range(0, len(texts), B):
        # parallel=None disables worker processes; parallel=0 means "all cores"
        out.extend(model.embed(texts[i:i + B], batch_size=B, parallel=None))
        print(f"  {min(i + B, len(texts))}/{len(texts)}", flush=True)
    vectors = np.array(out, dtype=np.float32)
    # Normalise so cosine similarity is just a dot product.
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    print(f"Vectors: {vectors.shape}")

    db_path.unlink(missing_ok=True)
    con = sqlite3.connect(db_path)
    con.execute(
        """CREATE TABLE chunks (
               id INTEGER PRIMARY KEY,
               message_id TEXT, subject TEXT, sender TEXT, date TEXT,
               chunk_index INTEGER, text TEXT, vector BLOB
           )"""
    )
    con.execute("CREATE INDEX idx_message ON chunks(message_id)")
    con.executemany(
        "INSERT INTO chunks (message_id, subject, sender, date, chunk_index, text, vector)"
        " VALUES (?,?,?,?,?,?,?)",
        [
            (r["message_id"], r["subject"], r["sender"], r["date"],
             r["chunk_index"], r["text"], v.tobytes())
            for r, v in zip(records, vectors)
        ],
    )
    con.commit()
    con.close()
    print(f"Wrote {db_path}")


if __name__ == "__main__":
    main()
