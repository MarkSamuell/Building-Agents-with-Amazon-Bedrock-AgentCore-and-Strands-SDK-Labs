# Exercise: Long-Term Memory with AgentCore Memory

## Overview
Extend the memory resource from L04 with long-term strategies and give WanderBot cross-session memory. You'll add two strategies on the console, then wire a `HookProvider` in the agent so every turn retrieves relevant traveller context and every response saves the new exchange.

**Estimated time:** 15 minutes

## Learning Objectives
1. Add `SEMANTIC` and `USER_PREFERENCE` strategies to an existing AgentCore Memory resource
2. Use `get_memory_strategies()` to fetch namespace templates at runtime
3. Register `MessageAddedEvent` and `AfterInvocationEvent` callbacks on a custom `HookProvider`
4. Pass `actor_id` and `session_id` through `agent.state` so hook callbacks can reach them
5. Distinguish short-term (L04) vs long-term (L09) memory

## Architecture
```
L04 Memory resource  (+ SEMANTIC + USER_PREFERENCE strategies)
        ↑ create_event()                       ↓ retrieve_memories()
                                               (prepended as Traveller Context)
          WanderBot Agent + WanderBotMemoryHook
```

## Prerequisites
- Completed AgentCoreMemory lesson (memory resource already exists)
- AWS account with AgentCore Memory access

---

## Exercise Steps

### Step 1 (infra) — Add the two long-term strategies
AWS Console → **Amazon Bedrock → AgentCore → Memory** → open the memory resource from Short Term Memory lesson → **Edit**.

Add these two strategies:

| Strategy type | Namespace template |
|--------------|---------------------|
| `SEMANTIC` | `wanderbot/{actorId}/facts` |
| `USER_PREFERENCE` | `wanderbot/{actorId}/preferences` |

`{actorId}` is resolved at runtime using the `actor_id` passed in the payload.

Wait until both strategies show **Active**, then copy the **Memory ID**.

### Step 2 (code) — Imports and `MemoryClient`
In `starter.py`:

```python
from bedrock_agentcore.memory import MemoryClient
from strands.hooks import (
    AfterInvocationEvent,
    HookProvider,
    HookRegistry,
    MessageAddedEvent,
)

MEMORY_ID = "PASTE_YOUR_MEMORY_ID_HERE"
REGION    = "us-east-1"
memory_client = MemoryClient(region_name=REGION)
```

### Step 3 (code) — Register the hook callbacks
The `_retrieve_travel_context` and `_save_interaction` methods are already implemented. Your job is only to register them:

```python
def register_hooks(self, registry: HookRegistry) -> None:
    registry.add_callback(MessageAddedEvent, self._retrieve_travel_context)
    registry.add_callback(AfterInvocationEvent, self._save_interaction)
```

### Step 4 (code) — Wire the agent
In `invoke()`:

```python
memory_hook = WanderBotMemoryHook(memory_client=memory_client, memory_id=MEMORY_ID)

agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[],
    state={"session_id": session_id, "actor_id": actor_id},
    hooks=[memory_hook],
)
response = agent(user_message)
return response
```

`session_id` comes from `context.session_id` (AgentCore-assigned) and `actor_id` from the payload — same pattern as L04. Both get stored in `agent.state` so the hook callbacks can read them via `event.agent.state.get(...)`.

---

## Deploy and Test

```bash
pip install -r requirements.txt
```

```bash
ER=$(python -c 'import yaml,sys; print(yaml.safe_load(open(".bedrock_agentcore.yaml"))["agents"]["WanderBot"]["aws"]["execution_role"])')
ECR_URI=$(python -c 'import yaml,sys; print(yaml.safe_load(open(".bedrock_agentcore.yaml"))["agents"]["WanderBot"]["aws"]["ecr_repository"])')
agentcore configure -e starter.py -n WanderBot -dt container -rf requirements.txt -er $ER -ecr $ECR_URI
agentcore deploy
```

### Session 1 — share preferences
```bash
agentcore invoke '{"message": "Hi, I am Alice. I love luxury travel and Japanese cuisine.", "actor_id": "alice-001"}'
agentcore invoke '{"message": "My budget is around $5000 per trip.", "actor_id": "alice-001"}'
```

Wait a few seconds — memory extraction is asynchronous.

### Session 2 — agent should remember
```bash
agentcore invoke '{"message": "Can you recommend a trip for me?", "actor_id": "alice-001"}'
agentcore invoke '{"message": "What do you remember about me?", "actor_id": "alice-001"}'
```

Expected: Alice's second session references luxury travel, Japanese cuisine, and the $5000 budget — retrieved from her namespaces on the memory resource.

### Cross-user isolation
```bash
agentcore invoke '{"message": "What do you know about me?", "actor_id": "bob-002"}'
```

Bob's response has no prior context — namespaces keep users separate.

---

## Bonus: Inspect Stored Memories from the CLI

Once you've had a few interactions, you can inspect what AgentCore actually stored using the `agentcore memory` commands. For example:

```bash
agentcore memory browse
```

This lets you walk through the memories on the resource and see the extracted facts and preferences, per namespace, for each actor — useful for debugging why an agent did or didn't recall something.

## Short-Term vs Long-Term 

| | Short-Term | Long-Term |
|-|-----|-----|
| **Storage** | Raw session events on the memory resource | Extracted facts + preferences in strategy namespaces |
| **Survives restart** | Yes, but scoped to the same `session_id` | Yes, across all sessions for the actor |
| **Retrieval** | List recent turns by session | Semantic search per namespace |
| **Context injection** | Prepended to the system prompt | Prepended to the user's message as "Traveller Context" |

## Common Errors
| Error | Fix |
|-------|-----|
| `get_memory_strategies()` returns empty | Strategies not yet Active, or wrong Memory ID |
| No context in session 2 | Extraction is async — wait 10-30 seconds after the last session-1 invoke |
| `toolResult` check fails | Keep the guard: `"toolResult" not in messages[-1]["content"][0]` |
| `create_event()` error | Use tuple format: `[(user_text, "USER"), (agent_text, "ASSISTANT")]` |

## Files
| File | Purpose |
|------|---------|
| `starter.py` | Starter agent — 4 TODOs (1 infra + 3 code) |
| `solution.py` | Reference solution |
| `requirements.txt` | Runtime dependencies |
