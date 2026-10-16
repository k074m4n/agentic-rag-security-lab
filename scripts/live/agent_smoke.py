"""Live check that a model can drive the chatbot's tools (needs an API key in .env).

    uv run python -m scripts.live.agent_smoke openrouter/openai/gpt-oss-120b [...]

Runs the real tool_calling_agent on the clean sample codebase with one question,
prints the tool calls it made, the answer, and the provider-reported cost.
"""

import os
import sys

from smolagents.memory import ActionStep

QUESTION = "Which function opens the SQLite database connection in this project, and in which file?"
EXPECTED = ("get_db", "db.py")


def run(model_id: str) -> bool:
    os.environ["LITELLM_MODEL"] = model_id
    os.environ.setdefault("GLOBAL_RPM", "30")

    from agents.tool_calling_agent import ToolCallingAgent

    chatbot = ToolCallingAgent(tools=[], max_steps=6)
    result = chatbot.run(QUESTION)

    tool_calls, cost = [], 0.0
    for step in chatbot.agent.memory.steps:
        if not isinstance(step, ActionStep):
            continue
        for call in step.tool_calls or []:
            tool_calls.append(call.name)
        raw = getattr(step.model_output_message, "raw", None)
        cost += float(getattr(getattr(raw, "usage", None), "cost", 0) or 0)

    answer = str(result.output)
    ok = all(token in answer for token in EXPECTED) and any(t != "final_answer" for t in tool_calls)
    print(f"model:   {model_id}")
    print(f"tools:   {' -> '.join(tool_calls)}")
    print(f"answer:  {answer[:300]}")
    print(f"cost:    ${cost:.5f}")
    print(f"result:  {'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    models = sys.argv[1:] or [os.getenv("LITELLM_MODEL", "")]
    results = [run(m) for m in models]
    sys.exit(0 if all(results) else 1)
