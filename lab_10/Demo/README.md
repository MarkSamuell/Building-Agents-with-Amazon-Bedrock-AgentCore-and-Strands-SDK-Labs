# Demo: AgentCore Observability

## Topic
Observing agents and tool calls with AgentCore's built-in OpenTelemetry instrumentation.

## Why Observability Matters
Agents fail in weird ways — a tool times out, the model picks the wrong tool, token costs creep up silently, a customer sees an odd answer you can't reproduce. Without traces you are guessing. With them, every invocation is a tree you can click into.

The good news: on AgentCore Runtime, observability is essentially free.

## How It Works

Because this agent runs inside **AgentCore Runtime**, observability is built in. AgentCore automatically:

- Wraps every agent invocation in an OpenTelemetry span
- Creates a child span for each tool call (name, inputs, output, duration)
- Captures model, token counts, and error traces
- Ships all traces to CloudWatch and surfaces them in **CloudWatch → GenAI Observability → Bedrock AgentCore**

No hooks. No `boto3`. No custom metrics code. One dependency enables all of it:

```
aws-opentelemetry-distro
```

**A nice detail:** when you deploy via `agentcore configure && agentcore deploy`, the starter toolkit adds this distro into the generated Dockerfile automatically. Every agent you've deployed in this course has been fully instrumented from day one — even without adding it to `requirements.txt` yourself. If you ever build your own image from scratch, include the distro manually.

```
Agent invocation span
  ├── search_flights span  (origin, destination, result, latency)
  └── search_hotels span   (city, max_price, result, latency)
```

## Setup

```bash
pip install -r requirements.txt
agentcore configure -e demo.py -n WanderBot -dt container -rf requirements.txt --disable-memory -er $ER -ecr $ECR_URI --non-interactive
agentcore deploy
```

## Run the Demo

Because the agent is deployed as a container, consecutive `agentcore invoke` calls hit the same live runtime session — CloudWatch groups them automatically. To start a fresh session, call `agentcore stop-session` between invokes.

```bash
# Session 1 — planning a Tokyo trip (two turns, one session)
agentcore invoke '{"message": "Find flights from London to Tokyo"}'
agentcore invoke '{"message": "Hotels in Tokyo under $200/night"}'

# Break the session, start a fresh one
agentcore stop-session

# Session 2 — planning a Rome trip
agentcore invoke '{"message": "Flights from New York to Rome"}'
agentcore invoke '{"message": "Hotels in Rome"}'
```

## What to Observe in CloudWatch

Navigate to: **CloudWatch → GenAI Observability → Bedrock AgentCore**

| View | What it shows |
|------|---------------|
| **Agents** | All deployed agents — invocation count, avg latency, error rate |
| **Sessions** | Grouped by session — every turn from the same conversation together |
| **Traces** | Each invocation as a span tree: agent call → tool call spans |
| **Transaction Search** | Filter by service, time range, or span duration |

### Reading a Trace

```
AgentInvocation   total ~3.2s | model: nova-2-lite | tokens 512 in / 128 out
  ├── search_flights   inputs: origin=LHR, destination=HND → 3 results, 120ms
  └── search_hotels    inputs: city=Tokyo, max_price=200.0 → 2 results, 95ms
```

Each tool span carries its inputs, its output, and its duration. If the agent picked the wrong tool or a tool timed out, you see it here.
