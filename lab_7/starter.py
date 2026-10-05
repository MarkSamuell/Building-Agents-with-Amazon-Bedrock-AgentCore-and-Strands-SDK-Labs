"""
================================================================================
WanderBot — EXERCISE: RAG with Amazon Bedrock Knowledge Bases
================================================================================
Topic    : Retrieval-Augmented Generation using Bedrock Knowledge Bases
Exercise : Create a Knowledge Base from Horizon Travel's documents and connect
           WanderBot to it with a custom @tool

EXERCISE INSTRUCTIONS
---------------------
  Step 1 (infra): Upload datasets/travel_policies.txt and datasets/destination_guides.txt
                  to an S3 bucket/prefix you control.

  Step 2 (infra): In the AWS Console, create a Bedrock Knowledge Base pointed at
                  that S3 prefix. Use Titan Text Embeddings v2 and S3 Vectors.
                  Sync the data source, wait for Ready, and copy the KB ID.

  Step 3 (code) : Set the Knowledge Base ID from Step 2

  Step 4 (code) : In invoke(), create the Agent with search_knowledge_base in
                  its tools list and invoke it.

See the README for the full console walkthrough.
================================================================================
"""

import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel
import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("WanderBot.AgentCoreRAG")

app = BedrockAgentCoreApp()
model = BedrockModel(model_id="us.amazon.nova-2-lite-v1:0")

# TODO Step 3: Paste the KB ID from Step 2
KB_ID  = "PASTE_YOUR_KB_ID_HERE"
REGION = "us-east-1"
_bedrock_runtime = boto3.client("bedrock-agent-runtime", region_name=REGION)


@tool
def search_knowledge_base(query: str) -> str:
    """
    Search Horizon Travel's knowledge base for travel policies,
    destination guides, baggage rules, and loyalty programme details.

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

    logger.info("User: %s", user_message[:80])

    # TODO Step 4: Create the agent with search_knowledge_base as a tool and invoke
 


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run()
