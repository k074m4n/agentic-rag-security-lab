import os
from typing import List

from dotenv import load_dotenv
from loguru import logger
from smolagents import Tool
from smolagents.agents import ToolCallingAgent as SmolToolCallingAgent

from agents.base_agent import BaseAgent
from agents.common import make_model, rate_limiter
from prompts import prompts
from toolkits.kb_search_toolkit import read_kb_file, search_kb
from toolkits.rag_toolkit import semantic_search_documents
from toolkits.scoped_filesystem_toolkit import create_scoped_filesystem_tools

load_dotenv()

CODEBASE_PATH = os.getenv("CODEBASE_PATH", "data/sample_codebase")
AGENT_WORKSPACE = os.getenv("AGENT_WORKSPACE_PATH", "data/agent_workspace")

class ToolCallingAgent(BaseAgent):
    def __init__(self, tools: List[Tool], max_steps: int = 6, max_retries: int = 2, return_full_result: bool = True):
        super().__init__()

        kb_tools = [search_kb, read_kb_file, semantic_search_documents]
        
        # Codebase filesystem tools (read, tree, list, write, grep)
        code_tools = create_scoped_filesystem_tools(
            codebase_root=CODEBASE_PATH,
            workspace_root=AGENT_WORKSPACE,
        )

        all_tools = tools + kb_tools + code_tools


        self.agent = SmolToolCallingAgent(
            name="tool_calling_agent",
            description="Chatbot that can consult local KB (markdown) before answering.",
            tools=all_tools,
            max_steps=max_steps,
            model=make_model(role="chat"),
            instructions=prompts.TOOL_CALLING_AGENT,
            return_full_result=return_full_result
        )

        logger.info(f"Initialized {self.agent.name}.")

    def run(self, *args, **kwargs):
        rate_limiter.wait()
        return self.agent.run(*args, **kwargs)
