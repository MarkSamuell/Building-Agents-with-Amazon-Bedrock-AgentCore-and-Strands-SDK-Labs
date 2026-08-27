# Project context

Labs for the course *Building Agents with Amazon Bedrock AgentCore and Strands
SDK*, course 1 of the AWS AI Agentic Engineer Nanodegree.
Last updated 2026-08-27. Module 1 worked through and written up; the labs have
moved **off the course VM** and now run locally on Mark's Mac, still against the
Vocareum lab account.

Read this first, then read `.kiro/course-notes.md` before answering anything about
the course itself -- this file is deliberately short because it loads on every
turn; the course knowledge lives in `course-notes.md` and is read on demand.

---

## 1. Where things live

| Thing | Location |
| --- | --- |
| Labs (this repo) | `~/Documents/Personal Projects/Building-Agents-with-Amazon-Bedrock-AgentCore-and-Strands-SDK-Labs` |
| Lab 1 code | `lab_1/` -- `starter.py`, `requirements.txt`, `README.md` |
| Python env | `.venv/` at the repo root, created with `uv`. Deps pinned in `lab_1/requirements.txt` |
| Course notes | `~/Documents/Study-Notes/AI/AWS AI Agentic Engineer Nanodegree/1- Building Agents with Amazon Bedrock AgentCore and Strands SDK.md` |
| Growing course knowledge | `.kiro/course-notes.md` in this directory |

The notes path is **outside the path scope of a session started here**, so a labs
session must not read it. Work on the notes belongs in a session started from
`~/Documents/Study-Notes`. The `~/Documents/Study-Notes` root is inferred from
where the `study-notes` knowledge base points; unverified from here.

## 2. How the knowledge store works

`course-notes.md` is the single growing notes file. It is the **working copy of a
Study-Notes file**: when the course finishes it moves to the notes path in section
1 and is renamed to match. So it is written for Mark to study from later, not as
agent instructions -- anything the agent needs to be told belongs in this file
instead.

It is **not** auto-loaded. It is read when relevant and is indexed in the
`personal-projects` knowledge base for search.

Rules for keeping it useful:

- **It reads as a course in itself** -- full explanations and worked examples,
  enough to relearn the topic from this file alone. Not a summary, not an index,
  not a log of what we did. No verbosity and no redundancy either: one idea per
  paragraph, stated once.
- **No project-tracking sections.** No verified-versus-claimed table, no traps
  list, no progress log, no open questions -- all tried and removed. AWS resources
  and cost go in sections 4 and 5 of *this* file instead.
- **Append one topic per course page.** The course is worked page by page and
  example by example. Do not rewrite what is already there, and do not run ahead of
  the page Mark is on.
- Split into one file per topic only if it becomes unwieldy, and update section 1
  here if that happens.

Format, matching Mark's existing Study-Notes files:

- `#` per topic in course order, **no document title and no meta sections** -- the
  file opens straight into the first topic. Motivation before mechanism, with
  headings often phrased as questions (`# Why an Agent Framework?`).
- `**Bold term**` lead-in then the explanation as prose on the same line;
  `_italics_` on the operative phrase; tables with a bold first column for
  comparisons.
- Code blocks are teaching artifacts rather than snippets: fence tagged ` Python`,
  numbered banner comments, inline comments on the non-obvious *why*, and the
  `pip install` line. `> **Note:**` for a caveat or something to try.
- **Insert Mark's own sharper questions as headings, answered more deeply than the
  course did.** This is the signature move of his existing notes and the most
  valuable part of them.
- **Diagrams: plain text inside a code fence. Never Mermaid, never images.** Only
  where the concept is structural in a way prose cannot carry -- a cycle, a
  containment, an ordering that matters. Default to a table or a sentence.

## 3. Related prior work in this tree

`../Customer-Support-Chatbot-with-Amazon-Bedrock-Flows/.kiro/` covers the same
service family and is in scope from here:

- `agentcore-api-reference.md` -- verified AgentCore API shapes and traps
- `context.md` -- how that project is put together, and what went wrong
- `cost_report.md` -- what the AgentCore work actually cost

Check `agentcore-api-reference.md` before deriving an AgentCore API shape from
scratch.

## 4. AWS

Two accounts are in play, and which one is in use decides who pays.

**Vocareum lab account `484086766087`** -- both the course VM and the local
`udacity-agentic-ai-profile2` authenticate as `assumed-role/voclabs` using temporary
STS credentials. Anything deployed against it bills to Vocareum's budget, not
Mark's. Those credentials expire: when they do, calls fail with `ExpiredToken`, and
the session token must be refreshed from the classroom and re-applied -- in
`~/.aws-personal/credentials` for local work. Adding credentials is always Mark's
action.

