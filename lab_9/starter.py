"""
================================================================================
WanderBot — EXERCISE: AgentCore Code Interpreter
================================================================================
Topic    : Isolated code execution with AgentCore Code Interpreter
Exercise : Add a calculate_trip_cost tool that runs exact arithmetic inside a
           secure, isolated Python sandbox managed by AgentCore.

WHY CODE INTERPRETER?
---------------------
  - LLMs make arithmetic mistakes
  - Running LLM-written code in your app process is unsafe
  - AgentCore spins up an ephemeral sandbox per call — no host access, no
    state leaking between requests (clearContext=True)

EXERCISE INSTRUCTIONS
---------------------
  Step 1 : Import code_session from bedrock_agentcore.tools.code_interpreter_client
  Step 2 : Set the REGION constant
  Step 3 : Implement the calculate_trip_cost @tool (template provided below)
  Step 4 : Wire the tool into the Agent and invoke it
================================================================================
"""

import json
import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel

# TODO Step 1: Import code_session
# from bedrock_agentcore.tools.code_interpreter_client import code_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("WanderBot.CodeInterpreter")

app = BedrockAgentCoreApp()
model = BedrockModel(model_id="us.amazon.nova-2-lite-v1:0")

# TODO Step 2: Set the REGION constant
# REGION = "us-east-1"


# ===========================================================================
# TODO Step 3: Implement the calculate_trip_cost tool
# ===========================================================================

# @tool
# def calculate_trip_cost(code: str, description: str = "") -> str:
#     """Execute Python code in an isolated AgentCore sandbox and return the output."""
#
#     if description:
#         code = f"# {description}\n{code}"
#
#     # Print the LLM-generated code so you can see what the agent wrote
#     print(f"\nGenerated Code:\n{code}\n")
#
#     with code_session(REGION) as code_client:
#         response = code_client.invoke("executeCode", {
#             "code": code,
#             "language": "python",
#             "clearContext": True,   # fresh sandbox every call — no state leaks
#         })
#
#     for event in response["stream"]:
#         return json.dumps(event["result"])


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

    # TODO Step 4: Build the Agent with calculate_trip_cost and invoke it
    #
    # agent = Agent(
    #     model=model,
    #     system_prompt=SYSTEM_PROMPT,
    #     tools=[calculate_trip_cost],
    # )
    # response = agent(user_message)
    # return response
    pass


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run()
