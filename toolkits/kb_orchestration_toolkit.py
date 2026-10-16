import os
import re
import time
from pathlib import Path
from typing import List, Tuple

from dotenv import load_dotenv
from smolagents import tool

from agents.common import rate_limiter

from .kb_task_prompts import (
    KB_API_REFERENCE_TASK,
    KB_ARCHITECTURE_TASK,
    KB_BUILD_AND_TOOLING_TASK,
    KB_DATA_MODELS_TASK,
    KB_OVERVIEW_TASK,
    KB_TESTING_AND_QA_TASK,
)

load_dotenv()
CODEBASE_PATH   = os.getenv("CODEBASE_PATH", "data/sample_codebase")
SUB_AGENTS_ROOT = os.getenv("SUB_AGENTS_ROOT", "data/sub_agents_workspace")
AGENT_WORKSPACE = os.getenv("AGENT_WORKSPACE_PATH", "data/agent_workspace")

os.makedirs(SUB_AGENTS_ROOT, exist_ok=True)
os.makedirs(AGENT_WORKSPACE, exist_ok=True)

def _abs(p: str) -> str:
    return os.path.realpath(os.path.abspath(p))

def _list_top_dirs(base: str) -> List[str]:
    base = _abs(base)
    if not os.path.isdir(base):
        return []
    out = []
    for name in sorted(os.listdir(base)):
        full = os.path.join(base, name)
        if os.path.isdir(full):
            out.append(name)
    return out

@tool
def plan_kb_tasks_from_codebase(max_tasks: int = 6) -> List[str]:
    """
    Create natural-language task descriptions for KB sub-agents.

    Instead of 1 task per top-level directory, we always try to produce
    a small, fixed set of high-level KB "chapters" (OVERVIEW, ARCHITECTURE,
    API_REFERENCE, DATA_MODELS, BUILD_AND_TOOLING, TESTING_AND_QA) that
    describe the project like a mini Code Wiki.

    Args:
        max_tasks (int): Upper bound for number of tasks to generate.
                         This can be used to truncate the list, but not
                         to create more tasks than the predefined set.

    Returns:
        List[str]: Task descriptions to pass into
                   spawn_sub_agents(number_of_subagents, task_descriptions).
    """
    base = _abs(CODEBASE_PATH)
    top_dirs = _list_top_dirs(base)
    dirs_hint = ", ".join(top_dirs) if top_dirs else "no obvious subdirectories"

    # Lightweight signals to specialize some tasks
    has_tests = any("test" in d.lower() for d in top_dirs)
    has_api_like = any(
        name.lower() in {"api", "routes", "controllers", "views"}
        for name in top_dirs
    )

    config_files = []
    for root, _, files in os.walk(base):
        for fname in files:
            lower = fname.lower()
            if lower in {
                "requirements.txt",
                "pyproject.toml",
                "setup.py",
                "package.json",
                "dockerfile",
                ".env",
                ".env.example",
                "config.py",
            }:
                rel = os.path.relpath(os.path.join(root, fname), base).replace("\\", "/")
                config_files.append(rel)
    config_hint = ", ".join(sorted(set(config_files))) if config_files else "no obvious config files"

    tasks: List[str] = []

    # 1) Project overview
    tasks.append(
        KB_OVERVIEW_TASK.format(
            codebase_path=CODEBASE_PATH,
            dirs_hint=dirs_hint,
        )
    )

    # 2) Architecture
    tasks.append(KB_ARCHITECTURE_TASK)

    # 3) API reference (if there is any API-like surface)
    api_hint = (
        "Look for files and directories named api, routes, controllers, views, or similar."
        if not has_api_like
        else "Focus especially on API-related directories: "
             + ", ".join(
                 d
                 for d in top_dirs
                 if d.lower() in {"api", "routes", "controllers", "views"}
             )
             + "."
    )
    tasks.append(
        KB_API_REFERENCE_TASK.format(api_hint=api_hint)
    )

    # 4) Data models
    tasks.append(KB_DATA_MODELS_TASK)

    # 5) Build, configuration, and tooling
    tasks.append(
        KB_BUILD_AND_TOOLING_TASK.format(
            config_hint=config_hint,
        )
    )

    # 6) Tests and quality
    tests_hint = "tests or test_*.py files" if has_tests else "any files whose names suggest tests"
    tasks.append(
        KB_TESTING_AND_QA_TASK.format(
            tests_hint=tests_hint,
        )
    )

    if max_tasks < len(tasks):
        return tasks[:max_tasks]
    return tasks


