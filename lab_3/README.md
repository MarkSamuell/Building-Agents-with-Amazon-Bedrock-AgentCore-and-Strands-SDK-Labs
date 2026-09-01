# Exercise: Structured Outputs with Pydantic

## Overview
Add Pydantic validation to WanderBot's `search_hotels` tool. You will define Pydantic models that validate both the input arguments and the output data from the tool, ensuring the agent only works with clean, structured data — even when the underlying dataset has issues.

**Estimated time:** 15 minutes

## Learning Objectives
1. Define Pydantic `BaseModel` classes with typed fields and `Field` descriptions
2. Use Pydantic to validate tool input arguments
3. Use Pydantic to validate tool output data
4. Handle `ValidationError` to skip malformed records gracefully

## Prerequisites
- Completed Function Calling with custom tools
- Dataset in the `datasets/` folder: `hotels_broken.json`

## Setup
```bash
pip install -r requirements.txt
```

## Dataset
| File | Contents |
|------|----------|
| `datasets/hotels_broken.json` | 4 hotel records across 2 cities — 2 records contain data issues (invalid price, missing fields) |

## Field Pattern
Each field in a Pydantic model follows this pattern:
```python
field_name: data_type = Field(description="What this field represents, e.g. 'Example value'")
```

For optional fields:
```python
field_name: Optional[data_type] = Field(default=None, description="...")
```

For fields with constraints:
```python
field_name: data_type = Field(ge=0, description="...")  # ge = greater than or equal to
```

## Exercise Steps

### Step 1: Add Pydantic to Requirements
Add `pydantic` to `requirements.txt` so it gets installed when the agent is built.

### Step 2: Complete `HotelSearchInput`
Add the following fields
- `city` — str, name of the destination city
- `max_price_usd` — float, maximum price per night in USD

### Step 3: Complete `HotelOption`
Add the following fields using the pattern above:
- `hotel_id` — str, hotel identifier
- `name` — str, hotel name
- `city` — str, city where the hotel is located
- `star_rating` — int, star rating from 1 to 5 (use `ge=1, le=5` constraints)
- `price_per_night_usd` — float, price per night in USD (use `ge=0` constraint)
- `available` — bool, whether the hotel has availability
- `room_types` — list[str], available room types
- `amenities` — list[str], hotel amenities
- `check_in_time` — Optional[str], check-in time
- `check_out_time` — Optional[str], check-out time
- `cancellation_policy` — Optional[str], cancellation policy description

### Step 4: Wire Up the Agent
In the `invoke` function, create the Agent with the `search_hotels` tool and invoke it with the user's message.

## Deploy and Invoke
```bash

# Since we will be updating the existing agent, we set the execution role and ECR URI from the existing values available in .bedrock_agentcore.yaml

ER=$(python -c 'import yaml,sys; print(yaml.safe_load(open(".bedrock_agentcore.yaml"))["agents"]["WanderBot"]["aws"]["execution_role"])')

ECR_URI=$(python -c 'import yaml,sys; print(yaml.safe_load(open(".bedrock_agentcore.yaml"))["agents"]["WanderBot"]["aws"]["ecr_repository"])')

agentcore configure -e starter.py -n WanderBot -dt container -rf requirements.txt --disable-memory -er $ER -ecr $ECR_URI --non-interactive

agentcore deploy

agentcore invoke '{"message": "Show me hotels in Barcelona under $200 per night"}'
```

## Expected Behaviour
When you run the test query, the agent should return only **Barceloneta Beach Hotel** at $149/night. The other two Barcelona hotels are skipped:
- **Hotel Casa Marina** — price is the string `"check website"` instead of a number
- **Gothic Quarter Inn** — missing `star_rating` and `price_per_night_usd` fields

You will see validation warnings in the logs explaining why each record was skipped.

## Hints
- The `Field(description=...)` documents what each field expects — be specific with examples
- Constraints like `ge=0` (greater than or equal to 0) and `le=5` (less than or equal to 5) reject values outside the valid range
- `Optional[str]` with `default=None` means the field can be missing from the data without causing a validation error
- The tool function validates first, then filters by price — this lets Pydantic catch bad data before the price comparison runs
- `model_validate()` parses a dict into a Pydantic model and raises `ValidationError` if the data doesn't match

## Common Errors
| Error | Fix |
|-------|-----|
| `ModuleNotFoundError: pydantic` | Add `pydantic` to `requirements.txt` (Step 1) |
| `ValidationError` on all records | Check your field names match the keys in `hotels_broken.json` exactly |
| `TypeError: '<=' not supported` | Make sure the price filter runs after Pydantic validation, not before |
| Tool not being called by the agent | Check the tool's docstring — the LLM uses it to decide when to call the tool |
| Agent returns no results | Expected for the broken records — check the logs for validation warnings |