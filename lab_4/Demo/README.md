

# WanderBot — DEMO: Short-Term Memory (AgentCore Memory)

Topic   : Multi-turn conversations using a custom HookProvider and AgentCore Memory
Duration: ~5-6 minutes

## DEMO FLOW

1. Problem: stateless agents forget previous turns
2. Create a memory resource using agentcore memory create
3. Show the HookProvider approach — two lifecycle hooks
4. Demo a multi-turn conversation — agent remembers context across invocations

## KEY CONCEPTS

- HookProvider       : interface for hooking into agent lifecycle events
- AgentInitializedEvent : fires once when agent is set up — load prior turns
- MessageAddedEvent     : fires every time a message is added — persist it
- session_id         : identifies the conversation thread (from context)
- actor_id           : identifies the user (from payload)
- MemoryClient       : AgentCore Memory client for reading/writing events

## HOW TO RUN
```bash
  agentcore memory create WanderBot

  ER=$(python -c 'import yaml,sys; print(yaml.safe_load(open(".bedrock_agentcore.yaml"))["agents"]["WanderBot"]["aws"]["execution_role"])')
  ECR_URI=$(python -c 'import yaml,sys; print(yaml.safe_load(open(".bedrock_agentcore.yaml"))["agents"]["WanderBot"]["aws"]["ecr_repository"])')

  agentcore configure -e demo.py -n WanderBot -dt container -rf requirements.txt -er $ER -ecr $ECR_URI 

  agentcore deploy

  agentcore invoke '{"message": "Hi! I want to plan a trip to Rome.", "actor_id": "alice"}'
  agentcore invoke '{"message": "Are there any flights from LHR to FCO on 15 March 2026?", "actor_id": "alice"}'
  agentcore invoke '{"message": "Which one is the cheapest?", "actor_id": "alice"}'
```


## Datasets
- `datasets/flights.json` — flight records


