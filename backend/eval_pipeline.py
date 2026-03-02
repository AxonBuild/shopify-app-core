"""
eval_pipeline.py
────────────────
Full evaluation pipeline for the Isla RAG system.

For each query in eval_dataset.json this script:
  1. Runs the real embedding + hybrid search pipeline
  2. Computes classic retrieval metrics:
       • Hit Rate   – did any expected product appear in top-K?
       • MRR        – mean reciprocal rank of first expected hit
       • Precision@K– fraction of returned products that are expected
  3. Sends results to OpenAI as an LLM judge for contextual quality scoring
  4. Writes a structured report to eval_report.json and prints a summary

Usage:
    python eval_pipeline.py                  # full eval (search + LLM judge)
    python eval_pipeline.py --no-llm         # metrics only, no OpenAI calls
    python eval_pipeline.py --query Q05      # run a single query by ID
    python eval_pipeline.py --report         # re-print last saved report
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from openai import OpenAI
from app.config.settings import settings
from app.services.embedding_service import embedding_service
from app.services.search_service import search_service

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATASET_FILE = os.path.join(BASE_DIR, "eval_dataset.json")
REPORT_FILE  = os.path.join(BASE_DIR, "eval_report.json")

# ── ANSI ──────────────────────────────────────────────────────────────────────
CYAN   = "\033[96m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
RED    = "\033[91m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
DIM    = "\033[2m"

client = OpenAI(api_key=settings.openai_api_key)

STORE_CONTEXT = (
    "You are evaluating an AI-powered shopping assistant for 'Ismail's Clothing', "
    "a Pakistani kids clothing store. The store sells ONLY Urban Junior Boy clothing: "
    "t-shirts, jeans, casual shirts, cargo pants, shorts, polos, and coord sets. "
    "All products are for boys aged 4–14 years. Prices are in PKR (450–2799 range)."
)

# ── Search runner ─────────────────────────────────────────────────────────────

def run_search(query: str, color_filter: Optional[str], max_price: Optional[float], top_k: int = 3) -> list[dict]:
    """Embed query and run hybrid search with optional filters."""
    text_vector = None
    try:
        text_vector = embedding_service.embed_text(query)
    except Exception as e:
        print(f"    {RED}Embedding error: {e}{RESET}")

    filters = []
    if color_filter:
        filters.append(f'color = "{color_filter.upper()}"')
    if max_price is not None:
        filters.append(f"price <= {max_price}")
    filter_str = " AND ".join(filters) if filters else None

    try:
        hits = search_service.perform_hybrid_search(
            query=query,
            text_vector=text_vector,
            limit=top_k,
            filter_str=filter_str,
        )
        return hits[:top_k]
    except Exception as e:
        print(f"    {RED}Search error: {e}{RESET}")
        return []


# ── Classic metrics ───────────────────────────────────────────────────────────

def compute_metrics(expected: list[dict], returned: list[dict]) -> dict:
    """
    Compute Hit Rate, MRR, and Precision@K.

    For edge cases where expected_products is [] (no results expected),
    we invert the logic: a hit means something was returned (bad), 0 returned = perfect.
    """
    expected_handles = {p["handle"] for p in expected}
    returned_handles = [h.get("handle", "") for h in returned]

    # Special case: query is expected to return nothing
    if not expected_handles:
        hit   = len(returned_handles) == 0
        mrr   = 1.0 if hit else 0.0
        prec  = 1.0 if hit else 0.0
        return {"hit_rate": float(hit), "mrr": mrr, "precision_at_k": prec, "empty_expected": True}

    # Hit Rate: did any expected handle appear?
    hit = any(h in expected_handles for h in returned_handles)

    # MRR: rank of first expected hit (1-indexed)
    mrr = 0.0
    for rank, handle in enumerate(returned_handles, 1):
        if handle in expected_handles:
            mrr = 1.0 / rank
            break

    # Precision@K: fraction of returned that are expected
    if returned_handles:
        true_positives = sum(1 for h in returned_handles if h in expected_handles)
        precision = true_positives / len(returned_handles)
    else:
        precision = 0.0

    return {
        "hit_rate":       float(hit),
        "mrr":            round(mrr, 4),
        "precision_at_k": round(precision, 4),
        "empty_expected": False,
    }


# ── LLM judge ────────────────────────────────────────────────────────────────

JUDGE_SYSTEM = f"""{STORE_CONTEXT}

Your job is to evaluate search results returned by a product search engine.
You will receive:
  - A customer's WhatsApp shopping query
  - What the correct/expected products should have been (if known)
  - The actual products the search engine returned

Rate EACH returned product on this scale:
  3 = Perfect match — exactly what the query asked for
  2 = Good match   — relevant product, minor mismatch (e.g. wrong color shade)
  1 = Partial match — same category but clearly off (e.g. query=jeans, result=t-shirt)
  0 = Irrelevant   — completely unrelated to query