**CodeBuild is dead in the lab account -- do not re-diagnose this.**
`agentcore deploy` fails every time with CodeBuild status `STOPPED` 1-4 seconds
into `PROVISIONING`, no context message, zero bytes of build log. Confirmed three
times across separate projects with freshly created roles, so it is nothing to do
with the agent code, the Dockerfile or IAM. Cause: the account carries an
EventBridge rule `voc-codebuild-cw-rule` matching
`{"source":["aws.codebuild"],"detail-type":["CodeBuild Build State Change"]}`,
one of a family of `voc-*` cost-control rules also watching EC2, RDS and Redshift.
Its targets cannot be read -- `events:ListTargetsByRule` is an **explicit deny** in
Vocareum's SCP `p-3zsdtilq` from org master `401209005059` -- so the policing
mechanism is deliberately hidden. `cloudtrail:LookupEvents` is also unavailable.
Unfixable from inside; escalate to Udacity if a working container deploy is needed.

**Work now happens on Mark's Mac, not the VM**, still against the lab account. The
Mac is strictly better suited: `arm64` native (Runtime accepts only `linux/arm64`;
the VM was `amd64`), Python 3.12.12, with `uv` and `docker` already installed.
`node` is 18.20.2, too old for the Node CLI, which needs 20+.

| Route | State |
| --- | --- |
| `python lab_1/starter.py` then curl `localhost:8080` | Works. Cheapest loop, needs only the venv |
| `agentcore dev` | Works. Uvicorn + StatReload on `0.0.0.0:8080`. Needs `uv`, not Docker |
| `agentcore deploy` (CodeBuild) | Permanently blocked, see above |
| `agentcore deploy --local-build` | **Now viable on the Mac** -- Docker present and arm64 native, so it builds locally and pushes to ECR without touching CodeBuild |
| `agentcore configure --deployment-type direct_code_deploy` | **Untested, most promising.** Zips to S3; no Docker, no CodeBuild. Caveat: `--runtime` advertises `PYTHON_3_10`/`PYTHON_3_11` while local Python is 3.12 |

**Credentials for the `agentcore` CLI.** It has **no `--profile` option** -- verified
against the full `configure` and `deploy` help -- and just uses the boto3 chain.
This session's environment already points `AWS_CONFIG_FILE` and
`AWS_SHARED_CREDENTIALS_FILE` at `~/.aws-personal/` with no profile name set, so
whatever is `[default]` there is what the CLI uses. Making
`udacity-agentic-ai-profile2` that default is the entire fix: one setting covers the
CLI, boto3 inside the agent, and `use_aws`. **Trap:** run `agentcore` from a terminal
not launched via `kiro-personal` and those two variables are unset, so it reads
`~/.aws/` -- the employer store -- instead.

**`agentcore destroy` exists.** Use it to tear down a deployed agent rather than the
twenty-odd manual delete calls the first two teardowns took.

**Mark's personal account** -- reachable only from a session on his own machine
through `~/.aws-personal/`. His own money, so state the cost and get confirmation
before creating any billable resource, and record every long-lived resource in
section 5 so a later session knows to tear it down.

## 5. Live AWS resources

| Resource | Region | Created | Standing cost | Torn down? |
| --- | --- | --- | --- | --- |
| All deploy scaffolding in **Vocareum account 484086766087**, across agents `WanderBot`, `Solu` and `solution`: ECR repos `bedrock-agentcore-<agent>`, CodeBuild projects `bedrock-agentcore-<agent>-builder`, IAM roles `AmazonBedrockAgentCoreSDK{Runtime,CodeBuild}-us-east-1-<hash>` (hash is derived from the agent name, so redeploying the same name regenerates identical names), S3 bucket `bedrock-agentcore-codebuild-sources-<account>-<region>`, and CodeBuild log groups. **No agent runtime was ever created**, since every build was stopped | us-east-1 | 2026-08-24 to 08-25 | None to Mark -- lab account paid | **Yes, fully, 2026-08-27.** Verified empty across runtimes, ECR, CodeBuild, logs, S3 and IAM. Note: `.bedrock_agentcore.yaml` in the VM still names deleted ECR repos and role ARNs, so a later `agentcore deploy` there would reuse dead references -- re-run `agentcore configure` first |

