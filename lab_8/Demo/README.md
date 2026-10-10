# Demo: Long-Term Memory with AgentCore Memory

## Topic
Persistent cross-session memory for WanderBot — built on top of the memory resource from L04 by adding two long-term strategies.

## Duration
~6 minutes

## What the Demo Shows
- Editing the existing memory resource in the AgentCore console to add two long-term strategies: `SEMANTIC` and `USER_PREFERENCE`
- A `WanderBotMemoryHook` that retrieves memories per namespace on every turn and saves the interaction afterwards
- Session 1 → Session 2 continuity: a second session remembers Alice's preferences with no code change to recall them

## Architecture
```
L04 Memory resource
  + SEMANTIC        strategy  → wanderbot/{actorId}/facts
  + USER_PREFERENCE strategy  → wanderbot/{actorId}/preferences

            ↑ create_event()                  ↓ retrieve_memories()
                                              (prepended as Traveller Context)

              WanderBot Agent + WanderBotMemoryHook
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| **MemoryClient** | AgentCore managed memory store — same resource as L04 |
| **Strategy** | A template that drives fact / preference extraction into its own namespace |
| **Namespace** | `wanderbot/{actorId}/…` — per-user scope, `{actorId}` resolved at runtime |
| **`get_memory_strategies()`** | Fetches namespace templates once at hook init |
| **`retrieve_memories()`** | Namespace-scoped semantic search for the current turn |
| **`create_event()`** | Persists a `(USER, ASSISTANT)` pair so memories get extracted |
| **`context.session_id`** | AgentCore-assigned session id, same pattern as L04 |
| **`agent.state`** | How `actor_id` + `session_id` reach the hook callbacks |

## Demo Flow (recording)
1. Recap the existing limitation — short-term memory resets on restart
2. Open the existing memory resource in the Console and add the two long-term strategies
3. Walk through `demo.py` — `get_namespaces`, the hook, `agent.state`
4. Deploy and run Session 1 (introduce Alice, share preferences)
5. Run Session 2 (fresh invoke → `context.session_id` is new) — the agent remembers Alice
6. "What do you remember about me?" as the closing moment

## Talking Points

> "Short Term memory gave the agent memory within a session. Long term memory strategies gives it memory across sessions. Same memory resource — we just layer two long-term strategies on top."

> "Hooks stay silent. The agent code doesn't know memory exists — it just sees a Traveller Context block appear at the top of the user message."

## Files
| File | Purpose |
|------|---------|
| `demo.py` | Agent + memory hook |
| `requirements.txt` | Runtime dependencies |
