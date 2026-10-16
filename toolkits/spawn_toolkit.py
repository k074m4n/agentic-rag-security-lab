from dotenv import load_dotenv
from smolagents import tool

import os, time, random
from typing import List

from smolagents.agents import ToolCallingAgent as SmolToolCallingAgent

from agents.common import make_model, rate_limiter

try:
    from litellm.exceptions import RateLimitError as LiteRateLimitError
except Exception:
    LiteRateLimitError = Exception

from toolkits.scoped_filesystem_toolkit import create_scoped_filesystem_tools

load_dotenv()
LITELLM_MODEL_ID = os.getenv("LITELLM_MODEL_ID")
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY")
CODEBASE_PATH   = os.getenv("CODEBASE_PATH", "data/sample_codebase")
SUB_AGENTS_ROOT = os.getenv("SUB_AGENTS_ROOT", "data/sub_agents_workspace")

os.makedirs(SUB_AGENTS_ROOT, exist_ok=True)

def _abs_norm(p: str) -> str:
    return os.path.realpath(os.path.abspath(p))

@tool
def spawn_sub_agents(number_of_subagents: int, task_descriptions: List[str]) -> str:
    """
    Spawn multiple sub-agents to analyze parts of the codebase based on provided task descriptions.
    Args:
        number_of_subagents (int): Number of sub-agents to spawn.
        task_descriptions (List[str]): List of natural-language task descriptions for each sub-agent.
    Returns:
        str: Summary message indicating completion and locations of results.
    """
    if number_of_subagents <= 0:
        raise ValueError("number_of_subagents must be > 0")
    if len(task_descriptions) != number_of_subagents:
        raise ValueError("task_descriptions length must equal number_of_subagents")

    workspaces: List[str] = []
    codebase_root = _abs_norm(CODEBASE_PATH)

    # Emin olmak için seri; model tarafında da tek-kanal throttling var.
    for i in range(number_of_subagents):
        workspace_root = _abs_norm(os.path.join(SUB_AGENTS_ROOT, f"sub_agent_{i}"))
        os.makedirs(workspace_root, exist_ok=True)
        workspaces.append(workspace_root)

        scoped_tools = create_scoped_filesystem_tools(
            codebase_root=codebase_root, workspace_root=workspace_root
        )

        # --- MODELİ TEK YERDEN OLUŞTUR (throttled) ---
        model = make_model(role="kb_worker") 

        # smol ToolCallingAgent (bizim wrapper değil)
        worker = SmolToolCallingAgent(
            name=f"sub_agent_{i}",
            description="Scoped filesystem worker that analyzes code and writes markdown outputs.",
            tools=scoped_tools,
            # Max steps’i çok abartmayalım; gerektikçe artırırız
            max_steps=6,
            model=model,
            instructions=(
                "You are a documentation-focused sub-agent responsible for a SINGLE KB "
                "chapter about the codebase. Use get_codebase_tree, list_codebase_directory, "
                "and read_codebase_file to explore the repository, then WRITE one focused "
                "MARKDOWN file into your workspace using write_workspace_file(). "
                "Follow the task description carefully: respect the requested filename "
                "(e.g. OVERVIEW.md, ARCHITECTURE.md, API_REFERENCE.md) and structure. "
                "Include a clear title, a small table of contents, short sections, and "
                "code blocks or simple text diagrams when helpful."
            ),  
            return_full_result=True,
        )

        # --- DIŞ BACKOFF ZIRHI (ihtiyaten) ---
        attempt = 0
        while True:
            attempt += 1
            try:
                # RPM throttling (global): model.generate tarafında da var; burada minik bekleme + jitter
                rate_limiter.wait()
                time.sleep(random.uniform(0.15, 0.35))
                worker.run(task_descriptions[i])
                break  # başarı
            except LiteRateLimitError as e:
                # 429 ise exponential backoff + ufak jitter
                sleep_s = min(30, (1.6 ** attempt)) + random.uniform(0.0, 0.6)
                time.sleep(sleep_s)
                continue
            except Exception as e:
                # Diğer hatalar: aynen fırlat
                raise

        # Bir sonraki sub-agent’a geçmeden minik ayrışma (thundering herd riskini azaltır)
        time.sleep(random.uniform(0.2, 0.5))

    rels = [os.path.relpath(p, start=os.getcwd()) for p in workspaces]
    return f"All {number_of_subagents} sub-agents completed. Results in: {', '.join(rels)}"
