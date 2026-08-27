"""
================================================================================
WanderBot — EXERCISE SOLUTION: Strands SDK + AgentCore Runtime
================================================================================
Reference solution for the exercise. A Strands Agent with the built-in
calculator tool, wrapped in a BedrockAgentCoreApp, ready for AgentCore Runtime.

HOW TO RUN
----------
  agentcore configure
  agentcore dev
  agentcore invoke --dev '{"message": "A round-trip flight costs $349. Hotel is $175/night for 4 nights. Total?"}'

  agentcore deploy --auto-update-on-conflict
  agentcore invoke '{"message": "How do I contact Horizon Travel customer support?"}'
================================================================================
"""

import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel
from strands_tools import calculator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("WanderBot.AgentCoreRuntime")

# ---------------------------------------------------------------------------
# AgentCore app instance
# ---------------------------------------------------------------------------
# (Step 2): Create the BedrockAgentCoreApp instance
app = BedrockAgentCoreApp()

# ---------------------------------------------------------------------------
# Foundation model — Amazon Nova 2 Lite via a cross-region inference profile.
# Optional tuning: temperature=0.1, max_tokens=1024
# ---------------------------------------------------------------------------
MODEL_ID = "us.amazon.nova-2-lite-v1:0"

# (Step 3): Configure the BedrockModel with MODEL_ID
# Every BedrockModel parameter is keyword-only -- its signature starts with a
# bare `*` -- so BedrockModel(MODEL_ID) raises TypeError on strands-agents 1.53.
# region_name is explicit on purpose: Strands does NOT read the region from your
# AWS profile. Left unset it uses $AWS_REGION, or falls back to us-west-2.
model = BedrockModel(
    model_id=MODEL_ID,
    region_name="us-east-1",
)

# ---------------------------------------------------------------------------
# WanderBot system prompt
# ---------------------------------------------------------------------------
# (Step 4): Write a SYSTEM_PROMPT string that describes:
#   - WanderBot's role as Horizon Travel's AI assistant
#   - Horizon Travel's services (flights, hotels, insurance, loyalty programme)
#   - When to use the calculator tool
#   - Style guidelines (friendly, concise)
SYSTEM_PROMPT = """
    You are WanderBot, the AI travel assistant for Horizon Travel.
    When asked to calculate costs, tips, totals, durations, or percentages,
    use the calculator tool. Keep answers friendly, concise, travel-focused.
"""


# ---------------------------------------------------------------------------
# Agent entry point — called for every incoming request
# ---------------------------------------------------------------------------
# (Step 5): Decorate this function with @app.entrypoint
@app.entrypoint
async def invoke(payload: dict, context=None):
    """WanderBot — Agent entry point."""
    user_message = payload.get("message", "Hello!")
    logger.info("User: %s", user_message[:80])

    # (Step 5): Build the Agent and return its response
    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[calculator],
    )
    response = agent(user_message)
    return response


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run()
