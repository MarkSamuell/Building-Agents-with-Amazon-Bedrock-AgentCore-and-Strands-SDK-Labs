# Exercise: RAG with Bedrock Knowledge Bases

## Overview
Give WanderBot access to Horizon Travel's real policy and destination documents using Retrieval-Augmented Generation. You'll build the Knowledge Base from scratch on the console, then wire a custom `@tool` in the agent code that calls Bedrock's `retrieve()` API. The result is an agent that quotes exact numbers from the source documents instead of guessing.

**Estimated time:** 25 minutes (most of it is the console walkthrough + KB sync)

## Learning Objectives
1. Upload source documents to S3 and create a Bedrock Knowledge Base
2. Ingest + sync documents using Titan Text Embeddings v2 and S3 Vectors
3. Implement a custom Strands `@tool` that wraps `bedrock-agent-runtime.retrieve()`
4. Wire the tool into the agent and observe grounded, cited answers

## Architecture
```
S3 (policies + destination guides)
    ↓ sync
Bedrock Knowledge Base (Titan v2, S3 Vectors)
    ↓ retrieve(query)
Top-k chunks
    ↓
WanderBot Agent → grounded answer
```

## Prerequisites
- AWS account with Bedrock access
- An S3 bucket you can write to
- AgentCore Runtime role with `bedrock:Retrieve` and `bedrock:RetrieveAndGenerate` permissions

## Knowledge Base Documents
| File | Contents |
|------|----------|
| `datasets/travel_policies.txt` | Fare classes, cancellation, baggage, insurance, loyalty, etc. |
| `datasets/destination_guides.txt` | Eight city guides — Barcelona, Tokyo, Rome, Dubai, Sydney, Reykjavik, New York, Cape Town |

---

## Exercise Steps

The first two steps are **infrastructure** (console + CLI). The last two are **code** changes in `starter.py`.

### Step 1 (infra) — Upload Documents to S3
```bash
aws s3 cp datasets/travel_policies.txt     s3://your-bucket/wanderbot-kb/
aws s3 cp datasets/destination_guides.txt  s3://your-bucket/wanderbot-kb/
```

### Step 2 (infra) — Create the Knowledge Base
In the AWS Console: **Amazon Bedrock → Knowledge Bases → Create**

1. **Name:** `wanderbot-kb`
2. **IAM role:** Create new (Bedrock auto-generates with S3 read access)
3. **Data source:**
   - Type: **Amazon S3**
   - S3 URI: `s3://your-bucket/wanderbot-kb/`
4. **Parsing strategy:** Amazon Bedrock default parser
5. **Chunking:** Default
6. **Embeddings model:** **Amazon Titan Text Embeddings v2**
7. **Vector store:** **Amazon S3 Vectors**
8. Click **Create Knowledge Base**
9. Select the data source and click **Sync**. Wait for **Ready**.
10. Copy the **Knowledge Base ID** (10-char alphanumeric, e.g. `BSTUUEN8YZ`)

### Step 3 (code) — Implement the `search_knowledge_base` tool
In `starter.py`:

```python
import boto3

KB_ID  = "PASTE_YOUR_KB_ID_HERE"
REGION = "us-east-1"
_bedrock_runtime = boto3.client("bedrock-agent-runtime", region_name=REGION)


@tool
def search_knowledge_base(query: str) -> str:
    resp = _bedrock_runtime.retrieve(
        knowledgeBaseId=KB_ID,
        retrievalQuery={"text": query},
    )
    results = resp.get("retrievalResults", [])
    if not results:
        return f"No information found for: {query}"

    chunks = [r["content"]["text"] for r in results]
    return "\n---\n".join(chunks)
```

### Step 4 (code) — Wire the agent with the tool
Inside `invoke()`:

```python
agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[search_knowledge_base],
)
response = agent(user_message)
return response
```

---

## Deploy and Test

```bash
pip install -r requirements.txt
```

```bash
ER=$(python -c 'import yaml,sys; print(yaml.safe_load(open(".bedrock_agentcore.yaml"))["agents"]["WanderBot"]["aws"]["execution_role"])')
ECR_URI=$(python -c 'import yaml,sys; print(yaml.safe_load(open(".bedrock_agentcore.yaml"))["agents"]["WanderBot"]["aws"]["ecr_repository"])')
agentcore configure -e starter.py -n WanderBot -dt container -rf requirements.txt --disable-memory -er $ER -ecr $ECR_URI --non-interactive
agentcore deploy
```

```bash
agentcore invoke '{"message": "What is the refund policy for Economy Flex?"}'
agentcore invoke '{"message": "What are the baggage allowances for Economy Lite?"}'
agentcore invoke '{"message": "When is the best time to visit Tokyo?"}'
agentcore invoke '{"message": "What does Premium travel insurance cover?"}'
```

## Key Insight
The agent code is tiny — one `@tool`, one `retrieve()` call. The heavy lifting happens in the Knowledge Base: chunking, embedding, and semantic search over the vectors. The system prompt is what tells the agent **when** to reach for the tool and **how** to cite retrieved content.

## Common Errors
| Error | Fix |
|-------|-----|
| Empty results | Confirm the data source status is **Ready** in the KB console |
| `AccessDeniedException` on retrieve | Add `bedrock:Retrieve` and `bedrock:RetrieveAndGenerate` to the Runtime role |
| Agent doesn't call the tool | Reinforce in the system prompt: "ALWAYS use `search_knowledge_base`" |
| Wrong KB ID | KB ID is 10 alphanumeric chars — not the ARN, not the data source ID |

---

## Bonus: Use the Strands `retrieve` Tool

Instead of writing a custom `@tool`, you can use the built-in `retrieve` tool from `strands_tools` — same behaviour, far less code. Add it to `requirements.txt`

**Agent code** (`solution_bonus.py`):

```python
from strands_tools import retrieve

agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[retrieve],
)
```

No boto3 client, no `KB_ID` constant, no custom `@tool` function.

**Deploy with the KB ID as an environment variable:**

```bash
agentcore configure -e solution_bonus.py -n WanderBot -dt container -rf requirements.txt --disable-memory -er $ER -ecr $ECR_URI --non-interactive
agentcore deploy --env KNOWLEDGE_BASE_ID=YOUR_KB_ID
```

The `retrieve` tool reads `KNOWLEDGE_BASE_ID` from the environment at runtime, so the agent code is fully decoupled from any specific knowledge base. Swap environments just by changing the env var at deploy time.

## Files
| File | Purpose |
|------|---------|
| `starter.py` | Starter agent code — custom-tool variant |
| `solution.py` | Reference solution — custom-tool variant |
| `solution_bonus.py` | Bonus solution — Strands `retrieve` community tool |
| `datasets/travel_policies.txt` | Source document ingested into the KB |
| `datasets/destination_guides.txt` | Source document ingested into the KB |
