"""Build an isolated, throwaway workspace for a single eval run.

Copies the clean sample codebase into a temp directory and creates empty
agent/KB/RAG directories next to it. The run's agents are pointed at these via
environment variables, so nothing touches the tracked repo and two runs can
never see each other's writes. Attack overlays (added later) are applied on top
of the copied codebase here, never in the source tree.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_CODEBASE = REPO_ROOT / "data" / "sample_codebase"
SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"

_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "*.sqlite3")


def build_workspace(dest: str | os.PathLike, overlay: str | None = None) -> dict:
    """Create an isolated workspace under ``dest`` and return env overrides.

    The returned dict is meant to be merged into the environment of the process
    that will run the agent (CODEBASE_PATH etc.), so module-level path reads in
    the toolkits resolve to this throwaway copy.
    """
    dest = Path(dest)
    codebase = dest / "codebase"
    agent_ws = dest / "agent_workspace"
    sub_ws = dest / "sub_agents_workspace"
    rag_dir = dest / "rag_index"

    if not SAMPLE_CODEBASE.is_dir():
        raise FileNotFoundError(f"Sample codebase not found at {SAMPLE_CODEBASE}")

    shutil.copytree(SAMPLE_CODEBASE, codebase, ignore=_IGNORE)
    for d in (agent_ws, sub_ws, rag_dir):
        d.mkdir(parents=True, exist_ok=True)

    if overlay:
        _apply_overlay(overlay, codebase)

    return {
        "CODEBASE_PATH": str(codebase),
        "AGENT_WORKSPACE_PATH": str(agent_ws),
        "SUB_AGENTS_ROOT": str(sub_ws),
        "RAG_INDEX_DIR": str(rag_dir),
    }


def _apply_overlay(overlay: str, codebase: Path) -> None:
    """Copy files from evals/scenarios/<overlay>/ over the codebase copy.

    Keeps attack payloads out of the tracked application tree: they exist only
    under evals/scenarios/ and only ever land in a temp copy.
    """
    src = SCENARIOS_DIR / overlay
    if not src.is_dir():
        raise FileNotFoundError(f"Overlay not found: {src}")
    for path in src.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(src)
        target = codebase / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