Then give an OVERALL score from 0–10 for the entire result set:
  9–10 = Outstanding: all products perfectly satisfy the query
  7–8  = Good: most products are right, tiny gaps
  5–6  = Acceptable: at least one strong match, some noise
  3–4  = Poor: mostly wrong products or missing key filters
  0–2  = Failed: results totally misaligned with query

Also flag if:
  - A color filter was clearly violated (returned wrong colors)
  - A price filter was clearly violated (price above stated max)
  - The query was out-of-catalog (no clothing product can satisfy it)

Respond STRICTLY as JSON:
{{
  "product_scores": [
    {{"handle": "...", "title": "...", "score": 0-3, "reason": "brief reason"}}
  ],
  "overall_score": 0-10,
  "color_filter_violated": true/false,
  "price_filter_violated": true/false,
  "out_of_catalog": true/false,
  "judge_summary": "1-2 sentence overall assessment"
}}"""


def llm_judge(query_entry: dict, returned_hits: list[dict]) -> dict:
    """Call OpenAI to judge the quality of search results."""
    expected = query_entry.get("expected_products", [])
    color    = query_entry.get("color_filter")
    max_price = query_entry.get("max_price")

    # Build the user message
    returned_str = "\n".join(
        f"  {i+1}. handle={h.get('handle')}  title={h.get('title')}  "
        f"color={h.get('color')}  price=PKR {h.get('price')}  "
        f"score={round(h.get('_rankingScore', 0), 3)}"
        for i, h in enumerate(returned_hits)
    ) or "  (no results returned)"

    expected_str = "\n".join(
        f"  - handle={p['handle']}  title={p['title']}  color={p['color']}  price=PKR {p['price']}"
        for p in expected
    ) or "  (none — query is expected to return 0 results)"

    user_msg = f"""
CUSTOMER QUERY: "{query_entry['query']}"
FILTERS APPLIED: color={color or 'none'}, max_price={max_price or 'none'} PKR
CATEGORY: {query_entry['category']}
NOTES: {query_entry['notes']}

EXPECTED PRODUCTS (ground truth):
{expected_str}

RETURNED PRODUCTS (what the search engine actually returned):
{returned_str}

