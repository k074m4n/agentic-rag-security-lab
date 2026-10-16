"""Orchestrate an eval sweep: (models x tasks x trials), one subprocess each.

Each run gets a fresh isolated workspace and runs in its own process, so module
state and files never leak between runs. Provider-reported cost is accumulated
across runs; the sweep stops launching new runs once the global budget cap is
reached, and each subprocess also carries the remaining budget as its own hard
cap so a single runaway run cannot overshoot.

Results are appended to a JSONL file as they complete, so a sweep that is
interrupted (or hits the budget) still leaves usable data.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from evals.tasks import get_tasks
from evals.workspace import build_workspace

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_subprocess(model, task, defense, trial, workspace_env, cost_cap, max_steps, timeout):
    env = {**os.environ, **workspace_env, "LITELLM_MODEL": model}
    cmd = [
        sys.executable, "-m", "evals.run_one",
        "--model", model,
        "--task", task.id,
        "--target", task.target,
        "--defense", defense,
        "--trial", str(trial),
        "--max-steps", str(max_steps),
    ]
    if cost_cap is not None:
        cmd += ["--cost-cap", f"{cost_cap:.6f}"]

    try:
        proc = subprocess.run(
            cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"model": model, "task_id": task.id, "defense": defense, "trial": trial,
                "error": f"timeout after {timeout}s", "cost": 0.0, "budget_exceeded": False}

    stdout = proc.stdout.strip().splitlines()
    for line in reversed(stdout):  # last JSON line is the record
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {"model": model, "task_id": task.id, "defense": defense, "trial": trial,
            "error": f"no record (rc={proc.returncode}): {proc.stderr[-400:]}",
            "cost": 0.0, "budget_exceeded": False}


def run_sweep(models, kinds, ids, defenses, trials, budget, max_steps, timeout, out_path):
    tasks = get_tasks(kinds=kinds, ids=ids)
    if not tasks:
        print("No tasks selected.", file=sys.stderr)
        return 1

    plan = [(m, t, d, i)
            for m in models for d in defenses for t in tasks for i in range(trials)]
    total = len(plan)
    print(f"Planned {total} runs: {len(models)} model(s) x {len(defenses)} defense(s) "
          f"x {len(tasks)} task(s) x {trials} trial(s). Budget cap ${budget:.2f}.",
          file=sys.stderr)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    spent = 0.0
    done = 0
    t_start = time.time()

    with out_path.open("a", encoding="utf-8") as out:
        for model, task, defense, trial in plan:
            remaining = budget - spent
            if remaining <= 0:
                print(f"Budget ${budget:.2f} reached; stopping with {done}/{total} runs done.",
                      file=sys.stderr)
                break

            with tempfile.TemporaryDirectory(prefix="eval_") as tmp:
                workspace_env = build_workspace(tmp, overlay=task.overlay)
                rec = _run_subprocess(model, task, defense, trial, workspace_env,
                                      cost_cap=remaining, max_steps=max_steps, timeout=timeout)

            rec["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            out.write(json.dumps(rec) + "\n")
            out.flush()

            spent += float(rec.get("cost", 0.0) or 0.0)
            done += 1
            flag = ""
            if rec.get("error"):
                flag = f"  ERROR: {rec['error'][:80]}"
            elif rec.get("kind") == "utility":
                flag = "  util=" + ("OK" if rec.get("utility_correct") else "miss")
            elif rec.get("kind") == "attack":
                flag = "  attack=" + ("SUCCESS" if rec.get("attack_success") else "blocked")
            print(f"[{done}/{total}] {model.split('/')[-1]:22} {task.id:14} "
                  f"trial{trial} ${spent:.4f}{flag}", file=sys.stderr)

            if rec.get("budget_exceeded"):
                print("A run hit the hard cost cap; stopping sweep.", file=sys.stderr)
                break

    dt = time.time() - t_start
    print(f"\nDone: {done} runs, ${spent:.4f} spent, {dt/60:.1f} min. Results in {out_path}",
          file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Run an eval sweep.")
    ap.add_argument("--models", required=True,
                    help="Comma-separated LiteLLM model ids.")
    ap.add_argument("--kinds", default="utility",
                    help="Comma-separated task kinds (utility,attack).")
    ap.add_argument("--ids", default=None, help="Comma-separated task ids (overrides kinds).")
    ap.add_argument("--defenses", default="baseline", help="Comma-separated defense profiles.")
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--budget", type=float, default=1.0, help="Hard USD cap for the whole sweep.")
    ap.add_argument("--max-steps", type=int, default=6)
    ap.add_argument("--timeout", type=int, default=600, help="Per-run timeout (s).")
    ap.add_argument("--out", default="evals/results/runs.jsonl")
    args = ap.parse_args()

    return run_sweep(
        models=[m.strip() for m in args.models.split(",") if m.strip()],
        kinds=[k.strip() for k in args.kinds.split(",") if k.strip()],
        ids=[i.strip() for i in args.ids.split(",")] if args.ids else None,
        defenses=[d.strip() for d in args.defenses.split(",") if d.strip()],
        trials=args.trials,
        budget=args.budget,
        max_steps=args.max_steps,
        timeout=args.timeout,
        out_path=args.out,
    )


if __name__ == "__main__":
    sys.exit(main())
