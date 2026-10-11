"""
================================================================================
WanderBot — EXERCISE SOLUTION: AgentCore Code Interpreter
================================================================================
Reference solution for the L10 exercise. Adds calculate_trip_cost — a tool
that runs exact arithmetic inside an isolated AgentCore Python sandbox.

HOW TO RUN
----------
  agentcore configure && agentcore deploy
  agentcore invoke '{"message": "2 rooms for 5 nights at $180/night, plus 12% tax. Total?"}'
================================================================================
"""

import json
import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.tools.code_interpreter_client import code_session
from strands import Agent, tool
from strands.models import BedrockModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("WanderBot.CodeInterpreter")

app = BedrockAgentCoreApp()
model = BedrockModel(model_id="us.amazon.nova-2-lite-v1:0")

REGION = "us-east-1"


# ===========================================================================
# Code Interpreter tool
# ===========================================================================

@tool
def calculate_trip_cost(code: str, description: str = "") -> str:
    """Execute Python code in an isolated AgentCore sandbox and return the output."""

    if description:
        code = f"# {description}\n{code}"

    # Print the LLM-generated code so you can see what the agent wrote
    print(f"\nGenerated Code:\n{code}\n")

    with code_session(REGION) as code_client:
        response = code_client.invoke("executeCode", {
            "code": code,
            "language": "python",
            "clearContext": True,   # fresh sandbox every call — no state leaks
        })

    for event in response["stream"]:
        return json.dumps(event["result"])


SYSTEM_PROMPT = """You are WanderBot, the AI travel assistant for Horizon Travel.

You have access to the calculate_trip_cost tool, which runs exact arithmetic
inside a secure, isolated Python sandbox via the AgentCore Code Interpreter.

USE calculate_trip_cost WHENEVER a customer asks about:
- Hotel stay totals (nights * rate, taxes, multi-room bookings)
- Any "how much will it cost if..." question

Always write a short Python script that computes the answer and calls print()
on the final result. Never estimate or guess numbers yourself. Present the
result clearly with a brief explanation."""


@app.entrypoint
async def invoke(payload: dict, context=None) -> dict:
    """WanderBot — Code Interpreter entry point."""
    user_message = payload.get("message", "Hello!")
    logger.info("User: %s", user_message[:80])

    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[calculate_trip_cost],
    )
    response = agent(user_message)
    return response


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run()
