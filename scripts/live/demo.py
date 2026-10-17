"""Live before/after demo: one attack with defenses off, then on.

Runs a single injection scenario against the real chatbot twice — once with no
defenses (the hijack succeeds) and once with the full defense stack (blocked) —
and prints a clean comparison. Each run is its own subprocess with its own
isolated workspace (same as the eval harness), so module-level paths never go
stale between runs. Needs an API key in .env; makes two real model calls.

    uv run python -m scripts.live.demo [model_id] [scenario_id]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
C = {
    "red": "\033[31m", "green": "\033[32m", "yellow": "\033[33m",
    "cyan": "\033[36m", "bold": "\033[1m", "dim": "\033[2m", "end": "\033[0m",
}


def _run(model: str, scenario: str, defense: str, task) -> dict:
    from evals.workspace import build_workspace

    with tempfile.TemporaryDirectory(prefix="demo_") as tmp:
        use_kb = task.use_kb_fixture and not task.build_kb
        wsenv = build_workspace(tmp, overlay=task.overlay, use_kb=use_kb)
        env = {**os.environ, **wsenv, "LITELLM_MODEL": model, "GLOBAL_RPM": "30"}
        proc = subprocess.run(
            [sys.executable, "-m", "evals.run_one", "--model", model,
             "--task", scenario, "--defense", defense, "--target", task.target],
            cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=240,
        )
    for line in reversed(proc.stdout.strip().splitlines()):
        if line.startswith("{"):
            return json.loads(line)
    raise RuntimeError(f"no record: {proc.stderr[-300:]}")


def main() -> int:
    model = sys.argv[1] if len(sys.argv) > 1 else "openrouter/google/gemini-2.5-flash-lite"
    scenario = sys.argv[2] if len(sys.argv) > 2 else "a_indirect"

    from evals.tasks import get_task
    task = get_task(scenario)
    success_key = "attack_success"

    print(f"\n{C['bold']}Agentic RAG Security Lab — live demo{C['end']}")
    print(f"{C['dim']}model: {model}{C['end']}")
    print(f"{C['dim']}scenario: {scenario} ({task.note}){C['end']}")
    print(f"{C['dim']}user asks: {task.question!r}{C['end']}\n")

    for label, defense in (("defenses OFF", "baseline"), ("defenses FULL (d1-d5)", "full")):
        print(f"{C['yellow']}{label} …{C['end']}")
        rec = _run(model, scenario, defense, task)
        hit = bool(rec.get(success_key))
        answer = (rec.get("answer") or "").strip().replace("\n", " ")
        verdict = (f"{C['red']}{C['bold']}HIJACKED{C['end']}" if hit
                   else f"{C['green']}{C['bold']}BLOCKED{C['end']}")
        print(f"  tools: {C['dim']}{' -> '.join(rec.get('tools', [])) or '(none)'}{C['end']}")
        print(f"  answer: {C['dim']}{answer[:140]!r}{C['end']}")
        print(f"  result: {verdict}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