def _gather_md_files(root: str) -> List[Tuple[str, str]]:
    files = []
    root_abs = _abs(root)
    for r, _, fs in os.walk(root_abs):
        for f in fs:
            if f.lower().endswith(".md"):
                p = os.path.join(r, f)
                rel = os.path.relpath(p, root_abs).replace("\\", "/")
                files.append((rel, p))
    files.sort()
    return files

@tool
def merge_kb_outputs_to_index(index_filename: str = "KB_INDEX.md") -> str:
    """
    Merge all markdown files under SUB_AGENTS_ROOT into a single index file.

    Args:
        index_filename (str): Output filename to create under AGENT_WORKSPACE_PATH.

    Returns:
        str: The relative path of the merged index file.
    """
    md_list = _gather_md_files(SUB_AGENTS_ROOT)
    if not md_list:
        raise FileNotFoundError("No markdown files found under SUB_AGENTS_ROOT.")

    out_path = os.path.join(AGENT_WORKSPACE, index_filename)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # Build a simple ToC + concatenation
    lines = ["# Knowledge Base Index\n", "## Table of Contents\n"]
    for rel, _ in md_list:
        anchor = re.sub(r"[^a-z0-9]+", "-", rel.lower()).strip("-")
        lines.append(f"- [{rel}](#{anchor})")
    lines.append("\n---\n")

    for rel, p in md_list:
        anchor = re.sub(r"[^a-z0-9]+", "-", rel.lower()).strip("-")
        lines.append(f"\n\n---\n\n## {rel}\n<a id='{anchor}'></a>\n")
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            lines.append(f.read())

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    rate_limiter.wait()
    time.sleep(0.5)
    return os.path.relpath(out_path, os.getcwd()).replace("\\", "/")

@tool
def build_kb_short_from_index(
    index_rel_path: str = "KB_INDEX.md",
    short_rel_path: str = "KB_SHORT.md",
) -> str:
    """
    Build a compressed "short" version of the KB index.

    Args:
        index_rel_path (str): Relative path to the full KB index file.
        short_rel_path (str): Relative path to write the compressed KB short file.
    Returns:
        str: The relative path of the compressed KB short file.

    """
    # Resolve paths
    cwd = Path(os.getcwd())
    # index_rel_path is usually something like "data/agent_workspace/KB_INDEX.md"
    index_path = (cwd / index_rel_path).resolve()

    if not index_path.exists():
        raise FileNotFoundError(f"KB index file not found: {index_path}")

    # Short file will live next to the index by default
    short_path = index_path.with_name(Path(short_rel_path).name)

    with open(index_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    # Very simple heuristic compression:
    # - Keep top-level title / intro
    # - For each "## " section, keep the header and first N non-empty lines
    MAX_TOTAL_CHARS = 6000
    LINES_PER_SECTION = 10

    out_lines = []
    out_lines.append("# Short Knowledge Base\n\n")
    out_lines.append(
        "_This is an automatically generated compressed summary of the full KB index. "
        "For full details, see KB_INDEX.md._\n\n"
    )

    current_section = []
    current_header = None

    def flush_section():
        nonlocal out_lines
        if not current_header:
            return
        out_lines.append(current_header)
        non_empty = [ln for ln in current_section if ln.strip()]
        for ln in non_empty[:LINES_PER_SECTION]:
            out_lines.append(ln)
        out_lines.append("\n")

    for ln in lines:
        # Stop if we already exceeded the rough size limit
        if sum(len(x) for x in out_lines) > MAX_TOTAL_CHARS:
            out_lines.append("\n...\n\n(Truncated for brevity. See KB_INDEX.md for full details.)\n")
            break

        # Top-level / section headers
        if ln.startswith("## "):
            # Flush previous section
            flush_section()
            current_header = ln
            current_section = []
        elif ln.startswith("# "):
            # Keep the very first main title once, skip others
            if not any(line.startswith("# ") for line in out_lines):
                out_lines.append(ln)
                out_lines.append("\n")
        else:
            if current_header is None:
                # Intro part before first section
                out_lines.append(ln)
            else:
                current_section.append(ln)

    # Flush last section
    flush_section()

    with open(short_path, "w", encoding="utf-8") as f:
        f.writelines(out_lines)

    # Small throttle to avoid overwhelming any system resources
    rate_limiter.wait()
    time.sleep(0.2)

    # Return path relative to cwd (aynı pattern merge_kb_outputs_to_index ile)
    return os.path.relpath(short_path, os.getcwd()).replace("\\", "/")