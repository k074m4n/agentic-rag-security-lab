"""Live before/after demo: one attack with defenses off, then on.

Runs a single injection scenario against the real chatbot twice — once with no
defenses (the hijack succeeds) and once with the full defense stack (blocked) —
and prints a clean comparison. Makes two real model calls, so it needs an API
key in .env. Nice to record as a short GIF for the README.

    uv run python -m scripts.live.demo [model_id] [scenario_id]
"""

from __future__ import annotations

import os
import sys
import tempfile

C = {
    "red": "\033[31m", "green": "\033[32m", "yellow": "\033[33m",
    "cyan": "\033[36m", "bold": "\033[1m", "dim": "\033[2m", "end": "\033[0m",
}


def _run(model: str, scenario: str, layers: str) -> tuple[str, bool]:
    from evals.grading import GradeContext
    from evals.tasks import get_task
    from evals.workspace import build_workspace

    os.environ["LITELLM_MODEL"] = model
    os.environ["SECURE_LAYERS"] = layers
    os.environ.setdefault("GLOBAL_RPM", "30")

    task = get_task(scenario)
    with tempfile.TemporaryDirectory(prefix="demo_") as tmp:
        env = build_workspace(tmp, overlay=task.overlay, use_kb=task.use_kb_fixture)
        os.environ.update(env)
        from agents import defense
        from agents.tool_calling_agent import ToolCallingAgent

        bot = ToolCallingAgent(tools=[], max_steps=6)
        answer = defense.sanitize_output(str(bot.run(task.question).output))
        ok = bool(task.grader(GradeContext(answer=answer)))
    return answer, ok


def main() -> int:
    model = sys.argv[1] if len(sys.argv) > 1 else "openrouter/openai/gpt-oss-120b"
    scenario = sys.argv[2] if len(sys.argv) > 2 else "a_indirect"

    from evals.tasks import get_task
    task = get_task(scenario)

    print(f"\n{C['bold']}Agentic RAG Security Lab — live demo{C['end']}")
    print(f"{C['dim']}model: {model}   scenario: {scenario} ({task.note}){C['end']}")
    print(f"{C['dim']}user asks: {task.question!r}{C['end']}\n")

    print(f"{C['yellow']}[1/2] defenses OFF …{C['end']}")
    ans_off, ok_off = _run(model, scenario, "")
    verdict = f"{C['red']}{C['bold']}HIJACKED{C['end']}" if ok_off else f"{C['green']}resisted{C['end']}"
    print(f"      assistant said: {C['dim']}{ans_off[:120].strip()!r}{C['end']}")
    print(f"      result: {verdict}\n")

    print(f"{C['yellow']}[2/2] defenses FULL (d1-d5) …{C['end']}")
    ans_on, ok_on = _run(model, scenario, "d1,d2,d3,d4,d5")
    verdict = f"{C['red']}{C['bold']}HIJACKED{C['end']}" if ok_on else f"{C['green']}{C['bold']}BLOCKED{C['end']}"
    print(f"      assistant said: {C['dim']}{ans_on[:120].strip()!r}{C['end']}")
    print(f"      result: {verdict}\n")

    print(f"{C['cyan']}summary:{C['end']}  defenses off → "
          f"{'attack won' if ok_off else 'no effect'}   |   defenses on → "
          f"{'attack won' if ok_on else 'attack stopped'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
