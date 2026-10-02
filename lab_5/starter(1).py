"""
================================================================================
WanderBot — EXERCISE: AgentCore Gateway
================================================================================
Topic     : Calling Lambda-backed tools via AgentCore Gateway and MCP
Exercise  : Connect WanderBot to the Gateway using MCPClient and MCP tool discovery

ARCHITECTURE
------------
  WanderBot (Strands Agent)
      ↓  tool call (MCP protocol)
  AgentCore Gateway  (No Authentication)
      ↓  direct Lambda invocation
  booking_lambda.py
"""

import logging
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel

# TODO (Step 1): Add the following imports:
#   Import streamable_http_client from mcp.client.streamable_http
#   Import MCPClient from strands.tools.mcp.mcp_client

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("WanderBot.AgentCoreGateway")

# ---------------------------------------------------------------------------
# App and model
# ---------------------------------------------------------------------------
app = BedrockAgentCoreApp()
model = BedrockModel(model_id="us.amazon.nova-2-lite-v1:0")

# ---------------------------------------------------------------------------
# Gateway endpoint — set via environment variable
# ---------------------------------------------------------------------------
GATEWAY_ENDPOINT = "https://PLACEHOLDER/mcp" # TODO: Set this before running:

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are WanderBot, the AI travel assistant for Horizon Travel.

You have access to tools via the AgentCore Gateway:
- get_booking(booking_ref)          : Retrieve a booking by reference (e.g. BK-1001)
- list_bookings_by_email(email)     : List all bookings for a customer email

Use these tools to help customers with their bookings.
Present results clearly and ask clarifying questions when needed."""


# ===========================================================================
# ENTRY POINT
# ===========================================================================

@app.entrypoint
async def invoke(payload: dict, context=None) -> dict:
    """
    WanderBot — AgentCore Gateway entry point.

    Payload keys:
        message    (str): User's prompt
    """
    user_message = payload.get("message", "Hello!")

    logger.info("User: %s", user_message[:100])

    
    # TODO Step 2: Connection to the Gateway using MCPClient:
   

    # TODO Step 3: Discover all tools registered in the Gateway:
    
        # TODO Step 4: Create the Agent with discovered tools and invoke it:
    

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run()