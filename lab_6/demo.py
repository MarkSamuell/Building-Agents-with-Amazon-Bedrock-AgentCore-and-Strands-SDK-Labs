"""
================================================================================
WanderBot — DEMO: AgentCore Browser
================================================================================
"""

import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel
from strands_tools.browser import AgentCoreBrowser
import nest_asyncio
import playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("WanderBot.AgentCoreBrowser")

app = BedrockAgentCoreApp()
model = BedrockModel(model_id="us.amazon.nova-2-lite-v1:0")

SYSTEM_PROMPT = """You are WanderBot, the AI travel assistant for Horizon Travel.

You have access to a live web browser. Use it to look up destination information
on Wikivoyage (en.wikivoyage.org) — a free, open travel guide.

When a customer asks about a destination:
1. Navigate to en.wikivoyage.org/wiki/<DestinationName>
2. Read the page — focus on highlights, neighbourhoods, and practical tips
3. Summarise what you find clearly and concisely

Always tell the customer that the information came from Wikivoyage."""


@app.entrypoint
async def invoke(payload: dict, context=None) -> dict:
    """WanderBot — AgentCore Browser entry point."""
    user_message = payload.get("message", "Hello!")

    logger.info("User: %s", user_message[:80])

    # session_timeout defaults to 3600s; 600s (10 min) is plenty for this demo
    browser = AgentCoreBrowser(session_timeout=600)
    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[browser.browser],
    )
    response = agent(user_message)
    return response


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run()
