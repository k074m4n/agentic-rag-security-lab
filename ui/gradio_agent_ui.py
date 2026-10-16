import os

from smolagents import GradioUI

from agents.base_agent import BaseAgent
from ui.base_ui import BaseUI


class GradioAgentUI(BaseUI):
    def __init__(self, agent: BaseAgent):
        """
        Initializes a Gradio agent chat UI.
        """
        self.agent = agent
        self.ui = self._build_ui()

    def _build_ui(self):
        """
        Builds the Gradio agent chat UI for the agent chat.
        """
        demo = GradioUI(agent=self.agent.agent)
        return demo

    def launch(self):
        """
        Launches the Gradio agent chat interface.
        """
        # smolagents' GradioUI.launch() defaults to share=True, which opens a public
        # *.gradio.live tunnel to an agent with file-write tools. Opt-in only.
        share = os.getenv("GRADIO_SHARE", "false").lower() == "true"
        self.ui.launch(server_name="127.0.0.1", share=share)
