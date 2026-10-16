import os
from typing import List

from dotenv import load_dotenv
from loguru import logger
from smolagents import Tool
from smolagents.agents import ToolCallingAgent as SmolToolCallingAgent

from agents.base_agent import BaseAgent, BaseManagerAgent
from agents.common import make_model, rate_limiter
from prompts import prompts
from toolkits.kb_orchestration_toolkit import (
    build_kb_short_from_index,
    merge_kb_outputs_to_index,
    plan_kb_tasks_from_codebase,
)
from toolkits.rag_toolkit import build_rag_index_for_kb
from toolkits.spawn_toolkit import spawn_sub_agents

load_dotenv()

RETURN_FULL_RESULT = True

class ManagerAgent(BaseManagerAgent):
    def __init__(self, tools: List[Tool], managed_agents: List[BaseAgent], max_steps: int = 6, max_retries: int = 2):
        super().__init__(managed_agents=managed_agents)

        tools = tools + [plan_kb_tasks_from_codebase, spawn_sub_agents, merge_kb_outputs_to_index, build_kb_short_from_index, build_rag_index_for_kb]

        self.agent = SmolToolCallingAgent(
            name="manager_agent",
            description="A manager agent that oversees other agents and helps users.",
            tools=tools,
            max_steps=int(os.getenv("MANAGER_MAX_STEPS", "6")),
            model=make_model(role="manager"),
            instructions=prompts.MANAGER_AGENT,
            managed_agents=managed_agents,
            return_full_result=RETURN_FULL_RESULT,
        )

        logger.info(f"Initialized {self.agent.name}.")

    def run(self, *args, **kwargs):
        rate_limiter.wait()
        return self.agent.run(*args, **kwargs)
