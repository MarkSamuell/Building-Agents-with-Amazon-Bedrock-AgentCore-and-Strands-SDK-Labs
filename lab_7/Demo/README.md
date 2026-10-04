# Demo: RAG with Amazon Bedrock Knowledge Bases

## Topic
Ground WanderBot's answers in Horizon Travel's real policy and destination documents using Retrieval-Augmented Generation backed by a Bedrock Knowledge Base.

## Duration
~6 minutes

## What the Demo Shows
- A Bedrock Knowledge Base already created from two source documents on S3 (policies + destination guides), using S3 Vectors + Titan v2
- A custom Strands `@tool` that wraps `boto3 bedrock-agent-runtime.retrieve()`
- The agent calling the tool on policy/destination questions and quoting exact figures from the retrieved chunks

## Architecture
```
S3 (policies + destination guides)
    ↓ sync
Bedrock Knowledge Base (Titan v2 embeddings, S3 Vectors)
    ↓ retrieve(query)
Top-k chunks
    ↓
WanderBot Agent → grounded answer
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| **Knowledge Base** | Managed vector store — ingests S3 docs, chunks, embeds, indexes |
| **Titan Text Embeddings v2** | Embedding model used for both documents and queries |
| **S3 Vectors** | Native Bedrock vector store — no OpenSearch/Aurora needed |
| **`retrieve()`** | Semantic search API — returns top-k chunks for a query |
| **Custom `@tool`** | One-function Strands tool wrapping the `retrieve()` call |
| **Grounding** | Anchoring the LLM's answer in retrieved text to avoid hallucination |

## Pre-Bake (optional)
`../PREBAKE.md` describes the same S3 + Knowledge Base setup the recording walks through, in case you want to pre-stage it for a re-take. The recording itself creates everything live.

## Demo Flow (recording)
1. Motivate RAG — hallucination problem, need grounded answers
2. Upload the two source documents to S3
3. Create the Knowledge Base on the console — Titan v2 + S3 Vectors, sync to Ready
4. Paste the KB ID into `demo.py`
5. Walk through the `@tool` — `retrieve()`, chunk join
6. Deploy and invoke on a specific policy question
7. Show the agent quoting exact numbers from the retrieved chunk

## Talking Points

> "The LLM didn't remember this refund number. It retrieved the exact policy chunk and quoted it. That's grounding — and it's how you stop agents from hallucinating."

> "The whole RAG integration is one `@tool` that calls `retrieve()`. No extra SDK, no new runtime — just boto3."

## Files
| File | Purpose |
|------|---------|
| `demo.py` | Agent code with the `search_knowledge_base` tool |
| `datasets/travel_policies.txt` | Source document — ingested into the KB |
| `datasets/destination_guides.txt` | Source document — ingested into the KB |
| `requirements.txt` | Runtime dependencies |
