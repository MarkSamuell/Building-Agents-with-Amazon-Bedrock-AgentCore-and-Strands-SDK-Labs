# Exercise: Function Calling

## Overview
Add custom tools to WanderBot using the Strands `@tool` decorator. You will implement three data-driven tools (flights, hotels, exchange rates) plus integrate the built-in `current_time` tool, giving WanderBot the ability to search real datasets and answer travel queries with live data.

**Estimated time:** 15 minutes

## Learning Objectives
1. Use the `@tool` decorator to define custom Python functions as agent tools
2. Write effective tool docstrings that guide the LLM's tool selection
3. Import and use built-in Strands tools (`current_time`)
4. Register multiple tools with a Strands Agent

## Prerequisites
- Completed AgentCore Runtime basics
- Datasets in the `datasets/` folder: `flights.json`, `hotels.json`, `exchange_rates.json`

## Setup
```bash
pip install -r requirements.txt
```

## Datasets
| File | Contents |
|------|----------|
| `datasets/flights.json` | 15 flight records with routes, times, prices, status |
| `datasets/hotels.json` | 10 hotels across 4 cities with ratings and amenities |
| `datasets/exchange_rates.json` | 15 currency exchange rates relative to USD |

## Exercise Steps

### Step 1: Add Imports
Add `tool` to the strands import and import `current_time` from `strands_tools`.

### Step 2: Implement `search_flights`
- Add the `@tool` decorator
- Add a docstring describing when to use this tool, the expected parameters, and the return format

### Step 3: Implement `search_hotels`
- Add the `@tool` decorator
- Add a docstring describing when to use this tool, the expected parameters, and the return format

### Step 4: Implement `get_exchange_rate`
- Add the `@tool` decorator
- Add a docstring describing when to use this tool, the expected parameters, and the return format

### Step 5: Wire Up the Agent
In the `invoke` function, create the Agent with all four tools


## Local Test
```bash
ER = <Execution Role ARN> # ← Fetch this from .bedrock_agentcore.yaml or your AWS console
ECR_URI = <ECR URI for this project> # ← Fetch this from .bedrock_agentcore.yaml or your AWS console

agentcore configure -e demo.py -n WanderBot -dt container -rf requirements.txt --disable-memory -er $ER -ecr $ECR_URI --non-interactive
agentcore dev

agentcore invoke --dev '{"message": "Find flights from BCN to FCO on 2026-03-20"}'

```

## Deploy to AgentCore Runtime

```bash

agentcore deploy

# Hotel search with budget
agentcore invoke '{"message": "What hotels are available in Rome under $200?"}'

# Currency conversion
agentcore invoke '{"message": "How many euros will I get for 500 US dollars?"}'

# Multi-tool (flights + currency)
agentcore invoke '{"message": "Find flights from Barcelona to Rome on 2026-03-20 and convert $500 to EUR"}'
```

## Hints
- The `@tool` decorator reads the function's docstring to generate the tool schema — make docstrings descriptive
- Type hints on parameters (e.g. `origin: str`) are required for schema generation
- Default parameter values (e.g. `max_price_usd: float = 9999.0`) become optional in the schema
- Use `Path(__file__).resolve().parent / "datasets"` to locate files relative to the exercise folder

## Common Errors
| Error | Fix |
|-------|-----|
| `FileNotFoundError: flights.json` | Check that `DATA_DIR` points to the `datasets/` folder |
| Tool not being called by the agent | Improve the tool's docstring — the LLM uses it to decide when to call the tool |
| `JSONDecodeError` | Ensure you're reading the file with `encoding="utf-8"` |
