# Exercise: Short-Term Memory

## Overview
Build a custom `ShortTermMemoryHookProvider` that hooks into the Strands agent lifecycle to give WanderBot persistent short-term memory via AgentCore Memory. The agent will remember what the customer said in earlier invocations, enabling natural multi-turn travel planning conversations.

**Estimated time:** 20 minutes

## Learning Objectives
1. Implement the `HookProvider` interface by extending `HookProvider`
2. Use `register_hooks()` to bind callbacks to specific lifecycle events
3. Understand how `AgentInitializedEvent` and `MessageAddedEvent` power the memory pattern
4. Pass `hooks=[]` and `state={}` to the Strands `Agent` constructor

## Prerequisites
- Dataset in `datasets/` folder: `hotels.json`
- A memory resource created via the CLI or AgentCore console

## Setup
```bash
pip install -r requirements.txt
```



## Dataset
| File | Contents |
|------|----------|
| `datasets/hotels.json` | 10 hotels across 4 cities (Barcelona, Tokyo, Rome, Dubai) with ratings, prices, and amenities |

## Key Concept: The HookProvider Pattern

A `HookProvider` lets you hook into specific moments in the agent's lifecycle. You subclass it, implement `register_hooks()`, and bind callbacks to events:

| Event | When it fires | What we do |
|-------|--------------|------------|
| `AgentInitializedEvent` | Once, when the agent is set up | Retrieve last K turns from AgentCore Memory and inject into `system_prompt` |
| `MessageAddedEvent` | Every time a message is added | Persist the message to AgentCore Memory via `create_event()` |

Session identity is passed via `agent.state` and read inside the hooks as `event.agent.state.get("session_id")`.

## Exercise Steps

### Step 1:  Create Memory Resource
Before starting the exercise, create a memory resource using the AgentCore CLI:

```bash
agentcore memory create WanderBot
```

Copy the Memory ID from the output and set it as the `MEMORY_ID` value in `starter.py`.

You can also create the memory resource through the AgentCore console in the browser — go to the Memory section, click Create, set the name and expiry.

### Step 2: Import hook classes
Import `HookProvider`, `HookRegistry`, `AgentInitializedEvent`, and `MessageAddedEvent` from `strands.hooks`.

### Step 3: Implement `__init__`
Store `memory_client`, `memory_id`, and `last_k_turns` as instance attributes.

### Step 4: Implement `register_hooks()`
Register two callbacks:
- `AgentInitializedEvent` → `self.on_agent_initialized`
- `MessageAddedEvent` → `self.on_message_added`

The `on_agent_initialized` and `on_message_added` methods are already provided for you. They will work once Steps 1–3 are complete.

### Step 5: Wire up the entry point
Create the Agent with:
- `hooks=[ShortTermMemoryHookProvider(memory_client, MEMORY_ID)]`
- `state={"session_id": session_id, "actor_id": actor_id}`

## How to Test

```bash
ER=$(python -c 'import yaml,sys; print(yaml.safe_load(open(".bedrock_agentcore.yaml"))["agents"]["WanderBot"]["aws"]["execution_role"])')

ECR_URI=$(python -c 'import yaml,sys; print(yaml.safe_load(open(".bedrock_agentcore.yaml"))["agents"]["WanderBot"]["aws"]["ecr_repository"])')

agentcore configure -e starter.py -n WanderBot -dt container -rf requirements.txt -er $ER -ecr $ECR_URI

agentcore deploy
```

### Multi-turn test:
```bash
# Turn 1: Start planning
agentcore invoke '{"message": "I want to plan a trip to Barcelona on a budget", "actor_id": "alice"}'

# Turn 2: Agent should remember Barcelona and the budget preference
agentcore invoke '{"message": "What hotels are available under $150 per night?", "actor_id": "alice"}'

# Turn 3: Agent should remember the hotel results
agentcore invoke '{"message": "Which one has the best cancellation policy?", "actor_id": "alice"}'
```

## Expected Behaviour
- **Turn 1**: Agent acknowledges Barcelona and budget preference — no tool call needed
- **Turn 2**: Agent uses `search_hotels` with city=Barcelona and max_price_usd=150, returns Catalonia Plaza ($145) and Hostal Grau ($85)
- **Turn 3**: Agent remembers the hotel results from Turn 2 and compares cancellation policies without calling the tool again

## Hints
- `event.agent.state` is the dict you passed as `state={}` when creating the Agent — that's how `session_id` and `actor_id` reach your hooks
- The `on_agent_initialized` and `on_message_added` methods are already written — you just need to make them reachable by completing the class structure and registering the hooks
- `context.session_id` provides the session ID automatically from AgentCore — you don't need to pass it in the payload

## Common Errors
| Error | Fix |
|-------|-----|
| Agent forgets earlier turns | Check that `register_hooks()` correctly binds both callbacks |
| `NameError: HookProvider` | Complete Step 1 — import the hook classes from `strands.hooks` |
| `MEMORY_ID` is empty | Set it to the value from `agentcore memory create` output |
| Agent doesn't use memory at all | Check that `hooks=[]` and `state={}` are passed to the Agent constructor in Step 4 |