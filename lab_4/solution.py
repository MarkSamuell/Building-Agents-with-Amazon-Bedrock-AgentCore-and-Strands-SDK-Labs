"""
================================================================================
WanderBot — EXERCISE: Short-Term Memory
================================================================================
"""

import json
import logging
from pathlib import Path

from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.hooks import (
    AgentInitializedEvent,
    HookProvider,
    HookRegistry,
    MessageAddedEvent,
)
from strands.models import BedrockModel

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
MEMORY_ID = "WanderBotNotebook-rlbXwr6VkG"  # TODO: Set this to your Memory ID from agentcore memory create

SYSTEM_PROMPT = """You are WanderBot, the AI travel assistant for Horizon Travel.

You are engaged in a multi-turn conversation and have full access to the conversation history.

CONVERSATION STYLE
- Always maintain context from previous turns — never ask for information already provided
- If the customer mentioned a city, date, or budget earlier, remember and use it
- Be proactive: suggest related information
- When the customer asks follow-up questions, answer in context

TOOL USE
- Use search_hotels for accommodation options
- Always use tools rather than guessing specific data"""


# ===========================================================================
# TOOL
# ===========================================================================

@tool
def search_hotels(city: str, max_price_usd: float = 9999.0) -> str:
    """
    Find available hotels in a destination city with optional budget filter.

    Args:
        city          : City name (e.g. 'Rome', 'Tokyo', 'Barcelona', 'Dubai')
        max_price_usd : Maximum price per night in USD (default: no limit)
    Returns:
        Formatted hotel list sorted by price with amenities and cancellation terms.
    """
    logger.info("search_hotels: city=%s, max=$%.0f", city, max_price_usd)

    try:
        hotels = json.loads((DATA_DIR / "hotels.json").read_text())
    except Exception:
        return "Hotel data is temporarily unavailable."

    matches = [
        h for h in hotels
        if h["city"].lower() == city.lower().strip()
        and h.get("available", False)
        and h["price_per_night_usd"] <= max_price_usd
    ]

    if not matches:
        budget = f" under ${max_price_usd:.0f}/night" if max_price_usd < 9999 else ""
        return (
            f"No available hotels found in {city}{budget}. "
            f"Try increasing your budget or searching a nearby city."
        )

    star_icons = {5: "⭐⭐⭐⭐⭐", 4: "⭐⭐⭐⭐", 3: "⭐⭐⭐", 2: "⭐⭐", 1: "⭐"}
    budget_note = f" (max ${max_price_usd:.0f}/night)" if max_price_usd < 9999 else ""
    rows = [f"🏨  Hotels in {city.title()}{budget_note}\n{'─' * 50}"]

    for h in sorted(matches, key=lambda x: x["price_per_night_usd"]):
        stars = star_icons.get(h["star_rating"], "")
        top_amenities = ", ".join(h["amenities"][:3])
        rows.append(
            f"\n{stars} {h['name']}\n"
            f"  💰 ${h['price_per_night_usd']:.0f}/night  |  "
            f"Rooms: {', '.join(h['room_types'][:2])}\n"
            f"  🔧 {top_amenities}\n"
            f"  📋 {h['cancellation_policy']}"
        )

    return "\n".join(rows)


# ===========================================================================
# SHORT-TERM MEMORY HOOK PROVIDER
# ===========================================================================

class ShortTermMemoryHookProvider(HookProvider):
    """HookProvider that gives WanderBot short-term memory via AgentCore Memory."""

    def __init__(self, memory_client: MemoryClient, memory_id: str, last_k_turns: int = 5):
        self.memory_client = memory_client
        self.memory_id = memory_id
        self.last_k_turns = last_k_turns

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(AgentInitializedEvent, self.on_agent_initialized)
        registry.add_callback(MessageAddedEvent, self.on_message_added)

    def on_agent_initialized(self, event: AgentInitializedEvent) -> None:
        """Load prior turns from AgentCore Memory and inject into system prompt."""
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


# ===========================================================================
# ENTRY POINT
# ===========================================================================

@app.entrypoint
async def invoke(payload: dict, context=None) -> dict:
    user_message = payload.get("message", "Hello!")
    session_id = context.session_id
    actor_id = payload.get("actor_id", "wanderbot-user")

    logger.info("Session %s | Actor %s | User: %s", session_id, actor_id, user_message[:80])

    memory_client = MemoryClient(region_name=REGION)

    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[search_hotels],
        hooks=[ShortTermMemoryHookProvider(memory_client, MEMORY_ID)],
        state={"session_id": session_id, "actor_id": actor_id},
    )

    response = agent(user_message)
    return response


if __name__ == "__main__":
    app.run()