"""
================================================================================
WanderBot — EXERCISE SOLUTION (BONUS): Strands `retrieve` community tool
================================================================================
Topic    : Same RAG behaviour, zero custom tool code
Change   : Drop the custom @tool + boto3 client and use the built-in `retrieve`
           tool from strands_tools. It reads the knowledge base ID from the
           KNOWLEDGE_BASE_ID environment variable at runtime.

DEPLOY WITH THE KB ID AS AN ENVIRONMENT VARIABLE
------------------------------------------------
  agentcore configure -e solution_bonus.py -n WanderBot ...
  agentcore deploy --env KNOWLEDGE_BASE_ID=BSTUUEN8YZ

  agentcore invoke '{"message": "What is the refund for Economy Flex?"}'
================================================================================
"""

import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel
from strands_tools import retrieve

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("WanderBot.AgentCoreRAG")

app = BedrockAgentCoreApp()
model = BedrockModel(model_id="us.amazon.nova-2-lite-v1:0")


SYSTEM_PROMPT = """You are WanderBot, the AI travel assistant for Horizon Travel.

You have access to a knowledge base containing:
- Horizon Travel Policies: fare classes, cancellation rules, baggage allowances,
  check-in times, loyalty programme, special assistance, passenger rights
- Destination Guides: Barcelona, Tokyo, Rome, Dubai, Sydney, Reykjavik, New York, Cape Town

ALWAYS use the retrieve tool before answering questions about:
- Horizon Travel policies, rules, fees, or procedures
- Destination information, attractions, or travel tips

Base policy answers on retrieved content — quote exact figures and cite the source section.
If the knowledge base doesn't cover the question, say so honestly."""


@app.entrypoint
async def invoke(payload: dict, context=None) -> dict:
    """WanderBot — RAG via the Strands `retrieve` community tool."""
    user_message = payload.get("message", "Hello!")

    logger.info("User: %s", user_message[:80])

    # `retrieve` reads KNOWLEDGE_BASE_ID from the environment at runtime —
    # no KB ID hardcoded, no boto3 client, no custom @tool function.
    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[retrieve],
    )
    response = agent(user_message)
    return response


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run()
