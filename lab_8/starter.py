"""
================================================================================
WanderBot — EXERCISE: Long-Term Memory with AgentCore MemoryClient
================================================================================
Topic    : Persistent memory across sessions using AgentCore Memory
Exercise : Extend the short term memory resource with long-term strategies and wire
           WanderBot to it through a hook.

EXERCISE INSTRUCTIONS
---------------------
  Step 1 (infra): In the AWS Console, open the memory resource from earlier or create a new one
                  and add two long-term strategies:
                    - SEMANTIC         → namespace: wanderbot/{actorId}/facts
                    - USER_PREFERENCE  → namespace: wanderbot/{actorId}/preferences
                  Wait until both are Active. Copy the Memory ID.

  Step 2 (code) : Import MemoryClient + hook classes, and set MEMORY_ID

  Step 3 (code) : Complete register_hooks() on WanderBotMemoryHook. The other
                  two methods are already implemented for you.

  Step 4 (code) : In invoke(), create the hook, build the Agent with
                  hooks=[memory_hook], and invoke it.

See the README for the full console walkthrough.
================================================================================
"""

import logging
from typing import Dict

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel

# TODO Step 2: Import MemoryClient and the hook classes

# TODO Step 2: Import AfterInvocationEvent, HookProvider, HookRegistry, 
#               MessageAddedEvent, from strands.hooks


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("WanderBot.LongTermMemory")

app = BedrockAgentCoreApp()
model = BedrockModel(model_id="us.amazon.nova-2-lite-v1:0")

# TODO Step 2: Paste the Memory ID from Step 1
MEMORY_ID = "PASTE_YOUR_MEMORY_ID_HERE"
REGION    = "us-east-1"
memory_client = MemoryClient(region_name=REGION)


# ===========================================================================
# NAMESPACE HELPER (provided)
# ===========================================================================

def get_namespaces(mem_client, memory_id: str) -> Dict[str, str]:
    """
    Returns e.g.:
      { "SEMANTIC":        "wanderbot/{actorId}/facts",
        "USER_PREFERENCE": "wanderbot/{actorId}/preferences" }
    """
    strategies = mem_client.get_memory_strategies(memory_id)
    return {s["type"]: s["namespaces"][0] for s in strategies}


# ===========================================================================
# MEMORY HOOK
# ===========================================================================
# The retrieve and save methods are fully implemented below — you only need
# to register them in Step 3.
# ===========================================================================

class WanderBotMemoryHook(HookProvider):
    """
    Long-term memory hook for WanderBot.

    - MessageAddedEvent    → retrieve memories per namespace, prepend as context
    - AfterInvocationEvent → save (USER, ASSISTANT) pair via create_event()
    """

    def __init__(self, memory_client, memory_id: str):
        self.memory_client = memory_client
        self.memory_id = memory_id
        self.namespaces = get_namespaces(self.memory_client, self.memory_id)
        logger.info("Namespaces loaded: %s", self.namespaces)

    # TODO Step 3: Register both callbacks on the registry
    #               _retrieve_travel_context for MessageAddedEvent
    #               _save_interaction for AfterInvocationEvent
    def register_hooks(self, registry: HookRegistry) -> None:
        pass

    def _retrieve_travel_context(self, event) -> None:
        """Search each memory namespace and prepend results to the user's message."""
        actor_id = event.agent.state.get("actor_id")
        if not actor_id:
            return

        messages = event.agent.messages
        if (
            not messages
            or messages[-1]["role"] != "user"
            or "toolResult" in messages[-1]["content"][0]
        ):
            return

        user_query = messages[-1]["content"][0]["text"]

        try:
            all_context = []
            for strategy_type, namespace in self.namespaces.items():
                resolved_namespace = namespace.format(actorId=actor_id)
                memories = self.memory_client.retrieve_memories(
                    memory_id=self.memory_id,
                    namespace=resolved_namespace,
                    query=user_query,
                    top_k=5,
                )
                for memory in memories:
                    if isinstance(memory, dict):
                        text = memory.get("content", {}).get("text", "").strip()
                        if text:
                            all_context.append(f"[{strategy_type}] {text}")

            if all_context:
                context_block = "\n".join(all_context)
                original_text = messages[-1]["content"][0]["text"]
                messages[-1]["content"][0]["text"] = (
                    f"Traveller Context:\n{context_block}\n\n{original_text}"
                )
                logger.info("Retrieved %d memory items for actor %s", len(all_context), actor_id)

        except Exception as exc:
            logger.error("Failed to retrieve travel context: %s", exc)

    def _save_interaction(self, event) -> None:
        """Persist the most recent (USER, ASSISTANT) pair."""
        actor_id   = event.agent.state.get("actor_id")
        session_id = event.agent.state.get("session_id")
        if not actor_id or not session_id:
            return

        try:
            messages = event.agent.messages
            user_text = agent_text = None

            for msg in reversed(messages):
                if msg["role"] == "assistant" and not agent_text:
                    content = msg["content"]
                    if isinstance(content, list):
                        agent_text = content[0].get("text", "")
                    else:
                        agent_text = str(content)
                elif (
                    msg["role"] == "user"
                    and not user_text
                    and "toolResult" not in msg["content"][0]
                ):
                    user_text = msg["content"][0]["text"]
                    break

            if user_text and agent_text:
                self.memory_client.create_event(
                    memory_id=self.memory_id,
                    actor_id=actor_id,
                    session_id=session_id,
                    messages=[
                        (user_text, "USER"),
                        (agent_text, "ASSISTANT"),
                    ],
                )
                logger.info("Saved interaction to memory for actor %s", actor_id)

        except Exception as exc:
            logger.error("Failed to save interaction: %s", exc)


SYSTEM_PROMPT = """You are WanderBot, the personal AI travel concierge for Horizon Travel.

You have PERSISTENT MEMORY: you remember each traveller's preferences, past trips,
and interests across multiple conversations.

MEMORY-AWARE BEHAVIOUR
- When a "Traveller Context" block appears at the start of the user's message,
  it contains facts and preferences retrieved from past conversations.
- Use this context to personalise your recommendations naturally.
- Reference past context: "Based on your interest in Japanese cuisine..."
- Never ask the traveller to repeat information they've already shared.

Be warm, attentive, and genuinely helpful — like a trusted travel agent who
has known the customer for years."""


@app.entrypoint
async def invoke(payload: dict, context=None) -> dict:
    """WanderBot — Long-Term Memory entry point."""
    user_message = payload.get("message", "Hello!")
    session_id   = context.session_id
    actor_id     = payload.get("actor_id", "wanderbot-user")

    logger.info("Session %s | Actor %s | User: %s", session_id, actor_id, user_message[:80])

    # TODO Step 4: Build the hook with memory_client and memory_id 
    #               and wire it into the agent - include agent state with session_id and actor_id



# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run()
