# Exercise: AgentCore Code Interpreter

## Overview
Add a `calculate_trip_cost` tool to WanderBot that runs exact arithmetic inside an isolated AgentCore Python sandbox — no LLM estimates, no risk of arbitrary code running in your application process.

**Estimated time:** 15 minutes

## Learning Objectives
1. Import `code_session` from `bedrock_agentcore.tools.code_interpreter_client`
2. Build a Python script as a string and execute it inside the sandbox
3. Understand `clearContext=True` — why call-level isolation matters
4. Read results back from `response["stream"]`

## Prerequisites
- AgentCore Code Interpreter runtime enabled in your AWS account

---

## How the Code Interpreter Works

```
@tool function builds a Python script (f-string with parameters)
       ↓
with code_session(REGION) as cs:          ← opens the isolated sandbox
    response = cs.invoke("executeCode", {
        "code":         code,             ← your Python script
        "language":     "python",
        "clearContext": True,             ← fresh sandbox every call
    })
    for event in response["stream"]:      ← stream back the output
        return json.dumps(event["result"])
```

### Why `clearContext=True`?
Without it, variables and definitions from a previous call persist in the sandbox — one customer's state can bleed into the next. With it, every execution starts with a completely clean Python environment.

---

## Exercise Steps

### Step 1 — Import `code_session`
```python
from bedrock_agentcore.tools.code_interpreter_client import code_session
```

### Step 2 — Set the REGION constant
```python
REGION = "us-east-1"
```

### Step 3 — Implement `calculate_trip_cost`
```python
@tool
def calculate_trip_cost(code: str, description: str = "") -> str:
    """Execute Python code in an isolated AgentCore sandbox and return the output."""

    if description:
        code = f"# {description}\n{code}"

    print(f"\nGenerated Code:\n{code}\n")

    with code_session(REGION) as code_client:
        response = code_client.invoke("executeCode", {
            "code": code,
            "language": "python",
            "clearContext": True,
        })

    for event in response["stream"]:
        return json.dumps(event["result"])
```

### Step 4 — Wire up the agent
```python
agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[calculate_trip_cost],
)
response = agent(user_message)
return response
```

## Deploy and Test
```bash
pip install -r requirements.txt
agentcore configure -e starter.py -n WanderBot -dt container -rf requirements.txt --disable-memory -er $ER -ecr $ECR_URI --non-interactive
agentcore deploy
```

```bash
agentcore invoke '{"message": "2 rooms for 5 nights at $180/night, plus 12% tax. Total?"}'
agentcore invoke '{"message": "Solo stay: 3 nights at $95/night with breakfast $18/day."}'
agentcore invoke '{"message": "Family booking: 2 rooms for 7 nights at $220/night, plus $40/day parking for 2 cars."}'
```

Every invocation logs the generated Python under `Generated Code:` — useful for seeing what the LLM actually wrote.

---

## Bonus: Custom Code Interpreters in the Console
AWS Console → **Amazon Bedrock → AgentCore → Code Interpreter** — you can create additional sandboxes here, same pattern as the custom browsers. Different agents can point at different Code Interpreters for different use cases.

## Common Errors
| Error | Fix |
|-------|-----|
| `code_session` not found | Check the import path: `from bedrock_agentcore.tools.code_interpreter_client import code_session` |
| Empty output | Make sure the generated Python calls `print()` — silent scripts return nothing |
| `NameError` on a variable set in a previous call | That's `clearContext=True` working as intended — each call is isolated |
| Double-braces in f-strings | Use `{{` and `}}` to produce literal `{` / `}` in the generated Python |

## Files
| File | Purpose |
|------|---------|
| `starter.py` | Starter — 4 TODOs |
| `solution/.py` | Reference solution |
| `requirements.txt` | Runtime dependencies |
