# Lab 1 — Strands SDK + AgentCore Runtime

First version of **WanderBot**, Horizon Travel's AI travel concierge: one Strands
`Agent`, one built-in `calculator` tool, wrapped in a `BedrockAgentCoreApp` and
deployed to AgentCore Runtime.

Course: *Building Agents with Amazon Bedrock AgentCore and Strands SDK*, Module 1.
Worked 2026-08-24 to 08-27 against the Vocareum lab account `484086766087` in
`us-east-1`. Started on the course VM, finished locally on an arm64 Mac.

Conceptual background — the agent loop, the three layers, the runtime contract —
lives in `.kiro/course-notes.md`. This file records what actually happened.

**Status: complete.** Every objective met, including a live deployment, though by a
route the course does not teach.

---

## Objectives

1. Instantiate a Strands `Agent` backed by a `BedrockModel` — done
2. Wrap it as a service with `BedrockAgentCoreApp` and `@app.entrypoint` — done
3. Plug in the built-in `calculator` tool — done, and **proven to fire**
4. Iterate locally with `agentcore dev`, then ship with `agentcore deploy` — done,
   via direct code deploy rather than the container path

Model: `us.amazon.nova-2-lite-v1:0` — a **cross-region inference profile**, not a
plain foundation model. The underlying model is `amazon.nova-2-lite-v1:0`, and the
execution role needs `bedrock:InvokeModel` *and*
`bedrock:InvokeModelWithResponseStream` on both ARN forms.

## Files

| File | Purpose |
| --- | --- |
| `starter.py` | The agent. Fixed: `BedrockModel(model_id=..., region_name=...)` |
| `requirements.txt` | Four direct dependencies, pinned |
| `README.md` | This file |

`solution.py` was never copied off the VM, so there is no reference to diff against.

## Environment

Local, not the VM, and better in every relevant way: arm64 native against an
arm64-only Runtime, Python 3.12.12, with `uv` and Docker available.

```bash
uv venv
uv pip install -r lab_1/requirements.txt
```

Credentials come from `[default]` in `~/.aws-personal/`, which resolves to
`assumed-role/voclabs`. The `agentcore` CLI has **no `--profile` option** — it uses
the plain boto3 chain — so the profile has to *be* the default. A shell that was not
launched via `kiro-personal` reads `~/.aws/` instead and fails with "Unable to
locate credentials".

## Running it locally

Two routes, neither needing Docker or a deploy.

```bash
# Cheapest: no toolkit at all -- this is what the __main__ guard is for
python lab_1/starter.py
curl http://localhost:8080/ping
curl -X POST http://localhost:8080/invocations \
  -H 'Content-Type: application/json' \
  -d '{"message": "What is 3,247 multiplied by 891?"}'
```

```bash
# Toolkit, with hot reload
agentcore dev
agentcore invoke --dev '{"message": "..."}'      # JSON, not a bare string -- see below
```

Both call Bedrock for real; only the hosting is local. Neither can catch a missing
entry in `requirements.txt`, because both use already-installed packages.

## What was verified

**Tool use fires — locally and deployed.** The decisive evidence is in the runtime
log, not the answer:

```
Tool #1: calculator
[WARNING] strands_tools.calculator: DEPRECATION WARNING: calculator is deprecated...
```

Worth being strict about this: `3,247 x 891 = 2,893,077` being *correct* proves
nothing on its own, since a model may get arithmetic right unaided. Only the tool
marker in the log discriminates. An earlier `$349 + 4 x $175 = $1,049` test looked
like proof and was not.

**The deployed agent uses its execution role**, logging
`Found credentials from IAM Role: execution_role`. So hardcoding a `profile_name`
in the agent would work locally and break in Runtime.

**The persona comes from the system prompt**, and so do its gaps: with Horizon's
services unstated, the model invents a plausible list of them.

**Latency**: 2.677s locally, 2.315s deployed.

## The deployment that worked

`direct_code_deploy` — zips the source to S3 and creates the runtime. No Docker, no
CodeBuild, nothing for Vocareum's cost-control rules to stop.

```bash
agentcore configure \
  --entrypoint lab_1/starter.py \
  --name WanderBot3 \
  --requirements-file lab_1/requirements.txt \
  --region us-east-1 \
  --deployment-type direct_code_deploy \
  --disable-memory

agentcore deploy
agentcore invoke '{"message": "What is 3,247 multiplied by 891?"}'
```