**Direct Code Deploy works, and is the only route that ever has.** On 2026-08-27 19:18 `agentcore configure --deployment-type direct_code_deploy` + plain `agentcore deploy` produced the project's **first live agent runtime**:
`arn:aws:bedrock-agentcore:us-east-1:484086766087:runtime/WanderBot3-MceMqz5L8c`, Python 3.12 (the menu offers 3.10-3.13 and defaults to 3.12). It touches neither CodeBuild nor Docker, so nothing for `voc-codebuild-cw-rule` to stop. `uv` cross-compiles the dependencies for `manylinux2014_aarch64`, zips them, and caches them for later deploys; the package came to 54.76 MB in
`s3://bedrock-agentcore-codebuild-sources-484086766087-us-east-1/WanderBot3/deployment.zip`. Extra IAM role `AmazonBedrockAgentCoreSDKRuntime-us-east-1-e0238e14b6` with policy `BedrockAgentCoreRuntimeExecutionPolicy-WanderBot3`. Logs land in `/aws/bedrock-agentcore/runtimes/WanderBot3-MceMqz5L8c-DEFAULT`.

**Observability is partly blocked in the lab account, harmlessly.** `application-signals:StartDiscovery` is denied for `voclabs`, so Transaction Search is skipped, and X-Ray trace delivery then fails validation because it needs that first. Deployment continues and CloudWatch **logs do work**. Not worth chasing.

**Live again as of 2026-08-27 19:09**, from a local `agentcore deploy` for agent `WanderBot2`: ECR repo `bedrock-agentcore-wanderbot2`, IAM roles `AmazonBedrockAgentCoreSDK{Runtime,CodeBuild}-us-east-1-4b11d1ddfa` with policies `BedrockAgentCoreRuntimeExecutionPolicy-WanderBot2` and `CodeBuildExecutionPolicy`, S3 bucket `bedrock-agentcore-codebuild-sources-484086766087-us-east-1`, CodeBuild project `bedrock-agentcore-wanderbot2-builder`. The build was `STOPPED` again, so still no runtime and no ECR image. **Tear down with `agentcore destroy`, not by hand.**

**The CodeBuild block is now confirmed account-level, not inferred.** The fourth `STOPPED` came from Mark's Mac -- different machine, OS and architecture, fresh roles, new agent name -- with the identical 1-4 second `PROVISIONING` failure. Nothing about the course VM was ever implicated.

**What the whole experiment actually cost: $0.0612**, measured via Cost Explorer, and paid by Vocareum. Breakdown: CodeBuild $0.0560, Bedrock $0.0039, CloudWatch $0.0012, S3 $0.0001, CloudWatch Events $0.00002. **CodeBuild was 92% of it despite every build being killed within 1-4 seconds** -- builds bill in rounded-up minutes, so a build stopped at two seconds costs the same as one that ran for a minute. ECR never appeared as a line item at all, confirming no image was ever pushed.

## 6. Status

| Item | State |
| --- | --- |
| Git repo | Initialised 2026-08-24, branch `main`, root commit `3d1a46a`. No remote -- pushing is Mark's action. **Everything since the root commit is uncommitted** |
| Environment | `.venv` at repo root via `uv`: `bedrock-agentcore` 1.22.0, `bedrock-agentcore-starter-toolkit` 0.3.12, `strands-agents` 1.53.0, `strands-agents-tools` 0.8.6, pinned in `lab_1/requirements.txt` |
| `lab_1/starter.py` | Imports cleanly, verified. Uses `BedrockModel(model_id=..., region_name="us-east-1")` -- keyword-only is mandatory on strands-agents 1.53, though the VM's older release accepted `model_id` positionally, which is why the course's own file ran there and fails here. **The system prompt still omits Horizon's services**, which exercise Step 4 asks for and which the "customer support" test question is designed to expose |
| `lab_1/` contents | `starter.py`, `requirements.txt`, `README.md`. **`solution.py` was never copied off the VM**, so there is no reference implementation to diff against |
| Tool use | **Proven 2026-08-27.** `python lab_1/starter.py` + curl asked for 3,247 x 891 and got the correct 2,893,077; the decisive evidence is the `strands_tools.calculator` deprecation warning in the server log, which only the tool executing can emit. `/ping` returned `{"status":"Healthy","time_of_last_update":...}`; invocation took 2.677s |
| Local AWS connection | **Verified 2026-08-27.** `[default]` in `~/.aws-personal/` resolves to `assumed-role/voclabs` in 484086766087; `udacity-agentic-ai-profile2` was removed so there is one canonical credential block. `us.amazon.nova-2-lite-v1:0` is `ACTIVE` in us-east-1 and invocable. **Docker client 29.2.0 is installed but the daemon is not running**, so `--local-build` is blocked until Docker Desktop is started |
| `course-notes.md` | Module 1 complete, plus lesson 2 `Anatomy of a Custom Tool`. Fact-checked end to end on 2026-08-25 against the Strands reference and AWS docs; five factual errors corrected. Migrates to Study-Notes at course end |
| Immediate next steps | 1. Write the Step 4 system prompt. 2. Start Docker Desktop. 3. `agentcore configure --deployment-type container`, then `agentcore deploy --local-build`. 4. Commit |
