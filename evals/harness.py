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
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
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


def _do_run(model, task, defense, trial, max_steps, timeout, per_run_cap):
    """Build an isolated workspace and run one task in a subprocess."""
    with tempfile.TemporaryDirectory(prefix="eval_") as tmp:
        use_kb = task.use_kb_fixture and not task.build_kb
        workspace_env = build_workspace(tmp, overlay=task.overlay, use_kb=use_kb)
        rec = _run_subprocess(model, task, defense, trial, workspace_env,
                              cost_cap=per_run_cap, max_steps=max_steps, timeout=timeout)
    rec["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    return rec


def run_sweep(models, kinds, ids, defenses, trials, budget, max_steps, timeout,
              out_path, concurrency=1):
    tasks = get_tasks(kinds=kinds, ids=ids)
    if not tasks:
        print("No tasks selected.", file=sys.stderr)
        return 1

    plan = [(m, t, d, i)
            for m in models for d in defenses for t in tasks for i in range(trials)]
    total = len(plan)
    print(f"Planned {total} runs: {len(models)} model(s) x {len(defenses)} defense(s) "
          f"x {len(tasks)} task(s) x {trials} trial(s). Budget ${budget:.2f}, "
          f"concurrency {concurrency}.", file=sys.stderr)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    state = {"spent": 0.0, "done": 0, "stop": False}
    lock = threading.Lock()
    out = out_path.open("a", encoding="utf-8")
    t_start = time.time()

    def commit(rec):
        with lock:
            out.write(json.dumps(rec) + "\n")
            out.flush()
            state["spent"] += float(rec.get("cost", 0.0) or 0.0)
            state["done"] += 1
            done, spent = state["done"], state["spent"]
            if rec.get("budget_exceeded"):
                state["stop"] = True
        flag = ""
        if rec.get("error"):
            flag = f"  ERROR: {rec['error'][:80]}"
        elif rec.get("kind") == "utility":
            flag = "  util=" + ("OK" if rec.get("utility_correct") else "miss")
        elif rec.get("kind") == "attack":
            flag = "  attack=" + ("SUCCESS" if rec.get("attack_success") else "blocked")
        print(f"[{done}/{total}] {rec.get('model', '').split('/')[-1]:22} "
              f"{rec.get('task_id', ''):18} trial{rec.get('trial', 0)} "
              f"${spent:.4f}{flag}", file=sys.stderr)

    def per_cap():
        # Hard cap for a single run: bound a runaway without starving a normal run.
        return min(0.50, max(0.01, budget - state["spent"]))

    def budget_ok():
        with lock:
            return not state["stop"] and state["spent"] < budget

    if concurrency <= 1:
        for item in plan:
            if not budget_ok():
                break
            commit(_do_run(*item, max_steps, timeout, per_cap()))
    else:
        it = iter(plan)
        inflight = set()
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            def submit_next():
                item = next(it, None)
                if item is None or not budget_ok():
                    return False
                inflight.add(ex.submit(_do_run, *item, max_steps, timeout, per_cap()))
                return True

            for _ in range(concurrency):
                if not submit_next():
                    break
            while inflight:
                finished, inflight = wait(inflight, return_when=FIRST_COMPLETED)
                for fut in finished:
                    commit(fut.result())
                while budget_ok() and len(inflight) < concurrency:
                    if not submit_next():
                        break

    out.close()
    dt = time.time() - t_start
    if state["spent"] >= budget or state["stop"]:
        print(f"Budget ${budget:.2f} reached.", file=sys.stderr)
    print(f"\nDone: {state['done']}/{total} runs, ${state['spent']:.4f} spent, "
          f"{dt/60:.1f} min. Results in {out_path}", file=sys.stderr)
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
    ap.add_argument("--concurrency", type=int, default=1,
                    help="Parallel runs (each its own subprocess and workspace).")
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
        concurrency=args.concurrency,
    )


if __name__ == "__main__":
    sys.exit(main())
