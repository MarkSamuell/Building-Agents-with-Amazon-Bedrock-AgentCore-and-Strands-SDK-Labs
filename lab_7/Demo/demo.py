"""
================================================================================
WanderBot — DEMO: RAG with Amazon Bedrock Knowledge Bases
================================================================================
"""

import logging

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("WanderBot.AgentCoreRAG")

app = BedrockAgentCoreApp()
model = BedrockModel(model_id="us.amazon.nova-2-lite-v1:0")

KB_ID  = "wanderbot-kb-2024-06"  # Replace with your actual knowledge base ID
REGION = "us-east-1"

_bedrock_runtime = boto3.client("bedrock-agent-runtime", region_name=REGION)


@tool
def search_knowledge_base(query: str) -> str:
    """
    Search Horizon Travel's knowledge base for travel policies,
    destination guides, baggage rules, and loyalty programme details.
    Use this when a customer asks about policies, destinations, or travel tips.

    Args:
        query: The question or topic to search for
    Returns:
        Relevant information retrieved from the knowledge base
    """
    resp = _bedrock_runtime.retrieve(
        knowledgeBaseId=KB_ID,
        retrievalQuery={"text": query},
    )
    results = resp.get("retrievalResults", [])
    if not results:
        return f"No information found for: {query}"

    chunks = [r["content"]["text"] for r in results]
    return "\n---\n".join(chunks)


SYSTEM_PROMPT = """You are WanderBot, the AI travel assistant for Horizon Travel.

You have access to a knowledge base containing:
- Horizon Travel Policies: fare classes, cancellation rules, baggage allowances,
  check-in times, loyalty programme, special assistance, passenger rights
- Destination Guides: Barcelona, Tokyo, Rome, Dubai, Sydney, Reykjavik, New York, Cape Town

ALWAYS use the search_knowledge_base tool before answering questions about:
- Horizon Travel policies, rules, fees, or procedures
- Destination information, attractions, or travel tips

Base policy answers on retrieved content — quote exact figures and cite the source section.
If the knowledge base doesn't cover the question, say so honestly."""


@app.entrypoint
async def invoke(payload: dict, context=None) -> dict:
    """WanderBot — RAG with Bedrock Knowledge Bases."""
    user_message = payload.get("message", "Hello!")

    logger.info("KB: %s | User: %s", KB_ID, user_message[:80])

    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[search_knowledge_base],
    )

    response = agent(user_message)
    return response


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run()
