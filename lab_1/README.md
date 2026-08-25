# Lab 1 — Strands SDK + AgentCore Runtime

First version of **WanderBot**, Horizon Travel's AI travel concierge: one Strands
`Agent`, one built-in `calculator` tool, wrapped in a `BedrockAgentCoreApp` so it
can be served over HTTP.

Course: *Building Agents with Amazon Bedrock AgentCore and Strands SDK*, Module 1.
Run 2026-08-24 against the Vocareum lab account `484086766087` in `us-east-1`.

Conceptual background — the agent loop, the three layers, the runtime contract —
lives in `.kiro/course-notes.md`. This file records what actually happened.

---

## Objectives

1. Instantiate a Strands `Agent` backed by a `BedrockModel`
2. Wrap it as a deployable service with `BedrockAgentCoreApp` and `@app.entrypoint`
3. Plug in the built-in `calculator` tool
4. Iterate locally with `agentcore dev`, then ship with `agentcore deploy`

Model: `us.amazon.nova-2-lite-v1:0` — a **cross-region inference profile**, not a
plain foundation model. The `us.` prefix lets Bedrock route to whichever US region
has capacity, and it means the execution role needs `bedrock:InvokeModel` on both
the profile ARN and the underlying foundation-model ARN.

## Files

| File | Purpose |
| --- | --- |
| `starter.py` | The exercise skeleton with five TODOs. Local copy — see known issues |
| `requirements.txt` | Not yet copied across from the lab |

## Running it

Two routes work, neither needs Docker or a deploy.

```bash
# Route 1: the toolkit's dev server, with hot reload
pip install uv          # the toolkit needs uv; without it dev fails with FileNotFoundError
agentcore dev           # uvicorn on 0.0.0.0:8080

# in a second terminal
agentcore invoke --dev '{"message": "A flight costs $349. Hotel is $175/night for 4 nights. Total?"}'
```

```bash
# Route 2: no toolkit at all -- this is what the __main__ guard is for
python starter.py
curl http://localhost:8080/ping
curl -X POST http://localhost:8080/invocations \
  -H 'Content-Type: application/json' \
  -d '{"message": "What is 3,247 multiplied by 891?"}'
```

Both call Bedrock for real. Only the hosting is local, so model access and IAM are
genuinely exercised. Neither can catch a missing entry in `requirements.txt`,
because both use already-installed packages — only a container build does that.

## What the dev server proved

**The persona comes from the system prompt.** The agent volunteers Horizon's
flights, hotels, insurance and its Rewards tiers (Silver, Gold, Platinum). None of
that is in the model's general knowledge, so it can only have come from the prompt.

**The agent is completely stateless.** Asked `"what about 5 nights?"` immediately
after a question about 4 nights at $175, it had no idea what was being referred to
and asked for destination and dates. Three causes compound: the `Agent` is built
_inside_ `invoke()` so every request starts with empty `agent.messages`, memory was
disabled at configure time, and each `invoke` is a separate call. Multi-turn
conversation has to be added deliberately.

**Tool use is not yet proven.** The agent returned $1,049 for `$349 + 4 × $175`,
which is correct — but it is also arithmetic the model can do unaided, so a correct
answer is equally consistent with the calculator never being called. Proving it
needs either the tool invocation visible in the dev server log, or a sum the model
would get wrong on its own, such as `3,247 × 891` (= 2,893,077).

## ❌ Blocked: `agentcore deploy`

```
❌ Build failed during COMPLETED phase
❌ CodeBuild failed with status: STOPPED
```

**Vocareum terminates CodeBuild builds in the lab account. This is not fixable
from inside the lab, and nothing in the agent code is involved.**

Why `STOPPED` is the whole clue: CodeBuild sets that status **only** when the
`StopBuild` API is called. An internal provisioning failure produces `FAILED`
along with a context message explaining itself. This produced neither.

Evidence gathered from the account:

| Observation | Source |
| --- | --- |
| `PROVISIONING` phase status `STOPPED` after 1–4s; `COMPLETED` never ran | `codebuild batch-get-builds` |
| Every phase `contexts` field null — CodeBuild logged no reason of its own | same |
| Log streams created but `storedBytes: 0` — no build command ever executed | `logs describe-log-streams` |
| Reproduced 3× across 2 agents (`WanderBot`, `Solu`) with freshly created roles, projects and ECR repos | three `agentcore deploy` runs |
| EventBridge rule `voc-codebuild-cw-rule`, **enabled**, matching `{"source":["aws.codebuild"],"detail-type":["CodeBuild Build State Change"]}` | `events list-rules` |
| Sibling rules `voc-ec2-cw-rule`, `voc-rds-cw-rule`, `voc-redshiftapi-cw-rule` — a cost-control family over hourly-billed services | same |
| Reading that rule's targets is an **explicit deny** in Vocareum's SCP `p-3zsdtilq` from org master `401209005059` | `events list-targets-by-rule` |
| `cloudtrail:LookupEvents` unavailable, so the `StopBuild` caller cannot be named | `cloudtrail lookup-events` |

Conclusively ruled out: the agent code, the generated Dockerfile,
`requirements.txt`, the IAM roles (all created successfully), and the compute type
— `BUILD_GENERAL1_MEDIUM` on `ARM_CONTAINER` is a documented, valid pairing at
7 GB and 4 vCPUs.

The one unprovable link is that this rule's hidden target is what calls
`StopBuild`. Every other step in the chain is confirmed. Worth reporting to
Udacity: a course whose deployment step is blocked by its own lab account is
their defect.

Two other deploy routes are also unavailable in the lab: `--local-build` needs a
container engine (none installed) and the VM is `linux/amd64` while Runtime
requires `linux/arm64`.

## Still untested

**Direct Code Deploy** — zips the source to S3 and calls the Runtime API without
touching CodeBuild, so the EventBridge rule has nothing to fire on. The configure
menu only offers it when `uv` is present, which it now is, so it needs a fresh
`agentcore configure` to switch off container mode. This is the most promising
remaining path to a real deployment.

## Known issues in this copy

- `starter.py` calls `BedrockModel(MODEL_ID)` positionally. The constructor is
  keyword-only — its signature begins with a bare `*` — so this raises
  `TypeError` on import. It must be `BedrockModel(model_id=MODEL_ID)`.
- `starter.py`'s system prompt omits Horizon Travel's services, which Step 4 of the
  exercise asks for. Without them the agent invents answers to questions such as
  "How do I contact Horizon Travel customer support?".
- `region_name` is not set. Per the Strands API reference it defaults to the
  `AWS_REGION` environment variable, or **us-west-2** if that is unset — it does
  *not* read the region from your AWS profile. Worth passing explicitly.
- `requirements.txt` has not been copied across, and Strands is not installed
  locally, so neither run route works on this machine yet.
