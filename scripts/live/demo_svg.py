"""Render the before/after demo as an SVG card for the README.

Runs one injection scenario twice (defenses off, then full) against the real
chatbot, each in its own isolated subprocess, and saves a terminal-style SVG to
media/demo.svg. Needs an API key in .env; makes two real model calls.

    uv run python -m scripts.live.demo_svg [model_id] [scenario_id]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from rich.console import Console
from rich.text import Text

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(model: str, scenario: str, defense: str, task) -> dict:
    from evals.workspace import build_workspace

    with tempfile.TemporaryDirectory(prefix="demosvg_") as tmp:
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

    con = Console(record=True, width=92)
    con.print()
    con.print(Text("  Agentic RAG Security Lab — one attack, defenses off vs on", style="bold"))
    con.print(Text(f"  user asks: {task.question}", style="dim"))
    con.print()

    for label, defense in (("defenses OFF ", "baseline"), ("defenses FULL", "full")):
        rec = _run(model, scenario, defense, task)
        hit = bool(rec.get("attack_success"))
        ans = (rec.get("answer") or "").strip().replace("\n", " ")[:88]
        verdict = Text("  HIJACKED", style="bold red") if hit else Text("  BLOCKED", style="bold green")
        con.print(Text(f"  [{label}]", style="yellow"), end="")
        con.print(verdict, end="")
        tail = " — obeyed the hidden instruction" if hit else " — ignored the trap, answered the user"
        con.print(Text(tail, style="dim"))
        con.print(Text(f"      → {ans!r}", style="grey58"))
        con.print()

    out = REPO_ROOT / "media" / "demo.svg"
    con.save_svg(str(out), title="agentic-rag-security-lab")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
