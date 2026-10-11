"""
================================================================================
WanderBot — DEMO: AgentCore Native Observability
================================================================================
Topic : Observability for agents and tool calls via AgentCore's built-in
        OpenTelemetry instrumentation.

HOW IT WORKS
------------
AgentCore Runtime auto-instruments every invocation with OpenTelemetry (ADOT).
Traces flow to X-Ray and appear in the CloudWatch GenAI Observability Dashboard.

No hooks, no boto3, no custom metrics code — adding one library to requirements
is all it takes:

    aws-opentelemetry-distro

Each trace captures:
  - The full agent invocation (latency, model, token counts)
  - A child span per tool call (name, inputs, output, duration)
  - Session grouping — invocations that share a session_id appear together

HOW TO RUN
----------
  agentcore configure && agentcore deploy

  # Consecutive invokes share the same runtime session — no flag needed.
  # Use `agentcore stop-session` to start a fresh one.
  agentcore invoke '{"message": "Find flights from London to Tokyo"}'
  agentcore invoke '{"message": "Hotels in Tokyo under $200/night"}'

  agentcore stop-session
  agentcore invoke '{"message": "Flights from New York to Rome"}'

  Then open: CloudWatch -> Bedrock -> GenAI Observability
================================================================================
"""

import json
import logging
from pathlib import Path

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("WanderBot.Observability")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "datasets"

app = BedrockAgentCoreApp()
model = BedrockModel(model_id="us.amazon.nova-2-lite-v1:0")


@tool
def search_flights(origin: str, destination: str) -> str:
    """Search available flights between two cities."""
    flights = json.loads((DATA_DIR / "flights.json").read_text())
    matches = [
        f for f in flights
        if f.get("origin", "").upper() == origin.upper()
        and f.get("destination", "").upper() == destination.upper()
        and f.get("status") != "CANCELLED"
    ]
    if not matches:
        return f"No flights found from {origin} to {destination}."
    return json.dumps(matches[:5], indent=2)


@tool
def search_hotels(city: str, max_price: float = 500.0) -> str:
    """Search available hotels in a city with an optional maximum price."""
    hotels = json.loads((DATA_DIR / "hotels.json").read_text())
    matches = [
        h for h in hotels
        if h.get("location", "").lower() == city.lower()
        and h.get("available", True)
        and h.get("price_per_night_usd", 0) <= max_price
    ]
    if not matches:
        return f"No hotels found in {city} under ${max_price}/night."
    return json.dumps(matches[:5], indent=2)


SYSTEM_PROMPT = """You are WanderBot, the AI travel assistant for Horizon Travel.

Use search_flights to find available flights and search_hotels to find accommodation.
Always confirm routes and availability before making recommendations."""


@app.entrypoint
async def invoke(payload: dict, context=None) -> dict:
    """WanderBot — observability demo entry point."""
    user_message = payload.get("message", "Hello!")
    logger.info("User: %s", user_message[:80])

    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[search_flights, search_hotels],
    )
    response = agent(user_message)
    return response


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run()
