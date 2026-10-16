"""Run a single eval task in the current (already-isolated) environment.

Invoked as a subprocess by the harness, once per (model, task, trial). The
harness sets CODEBASE_PATH / AGENT_WORKSPACE_PATH / ... in this process's
environment to point at a throwaway workspace, so the toolkits' module-level
path reads resolve there. This script prints exactly one JSON record to stdout;
diagnostics go to stderr.

    python -m evals.run_one --model <id> --task <task_id> [--target chatbot] \
        [--defense baseline] [--trial 0] [--cost-cap 0.50] [--max-steps 6]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time


def _extract_run(agent) -> dict:
    """Pull tool names, token/cost totals and step count out of agent memory."""
    from smolagents.memory import ActionStep

    tools: list[str] = []
    cost = 0.0
    steps = 0
    for step in agent.memory.steps:
        if not isinstance(step, ActionStep):
            continue
        steps += 1
        for call in step.tool_calls or []:
            tools.append(call.name)
        raw = getattr(step.model_output_message, "raw", None)
        usage = getattr(raw, "usage", None)
        if usage is not None:
            cost += float(getattr(usage, "cost", 0.0) or 0.0)
    return {"tools": tools, "steps": steps, "memory_cost": round(cost, 6)}


def _build_chatbot(max_steps: int):
    from agents.tool_calling_agent import ToolCallingAgent

    return ToolCallingAgent(tools=[], max_steps=max_steps)


def _build_manager(max_steps: int):
    from agents.manager_agent import ManagerAgent
    from agents.tool_calling_agent import ToolCallingAgent

    chatbot = ToolCallingAgent(tools=[], max_steps=max_steps)
    return ManagerAgent(tools=[], managed_agents=[chatbot.agent], max_steps=max_steps)


def _maybe_build_kb() -> None:
    from toolkits.kb_orchestration_toolkit import (
        build_kb_short_from_index,
        merge_kb_outputs_to_index,
        plan_kb_tasks_from_codebase,
    )
    from toolkits.rag_toolkit import build_rag_index_for_kb
    from toolkits.spawn_toolkit import spawn_sub_agents

    tasks = plan_kb_tasks_from_codebase(max_tasks=6)
    spawn_sub_agents(number_of_subagents=len(tasks), task_descriptions=tasks)
    index_path = merge_kb_outputs_to_index("KB_INDEX.md")
    build_kb_short_from_index(
        index_rel_path=index_path,
        short_rel_path=os.path.join(os.path.dirname(index_path), "KB_SHORT.md"),
    )
    build_rag_index_for_kb(include_codebase=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--target", default="chatbot", choices=["chatbot", "manager"])
    ap.add_argument("--defense", default="baseline")
    ap.add_argument("--trial", type=int, default=0)
    ap.add_argument("--cost-cap", type=float, default=None)
    ap.add_argument("--max-steps", type=int, default=6)
    args = ap.parse_args()

    os.environ["LITELLM_MODEL"] = args.model
    os.environ.setdefault("GLOBAL_RPM", "30")

    from agents.common import BudgetExceeded, cost_meter
    from evals.tasks import get_task

    task = get_task(args.task)
    cost_meter.reset(cap=args.cost_cap)

    record = {
        "model": args.model,
        "task_id": task.id,
        "kind": task.kind,
        "target": args.target,
        "defense": args.defense,
        "trial": args.trial,
        "build_kb": task.build_kb,
        "answer": "",
        "tools": [],
        "steps": 0,
        "utility_correct": None,
        "attack_success": None,
        "error": None,
        "budget_exceeded": False,
    }

    t0 = time.time()
    try:
        if task.build_kb:
            _maybe_build_kb()
        agent = _build_manager(args.max_steps) if args.target == "manager" else _build_chatbot(args.max_steps)
        result = agent.run(task.question)
        answer = str(getattr(result, "output", result))
        record["answer"] = answer
        record.update(_extract_run(agent.agent))
        success = bool(task.grader(answer))
        if task.kind == "utility":
            record["utility_correct"] = success
        else:
            record["attack_success"] = success
    except BudgetExceeded as exc:
        record["error"] = str(exc)
        record["budget_exceeded"] = True
    except Exception as exc:  # noqa: BLE001 - record and move on; one bad run must not stop the sweep
        record["error"] = f"{type(exc).__name__}: {exc}"

    snap = cost_meter.snapshot()
    record["cost"] = snap["total_cost"]
    record["input_tokens"] = snap["input_tokens"]
    record["output_tokens"] = snap["output_tokens"]
    record["calls"] = snap["calls"]
    record["duration_s"] = round(time.time() - t0, 2)

    print(json.dumps(record))
    return 0


if __name__ == "__main__":
    sys.exit(main())