Please evaluate the returned products.
""".strip()

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user",   "content": user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=600,
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {
            "error":           str(e),
            "overall_score":   -1,
            "judge_summary":   f"Judge call failed: {e}",
            "product_scores":  [],
            "color_filter_violated": False,
            "price_filter_violated": False,
            "out_of_catalog":  False,
        }


# ── Report printer ────────────────────────────────────────────────────────────

def print_summary(results: list[dict], use_llm: bool):
    total   = len(results)
    hits    = sum(1 for r in results if r["metrics"]["hit_rate"] == 1.0)
    avg_mrr = sum(r["metrics"]["mrr"] for r in results) / total
    avg_prec = sum(r["metrics"]["precision_at_k"] for r in results) / total

    print(f"\n{CYAN}{BOLD}{'━'*65}")
    print(f"  EVALUATION SUMMARY — {total} queries")
    print(f"{'━'*65}{RESET}")
    print(f"  {'Hit Rate':<25}: {BOLD}{hits}/{total}  ({100*hits/total:.0f}%){RESET}")
    print(f"  {'Mean Reciprocal Rank':<25}: {BOLD}{avg_mrr:.3f}{RESET}")
    print(f"  {'Mean Precision@K':<25}: {BOLD}{avg_prec:.3f}{RESET}")

    if use_llm:
        valid_scores = [r["judge"]["overall_score"] for r in results if r["judge"].get("overall_score", -1) >= 0]
        if valid_scores:
            avg_judge = sum(valid_scores) / len(valid_scores)
            print(f"  {'LLM Judge Score':<25}: {BOLD}{avg_judge:.1f} / 10{RESET}")
        violations_color = sum(1 for r in results if r["judge"].get("color_filter_violated"))
        violations_price = sum(1 for r in results if r["judge"].get("price_filter_violated"))
        ooc              = sum(1 for r in results if r["judge"].get("out_of_catalog"))
        print(f"  {'Color filter violations':<25}: {RED if violations_color else GREEN}{violations_color}{RESET}")
        print(f"  {'Price filter violations':<25}: {RED if violations_price else GREEN}{violations_price}{RESET}")
        print(f"  {'Out-of-catalog queries':<25}: {violations_price}")

    # Per-query breakdown
    print(f"\n  {BOLD}{'ID':<6}  {'QUERY':<45}  {'Hit':>4}  {'MRR':>5}  {'Judge':>6}{RESET}")
    print(f"  {'─'*6}  {'─'*45}  {'─'*4}  {'─'*5}  {'─'*6}")
    for r in results:
        m = r["metrics"]
        hit_str  = f"{GREEN}✓{RESET}" if m["hit_rate"] == 1.0 else (f"{DIM}–{RESET}" if m.get("empty_expected") else f"{RED}✗{RESET}")
        mrr_str  = f"{m['mrr']:.3f}"
        judge_str = f"{r['judge'].get('overall_score', '–'):>5}" if use_llm else "  –"
        score_val = r['judge'].get('overall_score', 10) if use_llm else 10
        color     = GREEN if score_val >= 7 else (YELLOW if score_val >= 4 else RED)
        print(f"  {r['id']:<6}  {r['query'][:44]:<45}  {hit_str:>4}  {mrr_str:>5}  {color}{judge_str:>6}{RESET}")

    print(f"\n{CYAN}{BOLD}{'━'*65}{RESET}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Isla RAG Evaluation Pipeline")
    parser.add_argument("--no-llm",  action="store_true", help="Skip LLM judge (metrics only)")
    parser.add_argument("--query",   type=str, default=None, help="Run a single query by ID (e.g. Q05)")
    parser.add_argument("--report",  action="store_true",   help="Re-print the last saved report")
    parser.add_argument("--top-k",   type=int, default=3,   help="Top-K results to fetch (default: 3)")
    args = parser.parse_args()

    # ── Re-print saved report ─────────────────────────────────────────────────
    if args.report:
        if not os.path.exists(REPORT_FILE):
            print(f"{RED}No report found at {REPORT_FILE}. Run without --report first.{RESET}")
            sys.exit(1)
        with open(REPORT_FILE, encoding="utf-8") as f:
            report = json.load(f)
        print_summary(report["results"], use_llm=any("judge" in r for r in report["results"]))
        return

    # ── Load dataset ──────────────────────────────────────────────────────────
    if not os.path.exists(DATASET_FILE):
        print(f"{RED}eval_dataset.json not found. Run generate_eval_dataset.py first.{RESET}")
        sys.exit(1)

    with open(DATASET_FILE, encoding="utf-8") as f:
        dataset = json.load(f)

    queries = dataset["queries"]
    if args.query:
        queries = [q for q in queries if q["id"].upper() == args.query.upper()]
        if not queries:
            print(f"{RED}Query ID '{args.query}' not found in dataset.{RESET}")
            sys.exit(1)

    use_llm = not args.no_llm
    top_k   = args.top_k

    print(f"\n{CYAN}{BOLD}━━━ Isla RAG Evaluation Pipeline ━━━{RESET}")
    print(f"  Queries   : {len(queries)}")
    print(f"  Top-K     : {top_k}")
    print(f"  LLM Judge : {'gpt-4o-mini' if use_llm else 'disabled'}")
    print(f"  Dataset   : {DATASET_FILE}\n")

    results = []

    for q in queries:
        print(f"  {YELLOW}{BOLD}[{q['id']}]{RESET} {q['query'][:60]}")
        print(f"         category={q['category']}  color={q.get('color_filter')}  price≤{q.get('max_price')}")

        # 1. Run search
        t0   = time.time()
        hits = run_search(q["query"], q.get("color_filter"), q.get("max_price"), top_k)
        elapsed = time.time() - t0

        returned_handles = [h.get("handle") for h in hits]
        print(f"         {DIM}search took {elapsed:.2f}s  →  {len(hits)} hits: {returned_handles}{RESET}")

        # 2. Classic metrics
        metrics = compute_metrics(q.get("expected_products", []), hits)
        hit_str = f"{GREEN}HIT{RESET}" if metrics["hit_rate"] == 1.0 else (f"{DIM}N/A{RESET}" if metrics.get("empty_expected") else f"{RED}MISS{RESET}")
        print(f"         hit={hit_str}  mrr={metrics['mrr']:.3f}  prec={metrics['precision_at_k']:.3f}")

        # 3. LLM judge
        judge_result = {}
        if use_llm:
            print(f"         {DIM}calling judge ...{RESET}", end="\r")
            judge_result = llm_judge(q, hits)
            score = judge_result.get("overall_score", "?")
            score_color = GREEN if isinstance(score, int) and score >= 7 else (YELLOW if isinstance(score, int) and score >= 4 else RED)
            print(f"         judge={score_color}{score}/10{RESET}  — {DIM}{judge_result.get('judge_summary', '')[:80]}{RESET}")

        results.append({
            "id":       q["id"],
            "query":    q["query"],
            "category": q["category"],
            "filters":  {"color": q.get("color_filter"), "max_price": q.get("max_price")},
            "returned": [
                {"handle": h.get("handle"), "title": h.get("title"),
                 "color": h.get("color"),   "price": h.get("price"),
                 "ranking_score": round(h.get("_rankingScore", 0), 4)}
                for h in hits
            ],
            "metrics":  metrics,
            "judge":    judge_result,
            "search_latency_s": round(elapsed, 3),
        })
        print()

    # ── Print summary ─────────────────────────────────────────────────────────
    print_summary(results, use_llm)

    # ── Save report ───────────────────────────────────────────────────────────
    if not args.query:   # only save full runs
        report = {
            "meta": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_queries": len(results),
                "top_k": top_k,
                "llm_judge": "gpt-4o-mini" if use_llm else None,
            },
            "results": results,
        }
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"{GREEN}Report saved → {REPORT_FILE}{RESET}\n")


if __name__ == "__main__":
    main()
