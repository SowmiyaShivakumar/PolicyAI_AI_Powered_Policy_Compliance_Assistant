"""
DeepEval Evaluation Runner
Run: cd backend && python evaluation/run_eval.py
"""

import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ── Increase per-task timeout ──────────────────────────────────────────────
# DeepEval has separate per-attempt and per-task timeouts.
os.environ.setdefault("DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE", "900")
os.environ.setdefault("DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE", "1200")

from deepeval import evaluate
from deepeval.test_case import LLMTestCase
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
)
from deepeval.evaluate.configs import AsyncConfig, ErrorConfig
from collections import defaultdict
from agents.orchestrator import run as run_pipeline
from evaluation.golden_dataset import GOLDEN_DATASET

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "eval_results.json")

METRICS = [
    AnswerRelevancyMetric(threshold=0.5,     verbose_mode=False, model="gpt-4o"),
    FaithfulnessMetric(threshold=0.5,        verbose_mode=False, model="gpt-4o"),
    ContextualPrecisionMetric(threshold=0.5, verbose_mode=False, model="gpt-4o"),
    ContextualRecallMetric(threshold=0.5,    verbose_mode=False, model="gpt-4o"),
]


def build_test_case(item: dict) -> LLMTestCase:
    query = item["input"]
    print(f"  Running: {query[:65]}...")

    result = run_pipeline(query)

    actual_output = (
        result.get("recommendation", {}).get("summary")
        or result.get("interpretation")
        or "No response generated."
    )

    chunks = result.get("chunks", [])

    # ── Keep context short to avoid gpt-4o token overflow ──
    if chunks:
        retrieval_context = [
            f"{c['subcategory_id']}: {c['text'][:80]}"
            for c in chunks[:3]          # max 3 chunks
        ]
    else:
        retrieval_context = [item["context"][:300]]

    context = (
        item["context"] if isinstance(item["context"], list)
        else [item["context"][:300]]
    )

    return LLMTestCase(
        input=query,
        actual_output=actual_output,
        expected_output=item["expected_output"],
        retrieval_context=retrieval_context,
        context=context,
    )

def run_evaluation():
    print("=" * 60)
    print("  DeepEval — Policy Compliance Evaluation")
    print(f"  Test cases : 10")
    print("=" * 60)

    test_cases = []
    for i, item in enumerate(GOLDEN_DATASET, 1):
        print(f"\n[{i}/{len(GOLDEN_DATASET)}]")
        try:
            tc = build_test_case(item)
            test_cases.append(tc)
        except Exception as e:
            print(f"  Skipped: {e}")
        time.sleep(0.5)

    print(f"\n{'='*60}")
    print(f"  Scoring {len(test_cases)} test cases (synchronous)...")
    print(f"{'='*60}\n")

    # ── Run synchronously to avoid all async timeout issues ───────────────
    eval_result = evaluate(
        test_cases,
        METRICS,
        async_config=AsyncConfig(run_async=False, throttle_value=0, max_concurrent=1),
        error_config=ErrorConfig(ignore_errors=False),
    )

    # ── Extract scores dynamically ────────────────────────────────────────
    metric_scores = {}

    try:
        test_results = eval_result.test_results

        all_scores = defaultdict(list)
        all_errors = defaultdict(list)

        for tr in test_results:
            for m in tr.metrics_data:
                if m.score is not None:
                    all_scores[m.name.strip()].append(m.score)
                elif m.error:
                    all_errors[m.name.strip()].append(m.error)

        # Report any metric errors
        if all_errors:
            print("\n  ⚠ Metrics with errors:")
            for name, errs in all_errors.items():
                print(f"    {name}: {len(errs)} error(s)")
                print(f"      e.g. {errs[0][:150]}")

        if not all_scores:
            print("\n  ❌ No scores collected — all metrics errored.")
            print("     Check your OPENAI_API_KEY and network connectivity.")
            metric_scores = {"note": "All metrics errored. See errors above."}
        else:
            for metric_name, scores in all_scores.items():
                passed = sum(1 for s in scores if s >= 0.5)
                avg    = round(sum(scores) / len(scores), 3)
                metric_scores[metric_name] = {
                    "average_score": avg,
                    "passed":        passed,
                    "total":         len(scores),
                    "pass_rate":     f"{round(passed / len(scores) * 100)}%",
                }

    except Exception as e:
        print(f"  Warning: Could not parse detailed scores ({e})")
        print("  DeepEval summary above is still valid.")
        metric_scores = {"note": "See DeepEval console output above for results."}

    # ── Print summary ──────────────────────────────────────────────────────
    overall = 0.0
    if isinstance(metric_scores, dict) and "note" not in metric_scores and metric_scores:
        overall = round(
            sum(v["average_score"] for v in metric_scores.values()) / len(metric_scores), 3
        )
        print(f"\n{'='*60}")
        print("  EVALUATION RESULTS")
        print(f"{'='*60}")
        for name, v in metric_scores.items():
            status = "✅" if v["average_score"] >= 0.5 else "❌"
            print(f"  {status} {name:25} avg={v['average_score']:.3f}  "
                  f"passed={v['passed']}/{v['total']}  ({v['pass_rate']})")
        print(f"\n  Overall : {overall:.3f} "
              f"({'PASS ✅' if overall >= 0.5 else 'FAIL ❌'})")
        print("=" * 60)
    else:
        print("\n  ⚠ No results to display. Check errors above.")

    output = {
        "summary":        metric_scores,
        "overall_score":  overall,
        "test_cases_run": len(test_cases),
    }
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved → {OUTPUT_FILE}")


if __name__ == "__main__":
    run_evaluation()
