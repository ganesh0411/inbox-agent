"""Hybrid retrieval: vector similarity fused with BM25 keyword search.

Vector search alone fails when the right document shares meaning but not
vocabulary with the query - or worse, when an irrelevant document happens to
contain the query's exact phrasing. BM25 catches names, numbers and identifiers
that embeddings blur together. Neither is reliable alone, so run both and fuse.

Fusion is Reciprocal Rank Fusion: each result scores 1/(K + rank) in each list
and the scores add. It uses only rank, not the raw scores, which matters because
cosine similarity and BM25 are not on comparable scales.
"""
import re
import sqlite3
from collections import defaultdict

from retrieve import DB, search as vector_search

RRF_K = 60          # dampens the top of each list; 60 is the standard default
CANDIDATES = 25     # how deep to look in each list before fusing

_STOP = {
    "what", "when", "where", "which", "who", "why", "how", "is", "are", "was",
    "were", "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "do",
    "does", "did", "i", "me", "my", "we", "our", "it", "that", "this", "any",
    "about", "with", "from", "have", "has", "had", "be", "been", "will", "would",
    "there", "their", "they", "s", "t",
}


def _fts_query(text):
    """Turn a natural question into something FTS5 will accept.

    FTS5 treats punctuation as syntax, so a raw question is a syntax error.
    Keep content words, OR them together so partial matches still rank.
    """
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    words = [w for w in words if len(w) > 2 and w not in _STOP]
    return " OR ".join(f'"{w}"' for w in words) if words else None


def _ensure_fts(con):
    """Build the keyword index on first use, so existing databases work as-is."""
    con.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts "
        "USING fts5(subject, sender, text, chunk_id UNINDEXED)"
    )
    n = con.execute("SELECT count(*) FROM chunks_fts").fetchone()[0]
    if n == 0:
        rows = con.execute("SELECT id, subject, sender, text FROM chunks").fetchall()
        con.executemany(
            "INSERT INTO chunks_fts (chunk_id, subject, sender, text) VALUES (?,?,?,?)",
            [(r[0], r[1], r[2], r[3]) for r in rows],
        )
        con.commit()


def keyword_search(query, k=CANDIDATES, db=str(DB)):
    con = sqlite3.connect(db)
    _ensure_fts(con)
    q = _fts_query(query)
    if not q:
        con.close()
        return []
    try:
        rows = con.execute(
            "SELECT chunk_id FROM chunks_fts WHERE chunks_fts MATCH ? "
            "ORDER BY rank LIMIT ?", (q, k),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    con.close()
    return [r[0] for r in rows]


def _hydrate(chunk_ids, db):
    if not chunk_ids:
        return {}
    con = sqlite3.connect(db)
    marks = ",".join("?" * len(chunk_ids))
    rows = con.execute(
        f"SELECT id, message_id, subject, sender, date, text FROM chunks "
        f"WHERE id IN ({marks})", chunk_ids,
    ).fetchall()
    con.close()
    return {
        r[0]: {"id": r[0], "message_id": r[1], "subject": r[2],
               "sender": r[3], "date": r[4], "text": r[5]}
        for r in rows
    }


def search(query, k=5, db=str(DB)):
    vec_hits = vector_search(query, k=CANDIDATES, db=db)
    vec_ids = [h["id"] for h in vec_hits]
    kw_ids = keyword_search(query, k=CANDIDATES, db=db)

    scores = defaultdict(float)
    sources = defaultdict(list)
    for rank, cid in enumerate(vec_ids):
        scores[cid] += 1 / (RRF_K + rank + 1)
        sources[cid].append("vector")
    for rank, cid in enumerate(kw_ids):
        scores[cid] += 1 / (RRF_K + rank + 1)
        sources[cid].append("keyword")

    top = sorted(scores, key=lambda c: -scores[c])[:k]
    meta = _hydrate(top, db)

    out = []
    for cid in top:
        if cid in meta:
            out.append({**meta[cid], "score": scores[cid], "matched": sources[cid]})
    return out


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--db", default=str(DB))
    a = ap.parse_args()

    for i, h in enumerate(search(a.query, a.k, a.db), 1):
        print(f"\n{i}. [{h['score']:.4f} via {'+'.join(h['matched'])}] {h['subject'][:66]}")
        print(f"   {' '.join(h['text'].split())[:160]}...")
