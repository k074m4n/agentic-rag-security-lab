from typing import List

from dotenv import load_dotenv
from loguru import logger
from smolagents import Tool
from smolagents.agents import CodeAgent as SmolCodeAgent

from agents.base_agent import BaseAgent
from agents.common import make_model, rate_limiter
from prompts import prompts

load_dotenv()


class CodeAgent(BaseAgent):
    def __init__(self, tools: List[Tool], max_steps: int = 6, max_retries: int = 2):
        super().__init__()

        self.agent = SmolCodeAgent(
            name="code_agent",
            description="Placeholder code agent. Executes model-written Python via smolagents' LocalPythonExecutor (not a sandbox); disabled unless ENABLE_CODE_AGENT=true.",
            tools=tools,
            model=make_model(role="code"),
            instructions=prompts.CODE_AGENT
        )

        logger.info(f"Initialized {self.agent.name}.")

    def run(self, *args, **kwargs):
        rate_limiter.wait()
        return self.agent.run(*args, **kwargs)