Result: `arn:aws:bedrock-agentcore:us-east-1:484086766087:runtime/WanderBot3-MceMqz5L8c`,
Python 3.12 (the menu offers 3.10–3.13 and defaults to 3.12).

**What `uv` is for.** Runtime is arm64-only, so dependencies must be built for a
platform you are not on. `uv` cross-compiles them: _"Building dependencies for Linux
ARM64 Runtime (manylinux2014_aarch64)"_, then zips and caches the result — 54.76 MB
here. That is why the toolkit refuses to work without it.

**The standing cost is the artifact, not the agent.** An idle runtime bills nothing;
the 54.76 MB zip in S3 does. Container deployments pay ECR storage instead.

**Observability is partly denied in the lab account, harmlessly.**
`application-signals:StartDiscovery` is not permitted for `voclabs`, so Transaction
Search is skipped and X-Ray trace delivery then fails validation because it depends
on it. Deployment continues and CloudWatch logs work, which is all that was needed.

## ❌ The route the course teaches, and why it fails here

```
❌ Build failed during COMPLETED phase
❌ CodeBuild failed with status: STOPPED
```

**Vocareum terminates CodeBuild builds in the lab account.** Not fixable from
inside, and nothing to do with the agent code.

`STOPPED` is the whole clue: CodeBuild sets that status **only** when the
`StopBuild` API is called. An internal provisioning failure produces `FAILED` with a
context message. This produced neither.

| Observation | Source |
| --- | --- |
| `PROVISIONING` phase status `STOPPED` at 1–4s; `COMPLETED` never ran | `codebuild batch-get-builds` |
| Every phase `contexts` field null — no reason logged | same |
| Log streams created but `storedBytes: 0` — no build command ever ran | `logs describe-log-streams` |
| Reproduced **4×** across 3 agents, freshly created roles each time, and from two different machines, OSes and architectures | four `agentcore deploy` runs |
| EventBridge rule `voc-codebuild-cw-rule`, enabled, matching all CodeBuild state changes | `events list-rules` |
| Siblings `voc-ec2-cw-rule`, `voc-rds-cw-rule`, `voc-redshiftapi-cw-rule` — a cost-control family over hourly-billed services | same |
| Reading that rule's targets is an **explicit deny** in Vocareum's SCP `p-3zsdtilq` from org master `401209005059` | `events list-targets-by-rule` |
| `cloudtrail:LookupEvents` unavailable, so the `StopBuild` caller cannot be named | `cloudtrail lookup-events` |

Ruled out conclusively: the agent code, the generated Dockerfile,
`requirements.txt`, the IAM roles, and the compute type —
`BUILD_GENERAL1_MEDIUM` on `ARM_CONTAINER` is a documented, valid pairing.

The one unprovable link is that this rule's hidden target calls `StopBuild`. Every
other step is confirmed. Worth reporting to Udacity.

`--local-build` is the other route past it — Docker builds the arm64 image locally
and pushes to ECR — but it needs the Docker daemon running, and direct code deploy
got there first with fewer moving parts.

## Traps worth remembering

- **`agentcore invoke` suggestions do not match this code.** The CLI proposes
  `"Hello"` and `'{"prompt": "Hello"}'`; the entrypoint reads `message`. Both
  silently return the `payload.get` default instead of erroring. Confirmed live: the
  log showed `User: Hello!` — the fallback — for an input of `Hello`.
- **`calculator` is deprecated** in `strands-agents-tools` 0.8.6 and becomes an error
  log at v0.9.0. The suggested replacement, `strands.vended_tools.bash`, is *not*
  like-for-like: calculator evaluated expressions against an AST allowlist, bash
  executes arbitrary commands.
- **`BedrockModel` is keyword-only.** `BedrockModel(MODEL_ID)` raises `TypeError` on
  strands-agents 1.53. The course's own file used the positional form and worked on
  the VM's older release.
- **Strands ignores your profile's region.** Unset, `region_name` falls back to
  `$AWS_REGION` or **us-west-2**, not the region in your AWS config.

## Outstanding

- **Step 4's system prompt** still omits Horizon's services, which the exercise asks
  for and which its own "customer support" test question is designed to expose.
- **Teardown**: agent `WanderBot3` (live runtime + 54.76 MB zip) and `WanderBot2`
  (ECR repo, CodeBuild project, two roles). Use `agentcore destroy`, not manual
  deletes — the first two teardowns took twenty-odd API calls each.
