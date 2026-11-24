"""Measure retrieval quality against the golden set.

Retrieval is the ceiling on everything downstream: if the right email is not
in the top k, no amount of prompting makes the answer correct. So this measures
retrieval alone, with no model in the loop - it is fast, free and deterministic.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GOLDEN = Path(__file__).parent / "golden.jsonl"


def evaluate(search_fn, questions, k):
    per_q, recalls, precisions, rrs = [], [], [], []

    for q in questions:
        hits = search_fn(q["question"], k=k)
        got = [h["subject"] for h in hits]
        want = set(q["relevant"])

        found = [s for s in got if s in want]
        recall = len(set(found)) / len(want)
        precision = len(found) / max(len(got), 1)

        rank = next((i + 1 for i, s in enumerate(got) if s in want), None)
        rr = 1 / rank if rank else 0.0

        recalls.append(recall)
        precisions.append(precision)
        rrs.append(rr)
        per_q.append({
            "id": q["id"],
            "question": q["question"],
            "recall": recall,
            "missed": sorted(want - set(got)),
            "first_rank": rank,
        })

    n = len(questions)
    return {
        "k": k,
        "questions": n,
        "recall_at_k": sum(recalls) / n,
        "precision_at_k": sum(precisions) / n,
        "mrr": sum(rrs) / n,
        "perfect": sum(1 for p in per_q if p["recall"] == 1.0),
        "zero": sum(1 for p in per_q if p["recall"] == 0.0),
        "per_question": per_q,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/demo_index.db")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--method", default="vector", choices=["vector", "hybrid"])
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--json-out")
    args = ap.parse_args()

    if args.method == "vector":
        from retrieve import search as _s
        search_fn = lambda q, k: _s(q, k=k, db=args.db)
    else:
        from hybrid import search as _h
        search_fn = lambda q, k: _h(q, k=k, db=args.db)

    questions = [json.loads(l) for l in GOLDEN.open()]
    r = evaluate(search_fn, questions, args.k)

    print(f"\n  method       {args.method}")
    print(f"  k            {r['k']}")
    print(f"  questions    {r['questions']}")
    print(f"  recall@{r['k']}     {r['recall_at_k']:.3f}")
    print(f"  precision@{r['k']}  {r['precision_at_k']:.3f}")
    print(f"  MRR          {r['mrr']:.3f}")
    print(f"  perfect      {r['perfect']}/{r['questions']}")
    print(f"  total miss   {r['zero']}/{r['questions']}")

    worst = [p for p in r["per_question"] if p["recall"] < 1.0]
    if worst:
        print(f"\n  incomplete ({len(worst)}):")
        for p in sorted(worst, key=lambda x: x["recall"]):
            print(f"    [{p['id']}] recall {p['recall']:.2f}  {p['question'][:58]}")
            if args.verbose:
                for m in p["missed"]:
                    print(f"           missed: {m}")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(r, indent=2))
        print(f"\n  wrote {args.json_out}")

    print()


if __name__ == "__main__":
    main()
