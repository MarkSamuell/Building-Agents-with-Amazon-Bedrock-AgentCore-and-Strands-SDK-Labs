"""
================================================================================
WanderBot — DEMO: Short-Term Memory (AgentCore Memory)
================================================================================
"""

import json
import logging
from pathlib import Path

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.memory import MemoryClient
from strands.hooks import (
    AgentInitializedEvent,
    HookProvider,
    HookRegistry,
    MessageAddedEvent,
)



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("WanderBot.ShortTermMemory")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "datasets"

app = BedrockAgentCoreApp()

MODEL_ID = "us.amazon.nova-2-lite-v1:0"
model = BedrockModel(model_id=MODEL_ID)

REGION = "us-east-1"
MEMORY_ID = "REPLACE_WITH_YOUR_MEMORY_ID"

SYSTEM_PROMPT = """You are WanderBot, the AI travel assistant for Horizon Travel.

You are helping a customer plan their trip across a multi-turn conversation.

CONVERSATION GUIDELINES
- Refer back to earlier parts of the conversation when relevant
- If the customer mentions a city, remember it for subsequent questions
- Be proactive: suggest related information
- Keep track of the customer's stated preferences
- When the customer asks follow-up questions, answer in context

TOOL USE
- Use search_flights when asked about flight options or availability
- Always use tools rather than guessing specific data

IATA CODE QUICK REFERENCE
LHR = London Heathrow | CDG = Paris Charles de Gaulle | JFK = New York JFK
MIA = Miami | LAX = Los Angeles | BCN = Barcelona | FCO = Rome Fiumicino"""


# ===========================================================================
# TOOL
# ===========================================================================

@tool
def search_flights(origin: str, destination: str, date: str) -> str:
    """
    Search for Horizon Travel flights by route and date.

    Args:
        origin      : IATA departure airport code (e.g. 'LHR', 'JFK')
        destination : IATA arrival airport code (e.g. 'CDG', 'FCO')
        date        : Date in YYYY-MM-DD format
    Returns:
        Formatted list of matching flights with prices and availability.
    """
    logger.info("search_flights called with: origin='%s', destination='%s', date='%s'", origin, destination, date)
    logger.info("DATA_DIR resolved to: %s", DATA_DIR)
    logger.info("flights.json path: %s", DATA_DIR / "flights.json")
    logger.info("flights.json exists: %s", (DATA_DIR / "flights.json").exists())

    try:
        raw = (DATA_DIR / "flights.json").read_text()
        logger.info("flights.json loaded, length: %d chars", len(raw))
        flights = json.loads(raw)
        logger.info("Parsed %d flight records", len(flights))
    except Exception as e:
        logger.error("Failed to load flights: %s", e)
        return "Flight data unavailable."

    # Log first few records to verify data
    for fl in flights[:3]:
        logger.info("Sample record: origin='%s', destination='%s', date='%s'", fl.get("origin"), fl.get("destination"), fl.get("date"))

    # Log what we're comparing
    logger.info("Filtering for: origin='%s' destination='%s' date='%s'", origin.upper(), destination.upper(), date)

    matches = [
        fl for fl in flights
        if fl["origin"].upper() == origin.upper()
        and fl["destination"].upper() == destination.upper()
        and fl["date"] == date
    ]

    logger.info("Found %d matching flights", len(matches))

    if not matches:
        return f"No flights found from {origin} to {destination} on {date}."

    lines = [f"Flights {origin.upper()} → {destination.upper()} on {date}:"]
    for fl in matches:
        status = {"SCHEDULED": "✅", "DELAYED": "⚠️", "CANCELLED": "❌"}.get(fl["status"], "")
        lines.append(
            f"  {status} {fl['flight_number']} | {fl['departure_time']}→{fl['arrival_time']} "
            f"| {fl['cabin_class']} | ${fl['price_usd']} | {fl['available_seats']} seats"
        )
    return "\n".join(lines)


# ===========================================================================
# SHORT-TERM MEMORY HOOK PROVIDER
# ===========================================================================

class ShortTermMemoryHookProvider(HookProvider):
    """
    Gives the agent short-term memory via AgentCore Memory.

    Two hooks:
      1. AgentInitializedEvent — retrieves recent turns and injects them
         into the system prompt before the first model call.
      2. MessageAddedEvent — persists each new message to AgentCore Memory
         so it's available in future invocations.
    """

    def __init__(self, memory_client: MemoryClient, memory_id: str, last_k_turns: int = 5):
        self.memory_client = memory_client
        self.memory_id = memory_id
        self.last_k_turns = last_k_turns

    def register_hooks(self, registry: HookRegistry) -> None:
        """Bind callbacks to the events we care about."""
        registry.add_callback(AgentInitializedEvent, self.on_agent_initialized)
        registry.add_callback(MessageAddedEvent, self.on_message_added)

    def on_agent_initialized(self, event: AgentInitializedEvent) -> None:
        """Load prior conversation turns and inject into the system prompt."""
        actor_id = event.agent.state.get("actor_id")
        session_id = event.agent.state.get("session_id")

        if not actor_id or not session_id:
            return

        recent_turns = self.memory_client.get_last_k_turns(
            memory_id=self.memory_id,
            actor_id=actor_id,
            session_id=session_id,
            k=self.last_k_turns,
        )

        if not recent_turns:
            logger.info("No prior turns found for session %s", session_id)
            return

        lines = []
        for turn in recent_turns:
            for message in turn:
                role = message.get("role", "unknown").capitalize()
                text = message.get("content", {}).get("text", "")
                if text:
                    lines.append(f"{role}: {text}")

        if lines:
            context = "\n".join(lines)
            event.agent.system_prompt += f"\n\nRecent conversation:\n{context}"
            logger.info(
                "Session %s: injected %d prior turns into system prompt",
                session_id, len(recent_turns),
            )

    def on_message_added(self, event: MessageAddedEvent) -> None:
        """Persist new messages to AgentCore Memory."""
        actor_id = event.agent.state.get("actor_id")
        session_id = event.agent.state.get("session_id")

        if not actor_id or not session_id:
            return

        message = event.message
        role = message.get("role", "")

        content = message.get("content", [])
        if not isinstance(content, list) or not content:
            return

        text = content[0].get("text") if isinstance(content[0], dict) else None
        if not text:
            return

        self.memory_client.create_event(
            memory_id=self.memory_id,
            actor_id=actor_id,
            session_id=session_id,
            messages=[(text, role.upper())],
        )
        logger.info("Session %s: persisted %s message", session_id, role)


# ===========================================================================
# ENTRY POINT
# ===========================================================================

@app.entrypoint
async def invoke(payload: dict, context=None) -> dict:
    """WanderBot — Short-Term Memory entry point."""
    user_message = payload.get("message", "Hello!")
    session_id = context.session_id
    actor_id = payload.get("actor_id", "wanderbot-user")

    logger.info("Session %s | Actor %s | User: %s", session_id, actor_id, user_message[:80])

    memory_client = MemoryClient(region_name=REGION)

    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[search_flights],
        hooks=[ShortTermMemoryHookProvider(memory_client, MEMORY_ID)],
        state={"session_id": session_id, "actor_id": actor_id},
    )

    response = agent(user_message)

    return response


if __name__ == "__main__":
    app.run()