"""End-to-end agent wiring test with a scripted model (no network, no API key).

Runs the real smolagents loop: manager -> tool_calling_agent -> real filesystem tool.
Guards against framework upgrades silently breaking delegation or tool dispatch.
"""

from smolagents.models import (
    ChatMessage,
    ChatMessageToolCall,
    ChatMessageToolCallFunction,
    MessageRole,
    Model,
)

from agents import common, manager_agent, tool_calling_agent


class ScriptedModel(Model):
    """Returns pre-defined tool calls in order and records every prompt it receives."""

    def __init__(self, script):
        super().__init__(model_id="scripted")
        self.script = list(script)
        self.seen = []

    def generate(self, messages, stop_sequences=None, response_format=None, tools_to_call_from=None, **kwargs):
        self.seen.append(messages)
        name, args = self.script.pop(0)
        call = ChatMessageToolCall(
            id=f"call_{len(self.seen)}",
            type="function",
            function=ChatMessageToolCallFunction(name=name, arguments=args),
        )
        return ChatMessage(role=MessageRole.ASSISTANT, content="", tool_calls=[call])


def _flatten(messages) -> str:
    return str(messages)


def test_manager_delegates_to_chatbot_which_reads_code(monkeypatch, codebase, workspace):
    chat_model = ScriptedModel(
        [
            ("read_codebase_file", {"file_path": "app/db.py"}),
            ("final_answer", {"answer": "Tasky opens a SQLite connection per request in get_db()."}),
        ]
    )
    manager_model = ScriptedModel(
        [
            ("tool_calling_agent", {"task": "How does the project connect to its database?"}),
            ("final_answer", {"answer": "relayed"}),
        ]
    )
    models = {"chat": chat_model, "manager": manager_model}

    monkeypatch.setattr(tool_calling_agent, "make_model", lambda role: models[role])
    monkeypatch.setattr(manager_agent, "make_model", lambda role: models[role])
    monkeypatch.setattr(tool_calling_agent, "CODEBASE_PATH", str(codebase))
    monkeypatch.setattr(tool_calling_agent, "AGENT_WORKSPACE", str(workspace))

    chatbot = tool_calling_agent.ToolCallingAgent(tools=[])
    manager = manager_agent.ManagerAgent(tools=[], managed_agents=[chatbot.agent])

    result = manager.run("How does the project connect to its database?")

    assert result.output == "relayed"
    # The chatbot's second model call must contain the real file contents returned by the tool.
    assert "sqlite3.connect" in _flatten(chat_model.seen[-1])
    # The manager must have received the chatbot's report.
    assert "SQLite connection per request" in _flatten(manager_model.seen[-1])


def test_make_model_honours_dotenv_default(monkeypatch):
    monkeypatch.delenv("LITELLM_MODEL_CHAT", raising=False)
    monkeypatch.setenv("LITELLM_MODEL", "gemini/gemini-2.5-flash-lite")
    assert common.make_model("chat").model_id == "gemini/gemini-2.5-flash-lite"
