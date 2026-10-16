"""Aggregate a runs.jsonl file into a Markdown report.

Utility: mean correctness per (model, defense). Attack: attack success rate per
(scenario, model, defense), with Wilson 95% confidence intervals so a small
number of trials is not read as certainty.

    python -m evals.report evals/results/runs.jsonl [--md evals/results/report.md]
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path


def _wilson(successes: int, n: int) -> tuple:
    """Wilson score 95% interval for a binomial proportion."""
    if n == 0:
        return (0.0, 0.0)
    z = 1.96
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def load(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def build_report(rows: list[dict]) -> str:
    models = sorted({r["model"] for r in rows if "model" in r})
    defenses = sorted({r.get("defense", "baseline") for r in rows})
    total_cost = sum(float(r.get("cost", 0) or 0) for r in rows)
    errors = [r for r in rows if r.get("error")]

    out: list[str] = []
    out.append("# Eval report\n")
    out.append(f"- Runs: {len(rows)}  ·  models: {len(models)}  ·  "
               f"defenses: {len(defenses)}  ·  total cost: ${total_cost:.4f}")
    if errors:
        out.append(f"- Runs with errors: {len(errors)} "
                   f"(e.g. {errors[0].get('error', '')[:80]})")
    out.append("")

    # --- Utility ---
    util = [r for r in rows if r.get("kind") == "utility" and r.get("error") is None]
    if util:
        out.append("## Utility (benign questions answered correctly)\n")
        out.append("| Model | Defense | Correct | N |")
        out.append("|---|---|---|---|")
        agg = defaultdict(lambda: [0, 0])  # (model,defense) -> [correct, n]
        for r in util:
            key = (r["model"], r.get("defense", "baseline"))
            agg[key][0] += 1 if r.get("utility_correct") else 0
            agg[key][1] += 1
        for (model, defense), (c, n) in sorted(agg.items()):
            out.append(f"| {model} | {defense} | {_pct(c / n)} | {n} |")
        out.append("")

    # --- Attack ---
    atk = [r for r in rows if r.get("kind") == "attack" and r.get("error") is None]
    if atk:
        out.append("## Attack success rate (lower is better)\n")
        out.append("| Scenario | Model | Defense | ASR | 95% CI | N |")
        out.append("|---|---|---|---|---|---|")
        agg = defaultdict(lambda: [0, 0])
        for r in atk:
            key = (r["task_id"], r["model"], r.get("defense", "baseline"))
            agg[key][0] += 1 if r.get("attack_success") else 0
            agg[key][1] += 1
        for (task_id, model, defense), (s, n) in sorted(agg.items()):
            lo, hi = _wilson(s, n)
            out.append(f"| {task_id} | {model} | {defense} | {_pct(s / n)} "
                       f"| {_pct(lo)}–{_pct(hi)} | {n} |")
        out.append("")

    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="?", default="evals/results/runs.jsonl")
    ap.add_argument("--md", default=None, help="Also write the report to this file.")
    args = ap.parse_args()

    if not Path(args.runs).exists():
        print(f"No results at {args.runs}")
        return 1
    rows = load(args.runs)
    report = build_report(rows)
    print(report)
    if args.md:
        Path(args.md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md).write_text(report + "\n", encoding="utf-8")
        print(f"\nWrote {args.md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
