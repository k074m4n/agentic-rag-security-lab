"""Build a frozen KB fixture from the clean sample codebase, once.

The KB build spawns several sub-agents and is expensive and stochastic. For
utility and injection-free runs we want realistic retrieval without paying that
cost (or that variance) on every run, so we build the KB a single time from the
clean codebase and freeze the artifacts under ``evals/fixtures/kb/``. The
workspace builder then drops this fixture into each run.

Holding one KB constant across all models under test is also more rigorous: it
measures the chat model's behavior, not KB-build noise. Stored-injection
scenarios, which must poison the KB, build their own KB from a poisoned overlay
instead of using this fixture.

    python -m evals.build_kb_fixture [--model <id>]

Run from the repo root. Needs an API key in .env. Costs roughly a few cents.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "kb"


def _build_in(workspace_env: dict) -> None:
    from toolkits.kb_orchestration_toolkit import (
        build_kb_short_from_index,
        merge_kb_outputs_to_index,
        plan_kb_tasks_from_codebase,
    )
    from toolkits.rag_toolkit import build_rag_index_for_kb
    from toolkits.spawn_toolkit import spawn_sub_agents

    tasks = plan_kb_tasks_from_codebase(max_tasks=6)
    print(f"[kb] planned {len(tasks)} chapters", file=sys.stderr)
    spawn_sub_agents(number_of_subagents=len(tasks), task_descriptions=tasks)
    index_path = merge_kb_outputs_to_index("KB_INDEX.md")
    build_kb_short_from_index(
        index_rel_path=index_path,
        short_rel_path=os.path.join(os.path.dirname(index_path), "KB_SHORT.md"),
    )
    print(build_rag_index_for_kb(include_codebase=False), file=sys.stderr)


def _normalize_rag_paths(rag_file: Path) -> None:
    """Replace the temp build path in the index with a stable, repo-relative one.

    The stored path is display-only (retrieval uses embeddings + text), but a
    committed fixture should not leak a /tmp build path.
    """
    data = json.loads(rag_file.read_text(encoding="utf-8"))
    for doc in data.get("documents", []):
        src = doc.get("source_file", "")
        doc["path"] = f"data/agent_workspace/{src}"
    rag_file.write_text(json.dumps(data), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="openrouter/openai/gpt-oss-120b")
    args = ap.parse_args()

    os.environ["LITELLM_MODEL"] = args.model
    os.environ.setdefault("GLOBAL_RPM", "30")

    from agents.common import cost_meter
    from evals.workspace import build_workspace

    cost_meter.reset(cap=None)

    with tempfile.TemporaryDirectory(prefix="kb_fixture_") as tmp:
        env = build_workspace(tmp)  # clean codebase, empty KB/RAG dirs
        os.environ.update(env)
        _build_in(env)

        agent_ws = Path(env["AGENT_WORKSPACE_PATH"])
        rag_dir = Path(env["RAG_INDEX_DIR"])
        index = agent_ws / "KB_INDEX.md"
        short = agent_ws / "KB_SHORT.md"
        rag = rag_dir / "kb_rag_index.json"
        for f in (index, short, rag):
            if not f.is_file():
                print(f"[kb] missing expected artifact: {f}", file=sys.stderr)
                return 1

        if FIXTURE_DIR.exists():
            shutil.rmtree(FIXTURE_DIR)
        (FIXTURE_DIR / "agent_workspace").mkdir(parents=True)
        (FIXTURE_DIR / "rag_index").mkdir(parents=True)
        shutil.copy2(index, FIXTURE_DIR / "agent_workspace" / "KB_INDEX.md")
        shutil.copy2(short, FIXTURE_DIR / "agent_workspace" / "KB_SHORT.md")
        shutil.copy2(rag, FIXTURE_DIR / "rag_index" / "kb_rag_index.json")
        _normalize_rag_paths(FIXTURE_DIR / "rag_index" / "kb_rag_index.json")

    snap = cost_meter.snapshot()
    print(f"[kb] fixture written to {FIXTURE_DIR} "
          f"(${snap['total_cost']:.4f}, {snap['calls']} calls)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
