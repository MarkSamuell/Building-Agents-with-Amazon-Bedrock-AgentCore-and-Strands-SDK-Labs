# Demo: AgentCore Gateway

## Topic
Calling Lambda-backed tools via AgentCore Gateway and MCP (direct Lambda target)

## Duration
~8 minutes

## Architecture
```
WanderBot (Strands Agent)
    ↓  tool call (MCP protocol)
AgentCore Gateway  (No Authentication)
    ↓  direct Lambda invocation
booking_lambda.py  /  hotel_lambda.py
```


## Demo Flow
1. **(1 min)** Recap Function calling: local `@tool` works for dev, but Lambda is production. Enter AgentCore Gateway.
2. **(2 min)** Explain the architecture: Gateway fronts Lambdas via MCP; no API Gateway layer needed
3. **(2 min)** Show `MCPClient` + `streamable_http_client` — `list_tools_sync()` discovers tools automatically
4. **(2 min)** Live demo: booking lookup

## Key Concepts
- **AgentCore Gateway**: MCP-protocol server that fronts Lambda functions
- **Direct Lambda target**: Gateway invokes Lambda directly 
- **`MCPClient` + `list_tools_sync()`**: discovers all Gateway tools — no `@tool` code in the agent
- **No authentication** (this lesson): Later, we add AgentCore Identity for authenticated calls

## Talking Points
- "The agent code barely changed from Function calling. We swapped `@tool` functions for `MCPClient` tool discovery. The LLM can't tell the difference — it just sees tool schemas."
- "There's no API Gateway here. The AgentCore Gateway calls the Lambda directly. The Lambda doesn't handle HTTP routing — it reads the function name and parameters from the event."
- "The `schema/` files are what you paste into the Gateway console. They're the bridge between the MCP tool definition and the Lambda function."

## Setup

### 1. Deploy Lambda functions
```bash
# Package and deploy booking_lambda.py
zip booking_lambda.zip lambda/booking_lambda.py
aws lambda create-function \
  --function-name wanderbot-booking-tools \
  --runtime python3.14 \
  --handler booking_lambda.lambda_handler \
  --zip-file fileb://booking_lambda.zip \
  --role arn:aws:iam::ACCOUNT_ID:role/lambda-execution-role

```

### 2. Create AgentCore Gateway
In the AWS Console → Amazon Bedrock → AgentCore → Gateways:
1. **Create Gateway** — Name: `wanderbot-gateway`, Authentication: **No Authentication**
2. **Add target** for booking tools:
   - Target type: Lambda
   - Function: `wanderbot-booking-tools`
   - Schema: paste contents of `schema/booking_schema.json`

### 3. Configure and run
```bash
pip install -r requirements.txt
agentcore configure -e demo.py -n WanderBot -dt container -rf requirements.txt --disable-memory -er $ER -ecr $ECR_URI --non-interactive
agentcore deploy
```

## How to Run
```bash
agentcore invoke '{"message": "What bookings does alice@example.com have?"}'
agentcore invoke '{"message": "Can you look up booking BK-1001?"}'
```

## Files
| File | Purpose |
|------|---------|
| `lambda/booking_lambda.py` | Lambda: booking lookup and email search |
| `schema/booking_schema.json` | OpenAPI schema — paste into Gateway console for booking target |
