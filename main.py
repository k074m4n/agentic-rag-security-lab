import os

from dotenv import load_dotenv
from loguru import logger

from agents.base_agent import BaseAgent
from agents.code_agent import CodeAgent
from agents.manager_agent import ManagerAgent
from agents.tool_calling_agent import ToolCallingAgent
from toolkits.kb_orchestration_toolkit import (
    build_kb_short_from_index,
    merge_kb_outputs_to_index,
    plan_kb_tasks_from_codebase,
)
from toolkits.rag_toolkit import build_rag_index_for_kb
from toolkits.spawn_toolkit import spawn_sub_agents
from ui.gradio_agent_ui import GradioAgentUI

# from phoenix.otel import register
# from openinference.instrumentation.smolagents import SmolagentsInstrumentor

load_dotenv()

AUTO_BUILD_KB = os.getenv("AUTO_BUILD_KB", "false").lower() == "true"
# CodeAgent runs model-written Python in-process (LocalPythonExecutor is not a security
# boundary). Off by default; see README "Known attack surface".
ENABLE_CODE_AGENT = os.getenv("ENABLE_CODE_AGENT", "false").lower() == "true"
# Phoenix/OpenInference şimdilik kapalı
# register()
# SmolagentsInstrumentor().instrument()

KB_ORCHESTRATION_MODE = os.getenv("KB_ORCHESTRATION_MODE", "deter").lower()
# "deter"  -> deterministik plan→spawn→merge (LLM sadece sub-agent'larda)
# "agent"   -> eski davranış: ManagerAgent.run(...) ile orkestrasyon

def kickoff_kb_build(manager_agent: BaseAgent) -> None:
    """
    KB build pipeline'ını iki farklı modda çalıştırır:

    - KB_ORCHESTRATION_MODE == "agent":
        Eski davranış: ManagerAgent'e tek bir yüksek seviye prompt ver,
        o da plan_kb_tasks_from_codebase / spawn_sub_agents /
        merge_kb_outputs_to_index sırasını kendi LLM döngüsüyle yönetsin.

    - KB_ORCHESTRATION_MODE == "deter":
        Deterministik pipeline: plan → spawn → merge çağrılarını
        doğrudan Python'dan yap. LLM sadece sub-agent'ların içinde
        (markdown chapter yazarken) kullanılacak.
    """
    print(f"[KB] Starting auto-build in '{KB_ORCHESTRATION_MODE}' mode…")

    if KB_ORCHESTRATION_MODE == "agent":
        # --- Eski agentik orchestrasyon ---
        prompt = (
            "Build the Knowledge Base for the current codebase using your tools. "
            "First call plan_kb_tasks_from_codebase(max_tasks=6), then "
            "call spawn_sub_agents with those tasks, then call "
            "merge_kb_outputs_to_index('KB_INDEX.md'). "
            "When you are done, return only the path to the merged KB index file."
        )
        out = manager_agent.run(prompt)
        print("[KB] Auto-build done (agent mode).\n", out)

    else:
        # --- Deterministik orchestrasyon (LLM sadece worker'larda) ---
        print("[KB] Planning KB tasks…")
        tasks = plan_kb_tasks_from_codebase(max_tasks=6)
        print(f"[KB] Planned {len(tasks)} tasks.")

        print("[KB] Spawning sub-agents…")
        spawn_summary = spawn_sub_agents(
            number_of_subagents=len(tasks),
            task_descriptions=tasks,
        )
        print("[KB]", spawn_summary)

        print("[KB] Merging KB markdown outputs…")
        index_path = merge_kb_outputs_to_index("KB_INDEX.md")
        print(f"[KB] KB index at: {index_path}")

        print("[KB] Building KB_SHORT.md from KB_INDEX.md…")
        short_path = build_kb_short_from_index(
            index_rel_path=index_path,
            short_rel_path=os.path.join(os.path.dirname(index_path), "KB_SHORT.md"),
        )
        print(f"[KB] Short KB at: {short_path}")

        print("[KB] Building RAG index over KB files…")
        rag_summary = build_rag_index_for_kb(include_codebase=False)
        print("[KB]", rag_summary)

        print("[KB] Auto-build done (deter mode).")


def main() -> None:
    # === STEP 1: Worker agents ===
    # KB'yi (search_kb/read_kb_file) kullanabilen chatbot
    tool_calling_agent: BaseAgent = ToolCallingAgent(tools=[])

    managed_agents = [tool_calling_agent.agent]

    # Örnek code agent (dış tool yok, placeholder) — yalnızca açıkça istenirse
    if ENABLE_CODE_AGENT:
        logger.warning("ENABLE_CODE_AGENT=true: code_agent executes model-written Python locally.")
        managed_agents.append(CodeAgent(tools=[]).agent)

    # === STEP 2: Manager agent ===
    # ManagerAgent kendi içinde KB orchestration tool'larını ekliyor
    manager_agent: BaseAgent = ManagerAgent(
        tools=[],
        managed_agents=managed_agents,
    )

    # Otomatik KB build (isteğe bağlı, .env üzerinden)
    if AUTO_BUILD_KB:
        kickoff_kb_build(manager_agent)

    # === STEP 3: UI ===
    ui = GradioAgentUI(agent=manager_agent)
    logger.info("Launching Gradio UI…")
    ui.launch()


if __name__ == "__main__":
    main()
