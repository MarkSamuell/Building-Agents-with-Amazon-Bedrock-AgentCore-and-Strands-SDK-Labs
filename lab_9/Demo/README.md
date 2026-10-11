# Demo: AgentCore Code Interpreter

## Topic
Isolated code execution with AgentCore Code Interpreter.

## Why Code Interpreter?
Agents regularly need to run code — arithmetic, data shaping, small scripts the LLM writes on the fly. Running that code inside your own application process is a bad idea:

- **Security** — LLM-generated code is untrusted input. Executing it in-process is arbitrary code execution.
- **Isolation** — one request's variables can bleed into the next.
- **Package conflicts** — the code may need libraries your app does not ship with.

AgentCore Code Interpreter gives you a managed, ephemeral Python sandbox per call. No host access, no internet, no state leaking between invocations.

## Architecture

```
Agent decides to call execute_python
         ↓
@tool function builds a Python script (f-string)
         ↓
code_session(REGION) opens the isolated sandbox
         ↓
code_client.invoke("executeCode", {..., "clearContext": True})
         ↓
Python runs in the sandbox — exact arithmetic
         ↓
Output streams back → tool returns the result
         ↓
Agent presents the answer to the customer
```

## Key Components

| Component | What it does |
|-----------|-------------|
| `code_session(REGION)` | Opens an ephemeral Python sandbox managed by AgentCore |
| `code_client.invoke("executeCode", {...})` | Runs your Python code inside the sandbox |
| `clearContext=True` | Resets the sandbox before running — no state from a previous call bleeds in |
| `response["stream"]` | The output is streamed back; iterate to get the result |
| `print(f"Generated Code: ...")` | Surfaces the LLM-written code in the logs for observability |

## Setup
```bash
pip install -r requirements.txt
agentcore configure -e demo.py -n WanderBot -dt container -rf requirements.txt --disable-memory -er $ER -ecr $ECR_URI --non-interactive
agentcore deploy
```

## How to Run
```bash
agentcore invoke '{"message": "Calculate the cost for 2 passengers: flight $450 each, 4 nights at $120/night, with insurance."}'
agentcore invoke '{"message": "What is the total for a solo trip? Flight $320, 3 nights at $95/night."}'
agentcore invoke '{"message": "Tokyo trip: flight $890, 7 nights at $180/night for 2 people. Total?"}'
```

## Verify in the Console
AWS Console → **Amazon Bedrock → AgentCore → Code Interpreter** — every `execute_python` call appears as a tracked session.
