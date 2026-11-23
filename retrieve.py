"""Search the index: embed the question, find the nearest chunks."""
import argparse
import multiprocessing as mp
import sqlite3
from functools import lru_cache
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

mp.set_start_method("spawn", force=True)

DB = Path("data/index.db")
MODEL = "BAAI/bge-small-en-v1.5"


@lru_cache(maxsize=2)
def _load(db=str(DB)):
    """Load the model and the whole index once, then reuse it."""
    model = TextEmbedding(MODEL)
    con = sqlite3.connect(db)
    rows = con.execute(
        "SELECT id, message_id, subject, sender, date, text, vector FROM chunks"
    ).fetchall()
    con.close()
    matrix = np.vstack([np.frombuffer(r[6], dtype=np.float32) for r in rows])
    meta = [
        {"id": r[0], "message_id": r[1], "subject": r[2],
         "sender": r[3], "date": r[4], "text": r[5]}
        for r in rows
    ]
    return model, matrix, meta


def search(query, k=5, db=str(DB)):
    model, matrix, meta = _load(db)
    q = np.array(list(model.embed([query], parallel=None))[0], dtype=np.float32)
    q /= np.linalg.norm(q)

    # Brute force is correct here: 186 messages is a few hundred vectors.
    # An ANN index only pays off once this stops fitting comfortably in memory.
    scores = matrix @ q
    top = np.argsort(-scores)[:k]
    return [{**meta[i], "score": float(scores[i])} for i in top]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--db", default=str(DB))
    args = ap.parse_args()

    for i, hit in enumerate(search(args.query, args.k, args.db), 1):
        print(f"\n{i}. [{hit['score']:.3f}] {hit['subject'][:70]}")
        print(f"   from: {hit['sender'][:60]}")
        snippet = " ".join(hit["text"].split())[:200]
        print(f"   {snippet}...")


if __name__ == "__main__":
    main()
