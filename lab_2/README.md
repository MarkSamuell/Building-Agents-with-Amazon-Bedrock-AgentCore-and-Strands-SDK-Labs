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

---

# AWS resources this lab creates

_Everything below this line is added notes, not part of the course-provided brief._

Deployed 2026-08-29 via `direct_code_deploy` into Vocareum account `484086766087`,
`us-east-1`. Five resources — and the absences say as much as the presences.

| Resource | Identifier | Console location |
| --- | --- | --- |
| **Agent runtime** | `WanderBot3-jJXNSUD2VQ`, version 1, `DEFAULT` endpoint, `READY` | Bedrock AgentCore → Agent Runtimes |
| **Execution role** | `AmazonBedrockAgentCoreSDKRuntime-us-east-1-e0238e14b6` | IAM → Roles |
| ↳ its inline policy | `BedrockAgentCoreRuntimeExecutionPolicy-WanderBot3` | same role, Permissions tab |
| **Deployment artifact** | `s3://bedrock-agentcore-codebuild-sources-.../WanderBot3/deployment.zip`, 45.7 MiB | S3 |
| **Log group** | `/aws/bedrock-agentcore/runtimes/WanderBot3-jJXNSUD2VQ-DEFAULT` | CloudWatch → Log groups |

**Not created, and that is the point:** no ECR repository, no CodeBuild project, and
*one* IAM role rather than two. That is the entire difference between direct code
deploy and the container path.

The S3 bucket is named `bedrock-agentcore-codebuild-sources-...` even though no
CodeBuild is involved — a naming leftover, not a sign something went wrong.

## What to read, not merely confirm

- **The role's Trust relationships tab** — `bedrock-agentcore.amazonaws.com` with
  `aws:SourceAccount` and `aws:SourceArn` conditions. That is confused-deputy
  protection: without it the service could be induced into assuming this role on
  behalf of a different account.
- **The role's inline policy** — the two Bedrock ARN forms side by side: the
  inference profile carrying an account id, and the foundation model with an *empty*
  account segment, because foundation models are not account-scoped.
- **The runtime's version and endpoint** — V1 created automatically with `DEFAULT`
  pointing at it.
- **A log stream** — the `Tool #1: search_flights` lines. A plausible-looking answer
  is not evidence a tool ran; this is.

> **Note:** the console will report `storedBytes: 0` on that log group even after
> several invocations. CloudWatch's stored-bytes figure lags badly. Open the stream
> rather than trusting the number.

## Verified here for the first time

**Non-Python files ship with a direct-code deployment.** All three tools read JSON
from `datasets/`, and the *deployed* agent returned real records — Hotel Campo de'
Fiori `HTL-008` at $165, flight `HZ-450` at gate G07. So the zip includes everything
under the source directory, not just `.py` files. Worth knowing before relying on it.

## Cost

Nothing accrues while idle: microVM billing is per session, per second, on CPU
actually consumed. The only standing charge is the 45.7 MiB zip at S3 Standard
rates. Billed to Vocareum, not to you.

## Teardown

```bash
agentcore destroy --agent WanderBot3 --dry-run     # preview, and read the warnings
agentcore destroy --agent WanderBot3 --force
```

`destroy` will **not** remove the S3 bucket or the CloudWatch log group. Enumerate
AWS and delete those by hand afterwards — it works from the config file, and the
config file is not an inventory.