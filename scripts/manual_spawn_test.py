# scripts/manual_spawn_test.py
import os
from dotenv import load_dotenv
from toolkits.scoped_filesystem_toolkit import create_scoped_filesystem_tools

load_dotenv()
CODEBASE_PATH   = os.getenv("CODEBASE_PATH", "data/sample_codebase")
SUB_AGENTS_ROOT = os.getenv("SUB_AGENTS_ROOT", "data/sub_agents_workspace")

os.makedirs(SUB_AGENTS_ROOT, exist_ok=True)
workspace = os.path.join(SUB_AGENTS_ROOT, "sub_agent_manual")
os.makedirs(workspace, exist_ok=True)

tools = create_scoped_filesystem_tools(
    codebase_root=os.path.abspath(CODEBASE_PATH),
    workspace_root=os.path.abspath(workspace),
)

# tools listesinden write_workspace_file fonksiyonunu bul
write_tool = None
for t in tools:
    if t.name == "write_workspace_file":
        write_tool = t
        break
assert write_tool, "write_workspace_file tool not found"

# DOĞRUDAN çağır (LLM yok)
result = write_tool("manual.md", "# Manual Smoke\nThis was written directly.")
print("RESULT:", result)
print("CHECK PATH:", os.path.join(workspace, "manual.md"))
