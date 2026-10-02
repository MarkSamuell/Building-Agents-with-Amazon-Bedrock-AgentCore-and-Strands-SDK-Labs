# Exercise: AgentCore Gateway

## Overview
Connect WanderBot to Lambda-backed tools via AgentCore Gateway. Instead of defining tools with `@tool`, you'll discover them automatically from the Gateway using `MCPClient` and `list_tools_sync()`.

**Estimated time:** 20 minutes

## Learning Objectives
1. Describe the Agent → Gateway → Lambda architecture
2. Import and configure `MCPClient` with `streamable_http_client`
3. Use `list_tools_sync()` to discover tools registered in the Gateway
4. Pass discovered tools to a Strands Agent
5. Explain what the schema files in `schema/` are for

## Architecture
```
WanderBot (Strands Agent)
    ↓  tool call (MCP protocol)
AgentCore Gateway  (No Authentication)
    └── Lambda target  → wanderbot-booking-tools
```

## Prerequisites
- Completed Function Calling lesson
- AWS credentials configured 

## Setup

### 1. Deploy Lambda functions
Deploy both Lambda functions before starting the exercise. 
- **wanderbot-booking-tools** — booking_lambda.py

### 2. Create AgentCore Gateway (via Console)
In the AWS Console → Amazon Bedrock → AgentCore → Gateways:

1. **Create Gateway** — Name: `wanderbot-gateway`, Authentication: **No Authentication**
2. **Add target** for booking tools:
   - Target type: Lambda
   - Name: `wanderbot-booking-tools`
   - Lambda ARN: your `wanderbot-booking-tools` function ARN
   - Schema: paste contents of `schema/booking_lambda.json`
3. Copy the **Gateway URL** from the console after creation

### 3. Configure environment
In your `solution.py`, set the Gateway endpoint:
```python
GATEWAY_ENDPOINT = "https://<gateway-url>/mcp"
```
Install dependencies:
```bash
pip install -r requirements.txt
```

## Key Concept: What the Schema Files Do
The Gateway converts the schema into MCP tool definitions. When `list_tools_sync()` is called, it returns these definitions as Strands-compatible tool objects — ready to pass directly to `Agent(tools=...)`.

## Exercise Steps

### Step 1: Import the MCP classes
```python
from mcp.client.streamable_http import streamable_http_client
from strands.tools.mcp.mcp_client import MCPClient
```

### Step 2: Open a Gateway connection
```python
client = MCPClient(
    lambda: streamable_http_client(url=GATEWAY_ENDPOINT)
)
```

### Step 3: Discover tools
```python
with client:
    tools = client.list_tools_sync()
```

### Step 4: Create the Agent and invoke it
```python
    agent = Agent(model=model, system_prompt=SYSTEM_PROMPT, tools=tools)
    response = agent(user_message)
```

## How to Test
```bash
agentcore configure -e starter.py -n WanderBot -dt container -rf requirements.txt --disable-memory -er $ER -ecr $ECR_URI --non-interactive
```
```bash
agentcore deploy
```
```bash
agentcore invoke '{"message": "Can you look up booking BK-1001?"}'
```
```bash
agentcore invoke '{"message": "What bookings does alice@example.com have?"}'
```

## Hints
- `list_tools_sync()` returns a list of Strands tool objects; pass it directly to `tools=` in `Agent()`
- No `@tool` decorators needed — the tools are defined in the Gateway via the schema files

## Common Errors
| Error | Fix |
|-------|-----|
| `Connection refused` | Check `GATEWAY_ENDPOINT` is set and the Gateway is active |
| `0 tools discovered` | Verify the Lambda target is registered in the Gateway with correct schema |
| Agent answers without tools | Ensure tools are passed as `tools=tools`, not `tools=[]` |

## Files
| File | Purpose |
|------|---------|
| `lambda/booking_lambda.py` | Lambda: booking lookup and email search |
| `schema/booking_lambda.json` | Tool schema for booking Lambda target |
