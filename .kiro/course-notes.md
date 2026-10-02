> Working copy of a Study-Notes file. Moves to `AI/AWS AI Agentic Engineer Nanodegree/1- Building Agents with Amazon Bedrock AgentCore and Strands SDK.md` when the course finishes.

# What Is AgentCore?

Not one service. AgentCore is a **family of managed pieces for running agents**, and you opt into each one separately. That matters because the name gets used as though it were a single product, which makes the whole thing look larger and more entangled than it is. Most agents use two or three of these and ignore the rest.

| Service | What it does | How you reach it |
| --- | --- | --- |
| **AgentCore Runtime** | Hosts your agent: an HTTPS endpoint, per-session isolation, runs up to 8 hours | `agentcore deploy`; `CreateAgentRuntime` / `InvokeAgentRuntime` |
| **AgentCore Memory** | Managed conversation store — short-term within a session, long-term across them | `agentcore memory` |
| **AgentCore Gateway** | Turns existing APIs and Lambda functions into MCP tools an agent can call | `agentcore gateway`, `agentcore create_mcp_gateway` |
| **AgentCore Identity** | Credential providers, so an agent can act as a user against third-party services | `agentcore identity` |
| **AgentCore Observability** | Traces, spans and metrics for agent behaviour, over OpenTelemetry | `agentcore obs`; injected by `opentelemetry-instrument` |
| **AgentCore Code Interpreter** | Sandboxed code execution so an agent can compute, plot and analyse data | system ARN `aws.codeinterpreter.v1`, or a custom one |
| **AgentCore Browser** | A managed headless browser an agent can drive | attached as tool type `agentcore_browser` |
| **AgentCore Policy** | Fine-grained rules over what an agent and its tools may do | `agentcore policy` |
| **AgentCore Evaluations** | Built-in and custom evaluators for measuring agent quality | `agentcore eval` |
| **AgentCore Harness** | AWS runs the agent loop _for_ you — the alternative to bringing your own framework | `CreateHarness` / `InvokeHarness` |

**Harness is the odd one out and worth understanding early.** Everywhere else you write the loop (or Strands writes it) and AgentCore hosts the result. With Harness you hand AWS a model, a system prompt and a list of tools, and _it_ runs the loop server-side. Two different philosophies: bring-your-own-framework versus managed orchestration. These notes follow the first.

> **Note:** one object, three vocabularies. The thing you deploy is an **agent** in the console (`/bedrock-agentcore/agents/<id>`), an **agent runtime** in the API and CLI (`list-agent-runtimes`, `agentRuntimeArn`), and just an **agent** in the toolkit's own output. Worth knowing when searching documentation, because the three sets of results barely overlap.

## What the infrastructure actually is

Every session gets a **dedicated microVM** with its own CPU, memory and filesystem, destroyed and memory-sanitised when the session ends, and able to live for up to 8 hours. That is the isolation boundary: code running for one caller cannot reach another's session, and nothing survives the session unless you deliberately store it.

One thing Runtime does **not** do: it does not map sessions to users. Session isolation is real, but remembering which person owns which session id is your backend's job.

Everything runs on `linux/arm64`. That single constraint explains more of the tooling than anything else — why builds happen remotely or need `uv`, and why an x86 laptop is at a disadvantage.

With the platform sketched, the rest of these notes work bottom-up: the deployment choices, then what an agent is, then how to wrap one, then how to ship it.

# What AgentCore Writes On Your Disk

`agentcore configure` produces local files, and reading them is the fastest way to understand what a deployment actually is.

```
.bedrock_agentcore.yaml              one file, every agent you have configured
.bedrock_agentcore/
    WanderBot2/
        Dockerfile                   container deployments only
    WanderBot3/
        dependencies.hash            direct-code deployments only
        dependencies.zip             direct-code deployments only
```

## `.bedrock_agentcore.yaml` — the project's memory

Holds a `default_agent` plus a block per agent, which is why `agentcore deploy` and `agentcore invoke` need no arguments. Configuring a second agent silently repoints `default_agent` at it.

The fields worth knowing:

| Field | Why it matters |
| --- | --- |
| `entrypoint`, `source_path` | **absolute paths** — the file is not portable between machines |
| `deployment_type` | `container` or `direct_code_deploy` |
| `runtime_type` | `PYTHON_3_12` etc. for direct code; `null` for container |
| `platform` | `linux/arm64` for both types |
| `ecr_repository` / `s3_path` | one is set and the other `null`, according to deployment type |
| `bedrock_agentcore.agent_arn` | **`null` until a deploy succeeds.** This is how `invoke` finds your agent |
| `protocol_configuration` | `HTTP` by default; also `MCP`, `A2A`, `AGUI` |
| `memory.mode` | `NO_MEMORY` when skipped |
| `lifecycle_configuration` | `null` means the defaults — 900s idle, 28800s max lifetime |

> **Note:** it is not an inventory of what exists in AWS. A container deploy that dies mid-build still leaves a real CodeBuild project behind while the `codebuild:` block stays `null`. Trusting this file to tell you what to clean up will leave resources running — enumerate AWS itself, or use `agentcore destroy`.

## The generated Dockerfile — what a container deployment really is

You never write it, and it answers several questions at once:

``` Dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim   # even the container path is uv-based
ENV AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1   # region baked into the image

COPY requirements.txt requirements.txt
RUN uv pip install -r requirements.txt               # THIS is why a missing entry breaks a deploy
RUN uv pip install aws-opentelemetry-distro==0.12.2  # observability arrives as a dependency

RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore                               # runs non-root

EXPOSE 8080                                          # the contract port
COPY . .
CMD ["opentelemetry-instrument", "python", "-m", "starter"]
```

Three things fall out of that `CMD`.

**The `__main__` guard really does run in production.** `python -m starter` executes the module as `__main__`, so `app.run()` fires inside Runtime. It is not merely a local-testing convenience.

**Your entrypoint becomes a Python module name.** `-m starter` means the file must be importable as a module — which is why a source directory containing spaces breaks a deployment before anything else does.

**Observability is a wrapper, not code you write.** `opentelemetry-instrument` wraps your process and instruments it; that is the entire mechanism.

The baked-in `AWS_REGION` also quietly fixes something: Strands falls back to `$AWS_REGION` when `region_name` is unset, so a container deployment gets the right region even if the code never says so. Run the same code locally without that variable and it would reach for us-west-2 instead.

## `dependencies.hash` and `dependencies.zip`

Direct-code deployments only. The `.zip` is your dependencies cross-compiled for `manylinux2014_aarch64`; the `.hash` is a single SHA-256 of the inputs, used as a cache key. First deploy logs "No cached dependencies found, will build" and then "Dependencies cached"; later deploys reuse the zip unless the hash changes. `--force-rebuild-deps` overrides it.

Worth knowing the size: for four dependencies the zip came to **54.76 MB**, and that artifact in S3 — not the idle runtime — is the standing cost of a direct-code deployment.

# Who Is Allowed To Do What

The course hands you `--execution-role` and moves on, which hides the fact that **four different identities** are involved in getting an agent running. Confusing them is the source of most AgentCore permission errors, because each fails at a different moment and with a different message.

| Identity | Who it is | What it needs | When it fails |
| --- | --- | --- | --- |
| **The deployer** | you, or your CI | create IAM roles, ECR repos, S3 buckets, CodeBuild projects; `CreateAgentRuntime`; `iam:PassRole` | at `deploy`, before anything runs |
| **The execution role** | assumed by the agent while it runs | `bedrock:InvokeModel`, CloudWatch Logs, plus whatever its tools touch | at first invocation, inside the agent |
| **The CodeBuild service role** | assumed by CodeBuild to build the image | ECR push, S3 read, logs | mid-build, container deployments only |
| **The caller** | whoever invokes the deployed agent | `bedrock-agentcore:InvokeAgentRuntime` | at `invoke`, from outside |

The toolkit creates the middle two for you and names them predictably: `AmazonBedrockAgentCoreSDKRuntime-<region>-<hash>` and `AmazonBedrockAgentCoreSDKCodeBuild-<region>-<hash>`. The hash is derived from the agent name, so deleting a role and redeploying the same agent regenerates an identically named one.

## The trust policy, and why it carries conditions

An execution role is useless unless the service is allowed to assume it. The documented policy:

``` json
{
  "Effect": "Allow",
  "Principal": { "Service": "bedrock-agentcore.amazonaws.com" },
  "Action": "sts:AssumeRole",
  "Condition": {
    "StringEquals": { "aws:SourceAccount": "123456789012" },
    "ArnLike": { "aws:SourceArn": "arn:aws:bedrock-agentcore:us-east-1:123456789012:*" }
  }
}
```

The two conditions are **confused-deputy protection**, and they are the part people delete when "it doesn't work". Without them, the AgentCore service principal could be induced to assume your role on behalf of _someone else's_ account — a stranger creates a runtime, names your role, and the service dutifully assumes it. `aws:SourceAccount` and `aws:SourceArn` bind the assumption to resources in your own account.

## Why the role names matter more than they look

AWS's managed policy for AgentCore grants `iam:PassRole` **only for roles whose name matches `*BedrockAgentCore*`**. So the toolkit's verbose naming is not cosmetic — it is what makes the managed policy work at all. Rename a role to something tidier and `PassRole` silently stops applying to it.

Two further gaps in that managed policy are worth knowing:

- **`iam:CreateRole` is not included.** Auto-creating an execution role needs a permission the managed policy does not grant, which is why "let the toolkit create one" fails in tightly scoped accounts.
- **`GetWorkloadAccessTokenForUserId` is included, and shouldn't be in production.** It issues workload tokens from a caller-supplied user-id string _without verifying any identity provider token_. The production form is `GetWorkloadAccessTokenForJWT`, which validates signature, issuer and expiry; AWS suggests explicitly denying the UserId variant once your workloads always carry a JWT.

## What the execution role actually needs

At minimum: model invocation and logs. The model half is the fiddly part and is covered under _The model id is not a model id_ below — two ARN forms, two actions, and model access enabled in every destination region.

Beyond that, the role needs whatever its **tools** need, and this is where least privilege earns its keep: a tool that reads S3 means the agent can read S3, for the whole session, whatever the model decides to ask for.

If AgentCore Memory is enabled, the role also needs event and record actions on the memory resource. It surfaces as an `AccessDeniedException` on `bedrock-agentcore:ListEvents` at the _first_ invocation, before the model is ever called — because memory is read at the start of a turn, not written at the end. Observed rather than documented.

## Two invoke actions, and an escalation trap

Callers need `bedrock-agentcore:InvokeAgentRuntime`. There is a second action, `InvokeAgentRuntimeForUser`, which invokes on behalf of an end user via the `X-Amzn-Bedrock-AgentCore-Runtime-User-Id` header — powerful, and worth denying explicitly where it isn't needed.

The subtler rule, from AWS's own security guidance: **the execution role should have equal or fewer privileges than the principals allowed to invoke the agent.** Otherwise invoking the agent _is_ a privilege escalation — a caller who can't read a bucket directly simply asks an agent whose role can.

> **Note:** AWS is blunt about the roles the toolkit generates: _"Do not use CLI-generated policies in production — the IAM policies created by the AgentCore CLI are designed for development and testing purposes. These permissions grant broad access and are not suitable for production."_ Anything created by pressing Enter at the `configure` prompts falls in that category.

# Deployment Options

"How do I deploy an agent" is really **four independent questions**, and the tooling conflates them badly enough that the choices look like more work than they are:

1. What **artifact** does Runtime receive — an image, or a zip?
2. Where does that artifact get **built** — in the cloud, or on your machine?
3. Where does it **run** — Runtime, or locally?
4. What **compute type** runs it — serverless microVMs, or dedicated instances?

Only the first is a real architectural decision. The rest follow from it, or from what your laptop happens to have installed.

## 1. The artifact: container or direct code

| | **Container** | **Direct code** |
| --- | --- | --- |
| What Runtime gets | an ARM64 OCI image | a zip of source plus dependencies |
| Built from | a Dockerfile the toolkit generates for you | `uv`, cross-compiling wheels for `manylinux2014_aarch64` |
| Stored in | **ECR** | **S3** |
| Config records | `ecr_repository`; `runtime_type: null` | `s3_path`; `runtime_type: PYTHON_3_12` |
| Language | anything you can put in an image | **Python only** |
| Iteration | slower — every change is an image build and push | faster; dependencies are cached by hash and reused |
| Standing cost | ECR image storage | S3 Standard on the zip |

The generated Dockerfile is worth reading once — it is covered under _What AgentCore Writes On Your Disk_ — because it shows that even the container path is `uv`-based underneath, and that observability arrives as a wrapped `CMD` rather than anything you write.

**Direct code is not "container, but worse".** It is a genuinely different contract: you hand over source and a Python version, and AWS supplies the runtime image. That is why it needs `--runtime PYTHON_3_10` through `PYTHON_3_13`, and why the container path has no equivalent flag — with a container, *you* are the one who chose the interpreter.

## 2. Where it builds and runs: three modes

`agentcore deploy` has three modes, and which are available depends on the artifact type:

| Mode | Container | Direct code |
| --- | --- | --- |
| **default**, no flags | CodeBuild builds the ARM64 image in the cloud. No local Docker needed | zips and uploads; nothing to build remotely |
| **`--local`** | builds *and runs* the container on your machine. Needs Docker, Finch or Podman | runs the script locally with `uv`. Not a deployment — this is development |
| **`--local-build`** | Docker builds the image locally, then it deploys to cloud Runtime | **not supported** |

Two things fall out of that table. `--local-build` exists for exactly one situation: you want a cloud deployment but need control over the build, or cloud building is unavailable to you. And `--local` is not a deployment at all in either column — it is the same idea as `agentcore dev`, minus the hot reload.

The arm64 constraint decides a lot here. Building an ARM image on an x86 machine needs QEMU emulation and is slow; on Apple Silicon it is native. Handing the build to CodeBuild sidesteps the question entirely, which is why it is the default.

## 3. Compute type: the cost axis

Independent of everything above, Runtime runs your agent on one of two compute types:

| | **microVM** (default) | **Instances** |
| --- | --- | --- |
| What it is | serverless, one microVM per session | AWS-managed EC2 |
| Billing | per second, on actual CPU and peak memory consumed | EC2 instance cost plus a management fee |
| Idle cost | **none** | charged while idle |
| Suits | almost everything | persistent or resource-heavy workloads |

Two consequences. An agent sitting deployed and uncalled costs nothing on microVMs, so there is no reason to tear one down to save money — only its stored artifact accrues. And since agents spend most of their life waiting on models and tools, being billed only for CPU actually burned is a large saving rather than a rounding error.

## 4. What protocol it speaks

A last axis, easy to miss: `--protocol` accepts `HTTP`, `MCP`, `A2A` and `AGUI`. Runtime will host an MCP server or an agent-to-agent endpoint as readily as an HTTP agent — the container contract differs, but the deployment machinery is identical. Everything in these notes uses `HTTP`.

## So which one?

The deciding question is short: **does your agent need anything that is not a Python package?**

| Situation | Choice |
| --- | --- |
| Pure Python agent, want the fastest loop | **Direct code, default mode.** Fewest moving parts; no Docker anywhere |
| Needs system packages, a compiled binary, a non-Python runtime, or a specific base image | **Container, default mode.** CodeBuild builds it; you still need no local Docker |
| Container needed, but you must control the build — or cloud build is blocked or unavailable | **Container, `--local-build`.** Requires Docker; painless on arm64, slow under emulation |
| Just iterating on prompts and tool wiring | **Neither.** `agentcore dev`, or plain `python <file>.py` |
| Long-running, resource-hungry, or needs warm state | Either artifact, on the **Instances** compute type, accepting idle billing |
| You would rather not write or deploy an agent at all | **AgentCore Harness** — hand AWS a model, a prompt and tools, and it runs the loop |

> **Note:** the two artifact types are not a one-way door, but switching is not free either. The deployment type is recorded per agent in `.bedrock_agentcore.yaml` along with type-specific fields, so reconfiguring an existing agent from container to direct code leaves a stale `ecr_repository` behind. Cleaner to configure a fresh agent name and delete the old one.

# Why an Agent Framework?

A foundation model does one thing: it takes a prompt and returns a completion. It cannot look anything up, cannot reliably do arithmetic, and cannot act on the world. Modern models accept more than text — Nova 2 Lite takes image and video input too — but the shape is unchanged: something goes in, text comes out, and nothing happens. Everything interesting that an "AI agent" appears to do comes from code _around_ the model, not from the model itself.

**The manual alternative** Without a framework you write that surrounding code yourself, and it is always the same code: describe your functions to the model, read the reply to work out _which_ function it wants and with what arguments, validate those arguments, call the function, format the result, append it to the conversation, and call the model again — repeating until the model stops asking. The loop is mechanical, and it fails silently in exactly the places that matter, such as a schema the model misreads or a tool result appended in the wrong shape.

**What Strands supplies** The loop itself, tool schemas generated automatically from your Python function signatures and docstrings, conversation state across turns, and adapters so the same agent runs against a different model provider unchanged.

## Why not just write the loop myself?

You can, and the happy path is short. The reason not to is that _the loop is not where the difficulty lives_. The difficulty is in tool-schema generation that the model actually understands, streaming partial responses, retries when a tool throws, capping runaway tool-calling, and keeping conversation state correct when a tool result arrives out of order. A framework is worth it for the second-order concerns, not the first-order one.

# The Three Layers

The course introduction names Bedrock, Strands and AgentCore Runtime in one sentence, which makes them look like three stages of one pipeline. They are not. They are three _independent_ layers, and knowing which does what prevents most of the confusion later.

| Layer | What it is | Alone, without the others |
| --- | --- | --- |
| **Amazon Bedrock** | An inference API. Messages in, completion out, _stateless_. It does accept tool specifications and can reply _asking_ for one — but it never executes anything and never loops. | Perfectly usable on its own via `Converse` or `InvokeModel`. |
| **Strands Agents SDK** | A library running _inside your own process_ that drives the agent loop and the tool plumbing. | A local Python script is already a complete, working agent. Needs no AWS hosting at all. |
| **AgentCore Runtime** | _Managed hosting_ — an HTTPS endpoint, per-session isolation, identity, observability, and runs of up to 8 hours. | Framework-agnostic. AWS names LangGraph, CrewAI and Strands; plain Python works too. |

The layering is a _containment_. The agent and its tools live in your own process; that process is optionally wrapped by AgentCore Runtime; Bedrock is a remote API called outwards from inside. So removing the outer wrapper leaves a working local script, swapping Bedrock for OpenAI changes nothing inside, and swapping Strands for LangGraph changes nothing outside.

Two details about Runtime's isolation are worth knowing early. Each session gets a **dedicated microVM** with its own CPU, memory and filesystem, terminated and memory-sanitised when the session ends — and billing is consumption-based, charging only during active processing rather than while your agent waits on a model or a tool. But **Runtime does not enforce session-to-user mapping**: keeping track of which user owns which session id is your backend's job, not the platform's.

# The Agent Loop

This is the single definition the course omits, and everything else hangs off it. An agent is _a loop around a model that is allowed to ask for functions to be run_.

```
    ┌──► 1. Strands sends: messages + schemas of every tool
    │              │
    │              ▼
    │       2. Model replies
    │              ├── plain text ─────────► loop ends, answer returned
    │              │
    │              └── tool-use request
    │                         │
    │                         ▼
    │       3. Strands runs the real Python function
    │                         │
    │                         ▼
    └────── 4. Result appended to the conversation
```

**1. Schemas go out with the prompt** Strands sends the model your messages _plus_ a machine-readable description of every available tool — name, description, and typed parameters. The model cannot call anything it was not told about.

**2. The model chooses** It replies with either final text, in which case the loop ends, or a _structured_ tool-use request naming one tool and its arguments. This is a first-class feature of the model API, not text parsing.

**3. The SDK executes** Strands runs the actual Python function. The model never runs anything; it only ever _asks_.

**4. The result is appended and the model is called again** The tool's output goes back into the same conversation, and round it goes. The loop ends when the model answers with text instead of another request.

Strands calls this the _model-driven approach_: the model decides which tool and when, rather than you writing an if/else flowchart over user intent.

## So what is a "tool", concretely?

A plain function, plus the schema the model reads to decide whether it wants it. The _description is not documentation_ — it is the only information the model has when choosing, so a vague description is a functional bug rather than a style problem.

## Why is the first tool always a calculator?

Not because arithmetic is interesting. Because multi-digit arithmetic is genuinely unreliable for a language model, in a way that is easy to see and impossible to argue with. It is the cheapest possible demonstration where the failure is visible before the import and gone after it. The lesson is tool-use; the arithmetic is a prop.

**Why it is unreliable is worth getting right, because the popular explanation is wrong.** Digit tokenization usually takes the blame, but the research finds the limitation persists _regardless of tokenization scheme_: models learn arithmetic as a hierarchy of symbol-to-symbol mappings rather than as an algorithm, and lean on heuristics such as a one-digit lookahead that collapse once carries cascade. The failure is architectural, not a quirk of the tokenizer — which is why a larger model does not reliably fix it and a calculator does.

> **Note:** on `strands-agents-tools` 0.8.6 `calculator` logs a deprecation warning on every call, and the suggested replacement is `from strands.vended_tools import bash`. **Do not take that advice blindly for an agent exposed to untrusted input.** The warning admits the problem itself: calculator only ever evaluated an expression checked against an _AST allowlist_, whereas bash executes arbitrary commands. Swapping one for the other to silence a warning trades a sandboxed evaluator for a shell — in a component whose arguments are chosen by a language model reacting to whatever a stranger typed into a chat box. The deprecation becomes an error log in v0.9.0, so it needs a decision eventually, but "use bash instead" is a materially wider security boundary and not a like-for-like swap.

## The minimal agent

``` Python
# =====================================================
# MINIMAL STRANDS AGENT - this is the whole thing
# =====================================================
# pip install strands-agents strands-agents-tools

# 1. IMPORTS
from strands import Agent                   # the loop
from strands.models import BedrockModel     # adapter to Amazon Bedrock
from strands_tools import calculator        # a ready-made tool

# 2. THE MODEL
# BedrockModel is only an adapter, and Bedrock is merely the default
# provider. Swapping this line for OpenAIModel is the only change needed
# to run the same agent elsewhere.
model = BedrockModel()                      # region and credentials come from the environment

# 3. THE AGENT
# tools= is the entire wiring. Strands reads each tool's name, docstring
# and type hints, turns them into a JSON schema, and ships that schema
# with every request to the model.
agent = Agent(
    model=model,
    tools=[calculator],                     # delete this line and the sum comes back wrong
)

# 4. RUN
# Calling the agent starts the loop and blocks until the model stops
# asking for tools. The return value is the final assistant message.
print(agent("What is 3,247 * 891?"))
```

> **Note:** run this twice, once with `tools=[calculator]` and once with `tools=[]`. Seeing the wrong answer appear is the point of the exercise; it is the only part of tool-use that is hard to believe without watching it.

# Why Wrap the Agent in an App?

The agent from the previous topic works, but nothing can _call_ it. It is a script: it runs once, prints, and exits. To be a service it needs to sit behind an HTTP endpoint, and AgentCore Runtime will only route traffic to a container that speaks a specific contract.

**What the contract requires** Two endpoints on port `8080`, in an ARM64 container.

| Endpoint | Method | What it must do |
| --- | --- | --- |
| **`/invocations`** | POST | Receive the caller's JSON body, return JSON or an SSE stream |
| **`/ping`** | GET | Report `{"status": "Healthy"}`, or `HealthyBusy` while background work is still running |

A session reporting `Healthy` is treated as idle and **terminated after 15 minutes of inactivity**; one reporting `HealthyBusy` is kept alive past that. `BedrockAgentCoreApp` answers the ping for you, which is why you never see this until you write a long-running tool.

`BedrockAgentCoreApp` implements both routes, the health reporting and the response framing. You never write them yourself — which is the whole point of the wrapper, and why it is _four lines_ rather than a web framework.

## The minimal WanderBot

``` Python
# =====================================================
# WANDERBOT v1 - a Strands agent wrapped as a service
# =====================================================
# pip install bedrock-agentcore strands-agents strands-agents-tools

# 1. IMPORTS
from bedrock_agentcore.runtime import BedrockAgentCoreApp   # the HTTP wrapper
from strands import Agent
from strands.models import BedrockModel
from strands_tools import calculator                        # built-in Strands tool

# 2. THE APP
# Building the app creates a web server that implements Runtime's contrac (the runtime container for our agent).
# Nothing is listening yet; app.run() at the bottom does that.
app = BedrockAgentCoreApp()

# 3. THE MODEL, built once at import time
# Module level on purpose: the adapter holds no conversation, so there is
# no reason to rebuild it per request.
# nova-2-lite is the course's choice, on the grounds that it is fast, cheap
# and strong at tool use -- unverified, but the shape of the argument is right:
# an agent calls the model repeatedly, so per-call latency and price compound.
MODEL_ID = "us.amazon.nova-2-lite-v1:0"    # the "us." prefix matters -- see below
model = BedrockModel(
    model_id=MODEL_ID,
    # Optional tuning knobs, both omitted here so the defaults apply:
    #   temperature=0.3   lower = more deterministic, higher = more varied
    #   max_tokens=1024   hard cap on response length
)

# 4. THE SYSTEM PROMPT
# calculator already carries its own description, and that description is
# what the model reads when choosing tools. This prompt biases the choice
# for the cases WanderBot cares about: tool selection is probabilistic, so
# naming the situations explicitly makes it markedly more reliable.
SYSTEM_PROMPT = """You are WanderBot, the AI travel assistant for Horizon Travel.
When asked to calculate costs, tips, totals, durations, or percentages,
use the calculator tool. Keep answers friendly, concise, travel-focused."""


# 5. THE ENTRYPOINT
# The decorator registers this function as the handler for POST /invocations.
# payload is the caller's JSON body, already parsed to a dict.
# context carries per-request metadata such as context.session_id. It defaults
# to None so the function can still be called directly from a test.
@app.entrypoint
async def invoke(payload: dict, context=None):
    # If payload contains "message", user_message gets that value. 
    # If it does not contain "message", user_message becomes Hello!
    user_message = payload.get("message", "Hello!")

    # Built here, inside the handler, rather than at module level -- see below.
    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[calculator],
    )
    return agent(user_message)


# 6. START THE SERVER
# Not merely a local-testing convenience: the container built at deploy time
# runs this file as a script, so __main__ is true in production too. This is
# the line that actually starts serving inside AgentCore Runtime.
if __name__ == "__main__":
    app.run()                              # listens on port 8080
```

Ask WanderBot _"A flight costs $349. Hotel is $145/night for 4 nights. What's the total?"_ and it runs exactly the loop from the previous topic — the model returns a tool-use request for `calculator`, Strands executes it, the arithmetic comes back exact, and the model turns the number into a sentence. The only orchestration code in the file is the word `calculator` inside a list.

## How does `invoke` ever get called?

**Nothing in the file calls it.** That is what makes the block unreadable at first. A Python script normally runs top to bottom, and you can point at the line where each function is invoked. Here you cannot, because `invoke` is _registered_ rather than called. You hand the function over, and something else calls it later — once for every HTTP request that arrives.

**What the decorator actually does** `@app.entrypoint` is ordinary Python decorator syntax. These two are equivalent:

``` Python
@app.entrypoint
async def invoke(payload, context=None):
    ...

# ---- identical to ----

async def invoke(payload, context=None):
    ...
invoke = app.entrypoint(invoke)     # this is all the @ line means
```

So `app.entrypoint` is just a function that takes your function as its argument. It stores a reference to it inside `app`, so the web server knows which function to hand requests to, and gives it back unchanged apart from an added `serve` method. _Your function's behaviour is not modified._ The bookkeeping is the entire point.

**You have met this arrangement before** In Airflow you write `def extract_data(**context)` and never call it either. You pass it to a `PythonOperator`, and Airflow calls it later, supplying a `context` argument you never wrote. `@app.entrypoint` is the same deal in different syntax: your function, someone else's trigger, arguments you did not pass.

Following one request through, with the ownership boundary marked:

```
  POST /invocations                            <- the caller
  {"message": "What's the total?"}
           │
           ▼
  BedrockAgentCoreApp                          <- the wrapper's code
    parses the JSON body into a dict
    looks up the function registered by @app.entrypoint
           │
           ▼
  invoke(payload={"message": ...}, context=…)  <- YOUR function, called for you
    reads the message, runs the agent, returns the answer
           │
           ▼
  BedrockAgentCoreApp                          <- the wrapper's code
    serialises the return value as the HTTP response body
```

**Where `payload` and `context` come from** Both are handed in by the wrapper, which is exactly why neither appears anywhere else in the file. `payload` is the caller's JSON body, already parsed into a dict. `context` is per-request metadata from the platform, carrying things such as `context.session_id`. It defaults to `None` so that you can still call `invoke({"message": "hi"})` directly in a test, where there is no HTTP request and so no context to supply.

**Why `agent(user_message)` reads like calling a variable** Because a Strands `Agent` implements `__call__`, which makes the instance callable like a function. `agent(user_message)` runs the entire agent loop and returns its result — the same idiom as `model(x)` in PyTorch.

## Deployed fine, but every request says "no handler was found". Why?

The scenario: the agent deploys, `agentcore invoke` returns _no handler was found for the request_, the `invoke` function is definitely present, and the file runs locally without complaint. **Cause: `invoke` is missing its `@app.entrypoint` decorator.**

The clue that looks exculpatory is the one that convicts. _"The file runs locally"_ is not evidence against this bug — it is its fingerprint. Without the decorator everything succeeds right up until a request arrives: the module imports, because Python has no opinion about whether a function is decorated; `BedrockAgentCoreApp()` constructs; `app.run()` starts the server; `/ping` answers `Healthy`. You can watch it boot and see nothing wrong.

Only the bookkeeping is missing. Since `@app.entrypoint` is just `invoke = app.entrypoint(invoke)`, skipping it leaves `app`'s registry _empty_ — a healthy server, listening, with nothing bound to `/invocations`.

The reason it survives every check you would naturally run: **nothing in your own file calls `invoke`, so nothing in your own file notices it was never registered.** The decorator matters only for the code path you did not write. Import it, lint it, read it, start it — all clean. Only a real HTTP request exposes it.

Each rival explanation is ruled out because it would produce a _different_ symptom:

| Cause | What it would actually look like |
| --- | --- |
| **Missing `@app.entrypoint`** | `no handler was found` — server healthy, registry empty |
| Wrong payload key | A reply, just the wrong one: the `payload.get` default |
| No Bedrock model access, or bad IAM | `AccessDenied`, raised *after* the handler ran |
| Import missing from `requirements.txt` | Container never starts, so `/ping` fails too |
| No `app.run()` | Nothing listening at all — connection refused |

So _"no handler"_ is specifically a **routing** failure, which proves the app started cleanly: imports fine, dependencies fine, contract endpoints alive, only the binding absent.

The diagnostic that follows is one step: **curl `/ping` first.** A healthy ping with a failing `/invocations` narrows it to registration immediately. A dead ping sends you to startup and dependencies instead.

> **Note:** one other cause produces the identical symptom — `.bedrock_agentcore.yaml` naming a different entry file than the one you decorated. Same empty registry, different reason, so check which file the config actually points at before rereading your decorators.

> **Note:** the entrypoint is declared `async def`, but `agent(user_message)` is an ordinary blocking call, so nothing here is actually concurrent — the coroutine holds the event loop until the agent finishes. It works and costs nothing for one request at a time. Real streaming needs `agent.stream_async(...)` with `yield` instead.

## Who decides that the payload key is `message`?

You do. The documentation is explicit that AgentCore _"passes request payloads directly to your container without validation"_ and that _"your container implementation determines which fields are required"_. There is no platform-defined schema, which is why AWS's own examples variously use `prompt`, `query` and `transcript` for the same idea. `message` is this file's private convention, and the caller simply has to match it.

> **Note:** `payload.get("message", "Hello!")` means a caller who sends `{"prompt": "..."}` gets no error — they get WanderBot cheerfully answering "Hello!". Convenient while testing, a silent bug anywhere real. `payload["message"]` fails loudly instead, which is usually what you want. Worse, the bug hides from the obvious test: send the message `"Hello"` and the reply is indistinguishable from the fallback firing. Only a message with specific content in it can tell you the key was read at all.
>
> Observed live: `agentcore invoke --dev "Hello"` — the form the CLI itself suggests — does **not** arrive under `message`. The server logged `User: Hello!`, the default, not the `Hello` that was sent. Always pass JSON: `agentcore invoke --dev '{"message": "..."}'`.

## Why is the Agent rebuilt on every request?

For _isolation_, and it is the most consequential line in the file. A Strands `Agent` accumulates conversation in `agent.messages`, so a module-level agent would keep every exchange the container ever handled — and traveller B would see traveller A's conversation. Rebuilding per request guarantees each caller starts clean. `model` can stay at module level precisely because it holds no conversation.

The cost is that **WanderBot has no memory at all**. Every request starts from an empty history, so a follow-up like "and what about 5 nights?" arrives with nothing to refer back to. Multi-turn conversation has to be added deliberately, and there are three routes: Strands' own **session management**, which persists conversation through a pluggable backend and ships with filesystem and S3 implementations; **AgentCore Memory**, the platform's managed store; or rehydrating history from the payload yourself on every call.

## The model id is not a model id

`us.amazon.nova-2-lite-v1:0` is a _cross-region inference profile_, not a foundation model. The underlying model is `amazon.nova-2-lite-v1:0`; the prefix selects a routing geography, and the same model publishes `us.`, `eu.` and `jp.` geographic profiles plus a `global.` one that may route to any commercial region.

Two consequences surface only at deployment.

**The execution role needs two ARN forms and two actions.**

```
arn:aws:bedrock:*:<account>:inference-profile/us.amazon.nova-2-lite-v1:0
arn:aws:bedrock:*::foundation-model/amazon.nova-2-lite-v1:0
```

The inference-profile ARN _includes_ the account id. The foundation-model ARN has an **empty account segment** (`::`) because foundation models are not account-scoped — putting an account id there produces an ARN that can never match, so every call fails. Both statements need `bedrock:InvokeModel` **and `bedrock:InvokeModelWithResponseStream`**: the second is not optional here, because Strands invokes through the streaming API even when your code looks synchronous. Granting only the non-streaming action is a common way to get a puzzling `AccessDenied` from working-looking code.

**Model access must be enabled in every destination region, not just yours.** A geographic profile dispatches across the regions in its geography, and the underlying model has to be enabled in each of them. Enabling access in your source region alone leaves the profile free to route to a region where you have none.

Granting only the profile ARN produces an authorization failure that names nothing useful, and reads at first glance as though the model does not exist.

## Two regions, and nothing links them

There are two regions in play, they mean different things, and they are set in completely different places:

| Region | What it decides | Set by |
| --- | --- | --- |
| **Where the agent is hosted** | which region holds the runtime, its execution role, its log group | `agentcore configure --region` |
| **Where Bedrock is called from** | which region serves the model | `region_name` on `BedrockModel` |

**Nothing ties one to the other.** A runtime hosted in us-east-1 will cheerfully call Bedrock in us-west-2, because Strands resolves its own region independently: `region_name` if you passed it, otherwise `$AWS_REGION`, otherwise **us-west-2** as a hardcoded fallback. It does _not_ read the region from your AWS profile, so `aws configure set region` has no effect on it whatsoever.

The mismatch surfaces as an `AccessDenied` on a model you are certain you enabled — because you enabled it in the region you were thinking about and the call went somewhere else. Passing `region_name` explicitly means the question never arises.

A container deployment hides this, which is its own hazard: the generated Dockerfile bakes in `AWS_REGION`, so the fallback lands somewhere sensible in production and the same code misbehaves only when run locally.

> **Note:** you cannot verify it by reading `model.config`. `region_name` is a constructor parameter consumed by `__init__` to build the boto client, while `config` holds only the `**model_config` fields such as `model_id`. Its absence there means nothing. The real check is `model.client.meta.region_name`.

# How Does the Agent Get to Runtime?

The file runs locally the moment you execute it. Getting it into AgentCore Runtime means putting it in a container, and that container has to be built somewhere, stored somewhere, and pointed at by a runtime resource. The starter toolkit does all of it from two commands.

**What has to travel with the code** A `requirements.txt` listing every import — `bedrock-agentcore`, `strands-agents`, `strands-agents-tools`. The container is built from your source _plus_ that list, so an import you have locally but forgot to list works perfectly on your machine and fails inside the container. This is the most common way a first deployment breaks.

## `agentcore configure` — answering the menu once

An interactive prompt that writes your answers to disk. What the course chooses:

| Prompt | Course's answer | What it means |
| --- | --- | --- |
| **Entrypoint** | `demo.py` | the file holding `app` and the decorated function |
| **Agent name** | `WanderBot` | becomes the runtime's name |
| **Dependency file** | auto-detected `requirements.txt` | confirmed rather than typed |
| **Deployment type** | **container** (option 2), and _every lesson uses this_ | see the comparison below |
| **Execution role** | let the toolkit create one | the role the agent assumes to call Bedrock |
| **ECR repository** | let the toolkit create one | where the built image lands |
| **Authentication** | default, i.e. IAM SigV4 | any principal holding `bedrock-agentcore:InvokeAgentRuntime` may call it |
| **Header allow list** | none | |
| **Memory** | skipped | consistent with the stateless agent above; memory is added in a later module |

**Two files appear that you did not write** `.bedrock_agentcore.yaml`, holding every answer above so later commands need no arguments, and a generated `Dockerfile` describing the image. Both are worth reading once — they are the only place the deployment's actual shape is written down.

## What `agentcore dev` actually runs

A local server on port 8080 speaking the same contract as Runtime, with hot reload. Its startup output says exactly what it is:

| Observed at startup | What it means |
| --- | --- |
| `Uvicorn running on http://0.0.0.0:8080` | a plain ASGI server in your own process |
| `Started reloader process using StatReload` | it watches file timestamps and restarts on change |
| `Will watch for changes in these directories: [...]` | the watched root is your source directory |
| `Found credentials in shared credentials file` | it uses your ordinary AWS credentials |
| refuses to start without `uv` | `[Errno 2] No such file or directory: 'uv'` |

**It does not run a container, despite course material saying it does.** The proof is local: `dev` runs happily in an environment that reports `No container engine found (Docker/Finch/Podman not installed)`, and the reloader watches the host filesystem directly. So it is the same _application_ and the same _HTTP contract_ as production, but _not_ the same execution environment — which means it cannot catch container-only faults: an import missing from `requirements.txt`, an arm64 incompatibility, or a broken Dockerfile.

**What `uv` is actually for** — verified from a real deploy. Runtime is arm64-only, so dependencies have to be built for a platform you are probably not on. `uv` is the cross-compiler: a direct-code deploy logs _"Building dependencies for Linux ARM64 Runtime (manylinux2014_aarch64) — installing dependencies with uv for aarch64-manylinux2014 (cross-compiling for Linux ARM64)"_, then zips and caches the result. It doubles as the local runner: `deploy --local` is documented as "run Python script locally with uv", which is why `dev` refuses to start without it.

## Iterating on the system prompt cheaply

**The constraint first: a prompt's effect cannot be observed without calling the model.** There is no offline check that tells you whether a rewording made tool selection more reliable or the tone warmer. Anything promising prompt iteration "for free" is measuring something else. What you can do is make each iteration nearly instant and nearly free.

**Hot reload removes the restart.** Edit `SYSTEM_PROMPT`, save, and StatReload restarts the app in place; the next `agentcore invoke --dev` uses the new wording. No `configure`, no rebuild, no redeploy. Iterating against a _deployed_ runtime instead means a full container build per word changed.

**In the course lab the calls are not yours to pay for.** The VM authenticates into Vocareum's account, so Bedrock charges land on their budget. Inference only becomes your cost when you point at your own account.

**When it is your account, the lever is token count.** Bedrock bills per token in and per token out. `nova-2-lite` is already at the cheap end, and `max_tokens` caps the expensive half. A prompt-tuning loop with capped output runs at fractions of a cent per iteration.

**Move the checks that don't need the model off the model path.** They cost nothing and catch the mistakes that would otherwise waste inference calls:

``` Python
print(repr(SYSTEM_PROMPT))   # repr, not print -- the quoting is the point
```

> **Note:** a triple-quoted prompt written at an indent carries leading spaces on _every line_ into _every request_, plus a leading newline. Behaviourally harmless, billable on each call, and invisible unless you use `repr()`.

## What `agentcore deploy` actually does

Four steps, none of which you drive:

```
  your source  ──►  S3 bucket
                        │
                        ▼
                  CodeBuild  builds the ARM64 image
                        │
                        ▼
                     ECR      image stored
                        │
                        ▼
              AgentCore Runtime  creates the agent, version V1
                                 and a DEFAULT endpoint
```

Building remotely rather than locally is deliberate: Runtime accepts _only_ `linux/arm64`, and building an ARM image on an x86 laptop needs emulation. Handing the build to CodeBuild sidesteps that entirely.

> **Note:** this creates real billable resources, but not the ones you would guess. **On the default microVM compute type the runtime has no standing charge** — billing is per session, at per-second increments, on actual CPU and peak memory, and CPU spent waiting on a model or a tool is free. An agent left deployed and never called costs nothing to keep. What accrues continuously is the **stored artifact**: ECR image storage for container deployment, or S3 Standard rates on the zip for direct code deployment. The exception is Runtime's other compute type, **Instances**, which bills EC2 cost plus a management fee and therefore does charge while idle. Check the pricing page for current rates.

> **Note:** CodeBuild bills in _rounded-up minutes_, which makes failed builds surprisingly expensive. Measured on a real account: five builds, every one killed 1–4 seconds in and producing zero output, still cost $0.056 — 92% of that experiment's entire bill, against $0.0039 of actual Bedrock inference. A build that dies instantly costs the same as one that ran for a minute, so a broken deploy loop is the most expensive thing here by an order of magnitude.

## Testing the deployed agent

`agentcore invoke` sends a JSON payload to the runtime, using the config file to find it. The course sends two messages deliberately: an ordinary greeting, which the model answers from its own knowledge, then an arithmetic question, which forces the calculator to fire. The second is the only proof that tool-calling survived deployment — a greeting would look identical whether or not the tool was wired up.

> **Note:** the course teaches the Python starter toolkit, whose signature is `configure` writing a `.bedrock_agentcore.yaml`. Running it now prints a deprecation notice: _"The Starter Toolkit CLI is no longer supported"_, directing you to the Node.js AgentCore CLI (`npm install -g @aws/agentcore`), which scaffolds with `create`, stores config under `agentcore/`, and is the only place new AgentCore features appear. `agentcore import` migrates existing agents. Both are invoked as `agentcore` and both have a `deploy`, so `agentcore --help` is what settles which is on your PATH.

> **Note:** a real deploy confirms the build runs in **CodeBuild**, in "codebuild mode", with no CodePipeline anywhere — the toolkit's own output says so. Course material describing a CodePipeline stage is wrong.

# Anatomy of a Custom Tool

Built-in tools proved that tool-use works, but they can only do generic things. An agent for Horizon Travel has to reach data that only Horizon has — its flights. That means writing a tool, and a custom tool is _just a Python function with a decorator_. There is no plugin interface, no registration file, no schema to hand-write.

``` Python
# =====================================================
# A CUSTOM TOOL - the whole pattern
# =====================================================
from strands import tool

@tool                                        # 1. turn the function into a tool
def search_flights(origin: str,              # 2. type hints become the input schema
                   destination: str,
                   date: str) -> str:        #    the return annotation is yours to choose
    """
    Search for available Horizon Travel flights between two airports on a given date.

    Use this tool whenever a customer asks about flight availability,
    departure times, prices, or seat availability between two cities.

    Args:
        origin      : IATA airport code for the departure airport (e.g. 'LHR', 'JFK')
        destination : IATA airport code for the arrival airport (e.g. 'CDG', 'MIA')
        date        : Travel date in YYYY-MM-DD format (e.g. '2026-03-15')

    Returns:
        A formatted summary of matching flights, or a message if none found.
    """
    # 3. the docstring above is the contract with the model -- see below
    # 4. load data, filter, and return a formatted string
```

**The type hints _are_ the schema.** `origin: str` becomes a required string parameter in the JSON schema the model receives. There is no second definition to keep in sync, which is the point — a mismatch between schema and signature is impossible because there is only one of them.

**The docstring is the contract, and it is doing more work than it looks.** Three separate jobs live in it:

| Part of the docstring | What the model uses it for |
| --- | --- |
| First line | what the tool *is* |
| _"Use this tool whenever a customer asks about…"_ | **when to call it** — the decision, not the description |
| Each `Args:` entry | what each argument *means*, and its format |

That third row is where the real leverage sits. `date : Travel date in YYYY-MM-DD format` is the only thing stopping the model from passing `"next Tuesday"` or `"15/03/2026"`. A format hint in a docstring is _cheaper and more reliable than validation code_, because it prevents the bad call rather than rejecting it. Equally, an unhelpful docstring is a functional bug: the model has nothing else to go on.

## Does `@tool` really "register" the tool?

**No, and the wording matters.** The decorator extracts metadata and builds the schema; it does not put the function anywhere the agent looks. The agent sees a tool only because you passed it in `tools=[...]`.

Strands _does_ have an auto-discovery mechanism — it will load and hot-reload any tool in a `./tools/` directory — but `load_tools_from_directory` **defaults to `False`**, and the docs recommend leaving it off in production. Worth knowing why: with it on, _any_ Python file dropped in that directory gets executed by the agent.

So the mental model is explicit wiring, not discovery. Which is also reassuring: nothing you didn't list can reach the model.

## What can a tool actually return?

The course example returns `str`, and that is the common case, but it is not a requirement. Strands converts the return value in three cases:

| You return | What Strands does |
| --- | --- |
| a string or other simple value | wraps it as `{"text": str(result)}` |
| a dict shaped as a proper `ToolResult` | uses it directly, giving you control of status and content type |
| an exception is raised | converts it to an error response automatically |

A `ToolResult`'s content can be `text`, `json`, `image` or `document` — so a tool can hand back a picture or a file, not only prose.

That third row deserves attention: **you do not need `try`/`except` for the model's benefit.** A raised exception becomes a tool-error the model can read and react to, often by apologising or trying different arguments. Catching everything and returning `"error"` as a string throws away information the model could have used.

## Two tools, one turn

Wiring a custom tool in is identical to a built-in one — same list, no distinction:

``` Python
from strands import Agent
from strands_tools import current_time      # built-in: get the current date and time

agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[current_time, search_flights],   # built-in and custom, same list
)
```

Ask _"Are there flights from LHR to CDG today?"_ and the agent calls `current_time` first, then `search_flights` with the resolved date, and answers — all in one turn.

**No new machinery is involved.** This is the loop from the earlier topic running twice: the model asks for `current_time`, gets a result appended, is called again, and _now_ has enough to ask for `search_flights`. Chaining is not a feature; it is what "loop until the model stops asking" already means. What makes it work is that the model can see the date field wants `YYYY-MM-DD` and that it lacks today's date — both facts coming from docstrings.

> **Note:** some built-in tools prompt for interactive confirmation before acting — those touching files, the shell, or code execution. In a deployed agent there is nobody to answer, so the call blocks. `BYPASS_TOOL_CONSENT=true` disables the prompt. Worth knowing before wiring `shell` or `file_write` into anything that runs unattended.

# Structured Outputs

Text is for humans; structure is for systems. An agent that summarises a support call in prose is useful to a person reading it. An agent that returns `{"issue_type": "login_problem", "urgency": "high"}` can open a ticket, page someone, or update a dashboard without anyone reading anything. That is the whole motivation: **structure is what lets an agent be a component rather than a conversation.**

## Why asking for JSON is not enough

The naive approach is to put it in the prompt — _"reply as JSON with fields issue_type, urgency, customer_email"_. It works often enough to be dangerous, and fails in a specific way: you get **syntactically fine JSON with semantically useless values**. `"urgency": "very"`. `"customer_email": "none found"`. Both parse; neither is usable.

The reason is worth stating precisely. A model is trained to produce plausible text, and a schema is a _type contract_. Nothing in next-token prediction enforces "this field is one of three enum values". Asking politely does not change the mechanism.

## Four levels of enforcement, and where each acts

These are usually discussed as one topic, but they intervene at different points and give different guarantees:

| Level | What it does | Where it acts | Guarantees | Tool used | Example |
| --- | --- | --- | --- | --- | --- |
| **Prompt instruction** | asks for JSON | nowhere | nothing | the system prompt | `"Reply as JSON with fields issue_type, urgency"` |
| **Tool / function schema** | model must emit a structured call matching a JSON schema | the model API | _shape_ — right fields, right JSON types | Strands `@tool`; `toolConfig`/`toolSpec` on Bedrock `Converse` | `def search_flights(origin: str, date: str)` — schema built from the signature and docstring |
| **Constrained decoding** | the schema is compiled into a grammar so invalid tokens cannot be produced | inside the model's sampler | shape, at generation time | `BedrockModel(strict_tools=True)` | injects `strict: true` per tool spec and `additionalProperties: false` into object schemas |
| **Runtime validation** | rejects or coerces what arrived | your code | _semantics_ — whatever you actually assert | Pydantic `BaseModel`, `Field`, `model_validate` | `date: Date = Field(...)` rejects `"banana"` and parses `"2026-03-15"` into a real `datetime.date` |

They stack rather than compete: a tool schema gets you the envelope, constrained decoding stops the model producing a malformed one, and validation is the only level that checks whether the contents mean anything. Strands' `agent.structured_output()` is rows 2 and 4 together — it generates a tool spec from your Pydantic model, then validates the reply against it.

On Bedrock, constrained decoding (row 3) is reachable through `strict_tools` on `BedrockModel`, which adds `strict: true` to each tool spec and injects `additionalProperties: false` into object schemas. It is not free: strict mode restricts which JSON Schema features a tool may use — `oneOf` is unsupported, and optional parameters are capped across all tools in a request — and a schema using an unsupported feature fails at request time with a `ValidationException`.

## What does a tool schema actually guarantee?

**Shape, not meaning.** This is the distinction everything else hangs off. Declare `date: str` and you are guaranteed a string. You are not guaranteed a _date_. `"next Tuesday"`, `"15/03/2026"` and `"banana"` are all perfectly valid values for a field typed `str`.

So function calling does not "guarantee correct format and types" in the sense people hope. It guarantees the envelope. What is inside the envelope is your problem, which is exactly why validation exists.

## Does `FlightSearchInput` reject a bad date?

**No — and this is worth knowing before trusting it.** The demo's model looks like a guard:

``` Python
class FlightSearchInput(BaseModel):
    origin: str = Field(description="IATA departure airport code, e.g. LHR")
    destination: str = Field(description="IATA arrival airport code, e.g. CDG")
    date: str = Field(description="Travel date in YYYY-MM-DD format, e.g. 2026-03-15")
```

Tested directly, every one of these is **accepted**: `date="next Tuesday"`, `date="15/03/2026"`, `date="banana"`, `date=""`. The only thing rejected is a _missing_ field. All three fields are unconstrained `str`, and `Field(description=...)` is documentation — it constrains nothing.

`description` describes. To validate, you need a **type or a constraint**:

``` Python
from datetime import date as Date

class FlightSearchInput(BaseModel):
    origin: str = Field(description="IATA departure airport code", pattern=r"^[A-Z]{3}$")
    date: Date = Field(description="Travel date in YYYY-MM-DD format")
```

Now `"banana"` and `"15/03/2026"` fail with `date_from_datetime_parsing`, `"lhr"` and `"LONDON"` fail with `string_pattern_mismatch`, and `"2026-03-15"` is _parsed into a real `datetime.date`_ rather than left as a string. That last part matters: a validated model should hand you a usable object, not a string you still have to parse.

## What does `Optional[str] = Field(default=None)` actually declare?

Three separate things live in that one line, and the middle one is the part almost everyone misreads:

``` Python
check_in_time: Optional[str] = Field(default=None, description="Check-in time, e.g. '15:00'")
#     ^              ^                    ^                          ^
#   name       type annotation         default                    metadata
```

- `Optional[str]` is shorthand for `str | None` — the **value** may be a string or null.
- `default=None` says the **key** may be absent from the input.
- `description=...` is documentation; it constrains nothing.

**`Optional` does not make a field optional.** It makes the value _nullable_. Omittability comes from the default alone, and in Pydantic v2 those are independent axes:

``` Python
class A(BaseModel): x: str                                  # required, no null
class B(BaseModel): x: Optional[str]                        # required, null allowed
class C(BaseModel): x: Optional[str] = Field(default=None)  # omittable, null allowed
class D(BaseModel): x: str = Field(default="15:00")         # omittable, no null
```

Run against all three cases, the results are:

| Declaration | key omitted | value is `null` | value is `'15:00'` |
| --- | --- | --- | --- |
| `x: str` | error `missing` | error `string_type` | ✓ |
| `x: Optional[str]` | **error `missing`** | ✓ → `None` | ✓ |
| `x: Optional[str] = None` | ✓ → `None` | ✓ → `None` | ✓ |
| `x: str = "15:00"` | ✓ → `'15:00'` | error `string_type` | ✓ |

Row two is the surprise: **`Optional[str]` with no default is still required.** All the annotation bought you is the right to pass an explicit `null`.

> **Note:** this changed between versions. In Pydantic **v1**, `Optional[str]` implied a default of `None`, so `Optional` genuinely did mean skippable. **v2 separated the two ideas.** Any tutorial or answer describing `Optional` as making a field omittable is describing v1.

`Field(default=None)` is simply `= None` with metadata attached — `x: Optional[str] = None` behaves identically. Reach for `Field(...)` only when you also want a description or a constraint.

It also changes what a tool emits. `model_dump_json()` renders an absent value as `null` rather than dropping the key, so the model receives `{"check_in_time": null}`. That is exactly the trade a nullable results field makes: the caller gets the record with one blank field instead of losing the whole record.

## Do the `Field(description=...)` strings reach the model?

**Not in this design, no.** It is tempting to think adding descriptions to a Pydantic model tightens the contract with the LLM. It doesn't, because the model never sees that schema.

`@tool` builds the tool specification from the **function signature and docstring**. In the demo the signature is `(origin: str, destination: str, date: str)` and `FlightSearchInput` is only instantiated inside the body — after the model has already chosen its arguments.

The proof is in a discrepancy. With a `Field(description="IATA departure airport code, e.g. LHR")` and a docstring saying `origin: IATA departure airport code`, the generated `tool_spec` contains:

```
"origin": { "description": "IATA departure airport code", "type": "string" }
```

The `e.g. LHR` is absent — so the text came from the docstring, not the Field. Two consequences: **the docstring is where you influence the model's behaviour**, and the Pydantic model is a runtime guard that acts only after a bad call has already been made.

## Strands has native structured output

The lesson stops at using Pydantic inside a tool, but Strands can make the **agent itself** return a validated object:

``` Python
class TripSummary(BaseModel):
    destination: str = Field(description="City the traveller is going to")
    nights: int = Field(ge=1, description="Number of nights")
    total_usd: float = Field(description="Total cost in US dollars")

result = agent("Summarise: Rome, 4 nights, flight $349 plus $175 a night")
# or explicitly:
summary = agent.structured_output(TripSummary, "Summarise: ...")
```

Passing `structured_output_model=TripSummary` to an invocation puts the validated object in `AgentResult.structured_output`, and a failure raises `StructuredOutputException`. It works across every model provider Strands supports.

**The mechanism is the interesting part: structured output _is_ function calling.** Strands converts your schema into a tool specification and the model returns data by calling that synthetic tool. So the two halves of this lesson are not alternatives — the Pydantic model, the tool schema and the structured response are all the same machinery pointed at different jobs.

## `Model(**data)` or `Model.model_validate(data)`?

**They run the same validation.** Verified: `HotelOption.model_validate(h) == HotelOption(**h)` is `True`, and both reject the same malformed record with the same error type. The choice is about the shape of the data in your hand, not about what is being validated or where it came from.

| You are holding | Use | Because |
| --- | --- | --- |
| separate named values | `Model(city=city, max_price_usd=max_price_usd)` | assembling a dict just to validate it is noise |
| one object, usually a dict | `Model.model_validate(record)` | unpacking it for Pydantic to reassemble it is noise |

That is the whole reason a tool uses the constructor for the LLM's arguments — they arrive as separate function parameters — and `model_validate` for each dataset record, which is already a dict. Nothing deeper is implied by the pairing.

It does also signal intent, which is worth something: `model_validate(record)` reads as _"here is untrusted data, check it"_, while the constructor reads as _"I am building one of these"_.

**One real capability difference.** `model_validate` accepts keyword arguments the constructor has no equivalent for — `strict=`, `from_attributes=`, `context=` — and the first of those changes behaviour you probably care about:

``` Python
HotelOption.model_validate({**record, "price_per_night_usd": "149"})
# -> 149.0        the string was silently coerced to a float

HotelOption.model_validate({**record, "price_per_night_usd": "149"}, strict=True)
# -> ValidationError: float_type
```

**Pydantic coerces by default**, so a `float` field accepts the string `"149"`. That has a sharp consequence for the broken-dataset exercise: the bad record is caught only because `"check website"` is not numeric. Had the data said `"149"`, the record would have been quietly _repaired_ rather than skipped, and nothing would have told you the upstream type was wrong.

Which you want is a genuine decision. Lax is forgiving of sloppy upstream data, which is usually right for a JSON file you do not control. Strict is right when a type change signals a problem you would rather hear about than paper over. And `from_attributes=True` lets `model_validate` read an arbitrary object's attributes — an ORM row, say — which the constructor cannot do at all.

## Validate at both ends

The demo's tool validates twice, and the second one is easy to overlook:

1. **Input from the model** — catches a malformed call before the filter runs on junk.
2. **Each record from the dataset** — `FlightOption.model_validate(fl)` inside a loop, logging and skipping bad rows rather than raising.

That second check is defending against _your own data_, not the LLM. A dataset with one malformed record would otherwise take down the whole tool call, and with it the agent's turn. Skipping and logging degrades gracefully: the traveller gets four flights instead of five, and the log tells you why.

> **Note:** returning `result.model_dump_json(indent=2)` rather than a dict is deliberate — a Strands tool returning a plain string has it wrapped as `{"text": ...}`, so the model receives the JSON as text it can read. Returning the Pydantic object itself would not serialise.

# Short-Term Memory

A language model has no memory. Every call is the first call. What looks like continuity is the framework **re-sending the conversation** on every turn — the agent is not remembering, it is being reminded, at full token cost, each time.

This is easy to see rather than take on trust. An agent built fresh inside its request handler, with memory disabled, answers _"and what about 5 nights?"_ by asking which hotel you mean. Nothing carried over, because nothing was re-sent.

## The three strategies, and what Strands calls them

The trade is always the same: context fidelity against tokens. Strands ships a class for each option, and one of them is already switched on whether you asked for it or not.

| Strategy | What it does | Strands | Cost |
| --- | --- | --- | --- |
| **Full history** | send every message every turn | no manager — you opt out of reduction | grows without bound; eventually overflows the context window |
| **Sliding window** | keep the most recent N messages | `SlidingWindowConversationManager` — **the default** | bounded, but older context is gone permanently |
| **Summarisation** | condense older messages into a précis | `SummarizingConversationManager` | bounded and retains the gist, at the price of an extra model call and lossy detail |

**The default matters.** `SlidingWindowConversationManager` is applied even when you never mention a conversation manager, so every agent in these labs already discards old turns once the window fills. The window is measured in _messages_ — not turns, and not exchanges — and defaults to 40. Since a turn that calls a tool expands into four messages, that default is nearer ten tool-using turns than forty of anything:

``` Python
from strands.agent.conversation_manager import SlidingWindowConversationManager

agent = Agent(
    conversation_manager=SlidingWindowConversationManager(
        window_size=10,   # messages to keep; the default is 40
        pin_first=1,      # never evict the first message
    )
)
```

`pin_first` is worth knowing: it protects the opening messages from eviction, which is how you stop a sliding window throwing away the turn that established what the whole conversation is about. The pin is written during the first reduction and stays set. **Pinned messages sit outside the window budget rather than inside it**: `window_size=6` with `pin_first=2` leaves eight messages — the two pinned, plus a full six-message window. So `pin_first` raises the ceiling instead of spending part of it, which matters when sizing a window against a context limit.

**Reduction runs at the end of an invocation rather than before the model call**, because `per_turn` defaults to `False`. That produces a result which looks contradictory at first: a turn can answer correctly from context that is evicted moments later, so the model saw more than the surviving history shows. `per_turn=True` reduces before every model call instead, which is what you want for an agent making many tool calls in a loop.

## What is "state", exactly?

The course splits this two ways — transient state versus session memory. Strands splits it **three** ways, and the finer taxonomy is more useful:

| | What it holds | Lifetime | Does the model see it? |
| --- | --- | --- | --- |
| **Conversation history** | the messages, in `agent.messages` | the conversation | **yes** — it *is* the prompt |
| **Agent state** | arbitrary data outside the conversation | across requests | **no** |
| **Invocation state** | context within a single invocation | one turn | no |

**The distinction that matters is not duration, it is whether the model sees it.** Conversation history is memory precisely because it is re-sent; agent state is deliberately *not* re-sent, which is what makes it the right place for a user id, a feature flag or a running counter — data your code needs and the model has no business reading, and which costs no tokens.

`Agent(state=...)` takes an `AgentState` or any JSON-serialisable dict, and `agent_id` names the agent for session management.

## Is short-term memory ephemeral?

**Not necessarily** — scope and storage are independent axes, and the course pairs them. AgentCore Memory's short-term memory stores raw events server-side: it survives a restart, and a user can return later and resume the same `sessionId`. Short-term in _scope_, durable in _storage_.

| | AgentCore short-term | AgentCore long-term |
| --- | --- | --- |
| Holds | raw events: messages, tool calls | extracted insights |
| Built by | `CreateEvent` per interaction | strategies: semantic, summarisation, user preference, episodic, or custom |
| Read by | `ListEvents`, `GetEvent`, `ListSessions` | semantic search across sessions |
| Scope | one session | all of an actor's sessions |

Both are scoped by **`actorId` + `sessionId`**.

> **Note:** getting `actorId` wrong leaks conversations between users. With memory enabled and no actor distinction, every conversation shares one memory — observed on a previous project, where a brand-new session was told details had "already" been provided and was handed an identifier created in someone else's conversation. Pass a fresh actor per conversation for isolation, or a stable one deliberately when a returning user should be remembered.

# What Is AgentCore Memory?

**Memory is its own AWS resource, created before and independently of any agent.** You create it once, keep the **memory ID** it returns, and hand that id to whatever code needs it. One resource can serve many agents, actors and sessions — nothing about it is per-agent.

Creation is asynchronous and takes a couple of minutes to reach `ACTIVE`, which is why the client offers a blocking variant:

``` Python
# pip install bedrock-agentcore
# =====================================================
# CREATING THE MEMORY RESOURCE - run once, before the agent
# =====================================================
from bedrock_agentcore.memory import MemoryClient

client = MemoryClient(region_name="us-east-1")

memory = client.create_memory_and_wait(   # the _and_wait variant polls until ACTIVE
    name="WanderBot",
    strategies=[],           # no strategies -> short-term only
    event_expiry_days=7,     # how long raw events are retained; the SDK default is 90
)
print(memory.get("id"))      # this string is the MEMORY_ID the agent needs
```

## `strategies` is the switch between the two layers

Short-term and long-term are not two services; they are two halves of one resource, and the `strategies` list decides which halves are live. An empty list stores raw events and does nothing further with them. Add a strategy and the _same_ events additionally feed an extraction pipeline.

The halves differ in _when_ they are written, and that is the practical catch. Short-term is synchronous — `create_event` returns and the event is durably stored. Long-term extraction is asynchronous and runs well behind the conversation: the SDK ships `wait_for_memories` purely to poll until it has caught up, and that method's own docstring recommends `time.sleep(150)` — two and a half minutes — for the cases where polling is unreliable. Long-term memory is therefore _eventually_ consistent, and an insight drawn from the current turn is not something the next turn can rely on.

## Strategies and namespaces

A **strategy** is the rule for converting raw conversation into durable insight, and comes in four ready-made families — semantic, summary, user preference and episodic — plus custom variants where you supply the extraction and consolidation configuration yourself.

Each strategy writes into a **namespace**: a slash-separated path fixed when the strategy is created, with `{actorId}`, `{sessionId}` and `{memoryStrategyId}` available as template variables. **The path is the retrieval scope**, which makes it a design decision rather than a label — `/strategy/{memoryStrategyId}/actor/{actorId}/session/{sessionId}/` confines insights to a single conversation, while dropping the session segment exposes them across every conversation that actor has ever had. Retrieval names the namespace directly, `retrieve_memories(namespace=..., query=..., top_k=...)`, with a `namespace_path` prefix form for reading a whole subtree. Namespaces are long-term only: short-term is always keyed by actor plus session, with no path involved.

## Events are immutable and append-only

Everything short-term memory holds is an **event**, appended and never edited. Conversational events carry `(text, ROLE)` pairs with the role `USER`, `ASSISTANT` or `TOOL`; blob events carry an arbitrary payload instead, which is where an agent checkpoint or serialised state would go rather than dialogue. Both are keyed by `memoryId` + `actorId` + `sessionId`, and `event_expiry_days` on the resource sets how long they survive.

> **Note:** the launch blog states that only conversational events feed long-term extraction. That is not repeated in the API reference, so treat it as probable rather than settled.

# Wiring Short-Term Memory Into the Agent

A planning conversation arrives in pieces — destination in one message, dates in the next, party size after that. Without memory every invocation is stateless and the traveller has to repeat themselves. The fix is **session-scoped short-term memory**, backed by AgentCore Memory and wired in through the Strands hook system.

## First, a memory resource

Memory is a resource you create before any code runs, either in the AgentCore console's memory section — name it, choose a short-term expiry, create — or from the CLI:

```bash
agentcore memory create --name wanderbot-memory
```

It takes a couple of minutes. Take the **memory ID** from the output and put it in your code.

## What is a hook, underneath?

**A hook is a callback the agent invokes at a named point in its own run loop.** Strands publishes _event objects_ at fixed moments — invocation start and end, before and after each model call, before and after each tool call, a message being appended, construction finishing — and you subscribe by registering a callback against the event _class_. Version 1.53 exports fifteen event types; short-term memory uses two of them. Request logging, tool-call auditing and guardrails are this same mechanism aimed at different events.

The design goal is composition: behaviour is added from _outside_ the agent, with no subclassing of `Agent` and no fork of the SDK.

| Piece | What it actually is |
| --- | --- |
| **`HookProvider`** | A `@runtime_checkable` _protocol_ rather than a base class — its sole requirement is a `register_hooks(self, registry, **kwargs)` method, and inheriting from it is optional. What it earns you is a home for several related callbacks _and_ the state they share, here the memory client, the memory id and `last_k_turns` |
| **`HookRegistry`** | The agent's own switchboard, reachable afterwards as `agent.hooks`. You never construct one; it arrives as the argument to `register_hooks`. `add_hook(provider)` does nothing but call `provider.register_hooks(registry)` straight back, while `add_callback(EventType, fn, order=0)` does the real subscribing, keeping one callback list per event type sorted by `order`, lowest first |

**Your callbacks queue alongside the framework's own.** During construction the agent registers its conversation manager, retry strategy and session manager on that same registry — `SlidingWindowConversationManager` from the previous topic is itself a `HookProvider`, and does its compression from a `BeforeModelCallEvent` callback. Hooks are not a bolt-on for user code; they are how Strands is wired internally.

## Two lifecycle events do all the work

| Event | Fires | Does |
| --- | --- | --- |
| `AgentInitializedEvent` | once per invocation, before the first model call | loads the last _k_ turns from memory and injects them into the system prompt |
| `MessageAddedEvent` | every time a message is added, user **and** assistant | persists that message with `memory_client.create_event` |

``` Python
from strands.hooks import (
    AgentInitializedEvent,   # fires once per invocation, before the first model call
    HookProvider,            # protocol you implement: one method, register_hooks
    HookRegistry,            # what you attach callbacks to
    MessageAddedEvent,       # fires on every message appended to the conversation
)


class ShortTermMemoryHookProvider(HookProvider):
    def __init__(self, memory_client, memory_id, last_k_turns=5):
        self.memory_client = memory_client   # bedrock_agentcore.memory client
        self.memory_id = memory_id           # the resource id from `agentcore memory create`
        self.last_k_turns = last_k_turns     # how much history to replay; more turns = more tokens

    def register_hooks(self, registry: HookRegistry) -> None:
        # The one method HookProvider requires. It declares which lifecycle events
        # you want and which of your methods handles each. Strands calls them; you
        # never invoke these yourself -- same registration pattern as @app.entrypoint.
        registry.add_callback(AgentInitializedEvent, self.on_agent_initialized)
        registry.add_callback(MessageAddedEvent, self.on_message_added)

    # ---- READ PATH: once, at the start of an invocation ----------------------
    def on_agent_initialized(self, event: AgentInitializedEvent) -> None:
        # Both ids live in agent.state, put there by the entrypoint.
        actor_id = event.agent.state.get("actor_id")
        session_id = event.agent.state.get("session_id")
        if not actor_id or not session_id:
            return          # no ids -> no memory, but the agent still works

        # Ask AgentCore Memory for this session's recent history. Returns a list of
        # turns, where each turn is itself a list of messages.
        recent_turns = self.memory_client.get_last_k_turns(
            memory_id=self.memory_id,
            actor_id=actor_id,
            session_id=session_id,
            k=self.last_k_turns,
        )
        if not recent_turns:
            return          # first turn of a new session: nothing to replay

        # Flatten the nested turns into plain "Role: text" lines.
        lines = []
        for turn in recent_turns:
            for m in turn:
                role = m.get("role", "unknown").capitalize()
                text = m.get("content", {}).get("text", "")
                if text:
                    lines.append(f"{role}: {text}")
        if lines:
            # This is the whole trick: history reaches the model as extra system
            # prompt. Nothing is "remembered" -- the prompt is simply longer.
            event.agent.system_prompt += "\n\nRecent conversation:\n" + "\n".join(lines)

    # ---- WRITE PATH: every message, user and assistant -----------------------
    def on_message_added(self, event: MessageAddedEvent) -> None:
        actor_id = event.agent.state.get("actor_id")
        session_id = event.agent.state.get("session_id")
        if not actor_id or not session_id:
            return

        # Messages carry a list of content blocks; pull the text out of the first.
        message = event.message
        content = message.get("content", [])
        text = content[0].get("text") if content and isinstance(content[0], dict) else None
        if not text:
            return          # tool-use blocks and the like have no text to store

        # One event per message, keyed by actor + session. `messages` takes
        # (text, ROLE) tuples, with the role upper-cased.
        self.memory_client.create_event(
            memory_id=self.memory_id,
            actor_id=actor_id,
            session_id=session_id,
            messages=[(text, message.get("role", "").upper())],
        )
```

## Where the two events are fired from, exactly

| Event | Emitted from | Called |
| --- | --- | --- |
| **`AgentInitializedEvent`** | the _last line_ of `Agent.__init__` | synchronously |
| **`MessageAddedEvent`** | `Agent._append_messages`, once per message appended | asynchronously |

The first location is what makes the read path safe: the constructor has finished assembling everything, yet no model call has happened, so `system_prompt` is still unsent and rewriting it costs nothing. It also means the read runs during `Agent(...)` rather than during `agent(user_message)` — build the agent twice in one request and history is replayed twice.

> **Note:** an `AgentInitializedEvent` callback **must be synchronous**. `add_callback` raises `ValueError: AgentInitializedEvent can only be registered with a synchronous callback` when handed an `async def`. That is why `on_agent_initialized` is a plain `def` in a file whose entrypoint is `async`.

The second location is why the write path bails out quietly when it finds no text: it fires for _every_ appended message, and an assistant message asking for a tool carries a tool-use block rather than prose. Only messages appended by the framework fire it at all, so anything a tool pushes into `agent.messages` by hand is never persisted.

## Why the hook can rewrite the system prompt

Hook events are frozen in all but name: their base class overrides `__setattr__` to raise `AttributeError` for any property not explicitly marked writable, so `event.message = something` fails outright. `event.agent.system_prompt += ...` succeeds because it never touches the event — it reaches _through_ it to the agent the event merely holds a reference to. An event is a notification with a pointer attached, not a mutable payload.

## The two paths, and why the ordering matters

```
  INVOCATION 1  (session_id = S)                    AgentCore Memory
  ────────────────────────────────                  ────────────────
  AgentInitializedEvent
    └─ get_last_k_turns(S) ──────────────────────►  (nothing yet)
       system_prompt unchanged

    user: "Alice is planning a trip to Rome"
      └─ MessageAddedEvent
           └─ create_event ────────────────────────►  USER      "Alice is…"
    assistant: "Lovely — when are you travelling?"
      └─ MessageAddedEvent
           └─ create_event ────────────────────────►  ASSISTANT "Lovely — …"

  INVOCATION 2  (same session_id = S)
  ────────────────────────────────
  AgentInitializedEvent
    └─ get_last_k_turns(S) ──────────────────────►  reads both back
       system_prompt += "Recent conversation: …" ◄──┘

    user: "which one is the cheapest?"                 <- now resolvable
      └─ MessageAddedEvent
           └─ create_event ────────────────────────►  USER      "which one…"
```

The asymmetry is the point: **the read happens once, at the start of an invocation; the write happens on every message.** So memory does nothing to help *within* a single invocation — Strands' own message list already carries that. What memory buys is the bridge *between* invocations, which is exactly where a stateless agent forgets.

That also explains the failure mode from earlier labs. Rebuilding the `Agent` inside the handler wipes the message list every request; memory restores it from outside, so the same follow-up question that previously drew a blank now resolves.

The entrypoint stays thin — it builds the agent with `hooks=[...]` and `state={"session_id": ..., "actor_id": ...}` and nothing else. `session_id` comes from `context`, which AgentCore supplies automatically and which every invocation in the same session shares. `actor_id` comes from the payload, so you pass it in. Both go into `agent.state`, which is how the hook provider reads them.

## Configure with memory enabled

At `agentcore configure`, **do not** pass `--disable-memory` — answer the memory prompt and select the memory resource. Running interactively rather than with `--non-interactive` is what lets you do that.

## Proving it works by taking it away

The demonstration is worth repeating: ask for flights, then run `agentcore stop-session` and ask _"which one is the cheapest?"_. With the session gone the agent has no context and starts asking for origin and destination again. Re-run the flight search in a fresh session, ask the same follow-up, and it answers correctly. Same code, same question — the only variable is whether the session's memory exists.

## Key takeaways

- `HookProvider` is the extension point for the Strands agent lifecycle. Subclass it, implement `register_hooks()`, and bind callbacks to the events you care about.

- `AgentInitializedEvent` fires once per invocation — the right place to load prior turns from AgentCore Memory and inject them into the system prompt.

- `MessageAddedEvent` fires on every new message — the right place to call memory_client.create_event so user and assistant text is persisted turn by turn.

- `agent.state` is how session identity reaches hooks. Pass state={"session_id": ..., "actor_id": ...} on the Agent and read it with event.agent.state.get(...).

- Session memory is scoped by session_id, and by user. A traveller with multiple planning sessions gets separate contexts without cross-contamination.

- The entrypoint stays tiny. Once the hook provider is attached, persistence and context injection happen automatically — no orchestration code is required.


# From Local Tools to Managed APIs

Every tool so far was a `@tool` function inside the agent's own source. That is right for development and wrong for production, for reasons that have nothing to do with the model: the tool shares the agent's deployment, its runtime, its dependencies and its permissions, and the data it reaches — Horizon's bookings — lives in another system anyway. A `@tool` that calls that system is just a client with the agent's release schedule bolted on.

The production shape is to run the tool as its own service and put something between the agent and the service that both sides understand. In AgentCore that something is the **Gateway**.

## What is AgentCore Gateway?

**AgentCore Gateway** is a managed MCP server that fronts your existing services — Lambda functions, REST APIs, other MCP endpoints — and presents them to an agent as tools. It does two jobs: it _translates_ an MCP tool call into an invocation of the thing behind it, and it _advertises_ which tools exist, so the agent discovers them instead of carrying their definitions in code.

**MCP (Model Context Protocol)** is the open protocol that standardises how an agent talks to tool servers: a client connects, asks the server to list its tools (name, description, parameter schema), and calls them by name. The agent side is an MCP _client_; the Gateway is an MCP _server_. Nothing behind the Gateway needs to know MCP exists.

| | Local `@tool` | Gateway tool |
| --- | --- | --- |
| **Where the code runs** | inside the agent's process | in a Lambda (or other target) |
| **Where the schema comes from** | generated from signature + docstring | written by hand, registered on the target |
| **How the agent learns about it** | imported in code | discovered at runtime over MCP |
| **Deployed with** | the agent | independently |

## What is a Gateway target?

**A Gateway holds no tools of its own.** It is the MCP front door; the tools live on **targets** attached to it. A target is one backend plus the description of what that backend offers — and the Gateway is the thing that turns "attached targets" into "a single list of tools" when the agent asks.

```
Gateway  wanderbot-gateway                     one MCP endpoint, one URL
  |
  +-- target  booking-target   -> Lambda      get_booking, list_bookings_by_email
  +-- target  hotel-target     -> Lambda      search_hotels, ...          (not built here)
  +-- target  ...              -> OpenAPI     every operation in the spec
```

A target is three things, fixed when you create it:

| Part | What it is | In this lab |
| --- | --- | --- |
| **The backend** | what the Gateway invokes | one Lambda function, by ARNs |
| **The tool schema** | what that backend offers, in MCP terms | `booking_lambda.json`, two tools |
| **The credential provider** | how the Gateway authenticates _to_ the backend | the Gateway's own IAM role |

**Targets are typed by backend.** Lambda is one of several. The control-plane API's `targetConfiguration` accepts `lambda`, `openApiSchema`, `smithyModel`, `mcpServer`, `apiGateway` and `connector` — so the same Gateway can front a Lambda, a REST API described by an OpenAPI document, and another MCP server, and the agent sees one flat tool list regardless. For an OpenAPI target the schema _is_ the spec, and each operation becomes a tool; for Lambda there is nothing to introspect, which is why you supply the tool schema by hand.

**The credential provider is the half the console hides.** Every target needs one, and for a Lambda it is `GATEWAY_IAM_ROLE` — the role you gave the Gateway at creation, which must be allowed `lambda:InvokeFunction` on that ARN. The other options (`OAUTH`, `API_KEY`, `CALLER_IAM_CREDENTIALS`, `JWT_PASSTHROUGH`) are for backends that want their own authentication, and they are the mechanism by which a Gateway can hold a secret the agent never sees. The console sets `GATEWAY_IAM_ROLE` silently when you "create a new service role"; building the target with the API or CloudFormation, you must say it, and the service refuses a Lambda target without it.

> **Note:** the role is _not_ checked when the Gateway is created — `create_gateway` accepts any ARN. It is checked when the **target** is attached, with "Gateway execution role lacks permission to invoke Lambda function". So a bad role surfaces at target creation, and IAM's eventual consistency means a _correct_ role attached seconds earlier can be refused once and succeed on retry.

**The target name becomes part of every tool name.** The Gateway exposes each tool as `<target>___<tool>` — `booking-target___get_booking`. That prefix is what keeps two targets that each define a `search` tool from colliding, and it is the string the Lambda handler strips to recover the function name. The target name you choose is therefore not cosmetic: it is in the protocol.

**Lifecycle, and why it matters for idempotency.** A target has its own status (`CREATING`, `READY`, `FAILED`, plus `SYNCHRONIZING` for backends the Gateway re-reads), and it can only be attached to a Gateway that is already `READY`. A target is a child of its Gateway — delete the Gateway and its targets go with it — but it is addressed by its own `targetId`, and `list_gateway_targets` has no filter-by-name, so finding "the target I already made" means scanning the list. One Gateway, many targets, each independently added, updated or removed without touching the others: that is the unit of change, and it is what lets a tool backend be swapped without the agent noticing.

## The flow, end to end

```
WanderBot (Strands Agent)
    |  MCP over streamable HTTP   -- list tools, then call one
AgentCore Gateway
    |  direct Lambda invocation   -- no API Gateway, no HTTP routing
booking_lambda.py
    |  handler routes on the tool name the Gateway supplies
get_booking() / list_bookings_by_email()
```

Two things are notable by their absence. There is no API Gateway and no web framework in the Lambda: the Gateway invokes the function directly, so the handler receives plain parameters and returns a result. And there is no tool code in the agent: it holds a URL and a system prompt, nothing else.

## The Lambda behind the Gateway

The Lambda is ordinary Python: hard-coded sample data, two functions (`get_booking` by reference, `list_bookings_by_email` by address), and a handler. The one Gateway-specific line is how the handler learns _which_ tool was called. The Gateway invokes a single function for every tool on the target, and names the intended tool in the invocation's client context:

``` Python
raw_tool = context.client_context.custom.get("bedrockAgentCoreToolName", "")
tool = raw_tool.split("___", 1)[-1] if "___" in raw_tool else raw_tool
```

The handler expects the name prefixed by the target name and three underscores — `booking-target___get_booking` — and keeps the part after the separator. That is the whole dispatch: one Lambda, several tools, routed by a string the Gateway sets. The fallback branch (infer the tool from the event's keys when there is no client context) is what keeps a plain `aws lambda invoke` working for local testing.

## What does the schema file contribute?

The Gateway runs in a different process from the function, so it cannot introspect a signature or read a docstring. The **schema** is how you tell it what the Lambda offers: a list of tool definitions, each with a `name`, a `description` the model reads when choosing tools, and an `inputSchema` — JSON Schema for the parameters, which the Gateway also uses to validate what the model sends. You register it when adding the Lambda as a target.

Set a Gateway tool definition beside a `@tool`'s generated `tool_spec` and they have the **same three keys**: `name`, `description`, `inputSchema`. The decorator generated that contract from code; for a Gateway tool you author it by hand. Same contract, different author — which is why the model experiences no difference between them.

## Connecting from the agent

``` Python
# pip install strands-agents mcp
# =====================================================
# AGENT SIDE - discover tools, then use them, in one session
# =====================================================
from strands import Agent
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamable_http_client

GATEWAY_ENDPOINT = "https://<gateway-url>/mcp"

# 1. A transport FACTORY, not a connection. The lambda is a recipe the client
#    calls later; constructing MCPClient opens nothing.
client = MCPClient(lambda: streamable_http_client(url=GATEWAY_ENDPOINT))

# 2. Entering the block is where networking starts: a background thread opens
#    the transport and completes the MCP handshake before the body runs.
with client:
    # 3. Ask the server for every registered tool. Each comes back as a
    #    Strands-compatible tool object built from the Gateway's schema.
    tools = client.list_tools_sync()

    # 4. Same constructor as always. No @tool anywhere.
    agent = Agent(model=model, system_prompt=SYSTEM_PROMPT, tools=tools)

    # 5. Invoke INSIDE the block - remote tools call back through this client.
    response = agent(user_message)
# 6. Leaving the block closes the session and the thread, even on an exception.
```

> **Note:** `MCPClient(url=GATEWAY_ENDPOINT)` is accepted as a shortcut and builds the streamable HTTP transport for you. The lambda form is the general one — it is how you would plug in any other MCP transport.

## Why can the agent not tell a local tool from a remote one?

Because they are the same type as far as `Agent` is concerned. `list_tools_sync()` wraps each MCP tool definition as an `MCPAgentTool`; a `@tool` function becomes a `DecoratedFunctionTool`. Both subclass Strands' `AgentTool`, and `Agent(tools=...)` asks every tool for the same three things — a name, a spec, a way to invoke it. The model is handed names and schemas either way. Where execution happens — in-process, across MCP to a Gateway, inside a Lambda — sits entirely below that boundary.

## What the `with` block owns

**The context manager is the session, not a convenience.** `MCPClient` does nothing at construction. `__enter__` starts a background thread, opens the transport, runs MCP initialisation and _blocks_ until the server is ready or `startup_timeout` (30 s by default) expires. `__exit__` tears all of it down.

Two consequences follow, and both bite:

- Call `list_tools_sync()` before entering the block and it refuses locally with `MCPClientInitializationError: the client session is not running` — no request is ever sent.
- Do not return `tools` out of the block and invoke the agent afterwards. An `MCPAgentTool` executes by calling back through its `MCPClient`, and that client has been stopped. Discovery and use share one session lifetime.

> **Note:** `mcp` ships both `streamable_http_client` and `streamablehttp_client`, and they are _different functions_ with different parameters, not alternative spellings of one. The course uses `streamable_http_client`; do not swap in the other on the assumption they are aliases.

## How do you know an endpoint speaks MCP at all?

You cannot tell from the URL. The protocol has no discovery endpoint and no "are you MCP?" probe; a server proves it speaks MCP by **answering the first message correctly**. That first message is the handshake, and `with client:` is nothing more than the SDK performing it for you.

**The handshake is JSON-RPC 2.0 over HTTP.** The client POSTs an `initialize` request naming its protocol version, capabilities and identity:

```bash
curl -s -i -X POST https://<endpoint>/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  --data '{"jsonrpc":"2.0","id":1,"method":"initialize",
           "params":{"protocolVersion":"2025-11-25","capabilities":{},
                     "clientInfo":{"name":"probe","version":"0.1"}}}'
```

An MCP server answers with a JSON-RPC _result_ carrying three required fields — its own `protocolVersion`, its `capabilities`, and `serverInfo` — plus a session header the client must echo on every later request. This is a real reply from a one-tool test server:

```json
HTTP/1.1 200 OK
content-type: application/json
mcp-session-id: <id>

{"jsonrpc":"2.0","id":1,
 "result":{"protocolVersion":"2025-11-25",
           "capabilities":{"tools":{"listChanged":false}, "prompts":{...}, "resources":{...}},
           "serverInfo":{"name":"probe-server","version":"1.29.1"}}}
```

The same request to a plain web server on another port returned `501 Unsupported method ('POST')` and an HTML error page. That is the whole test: a JSON-RPC result with those three fields means MCP; a 404, HTML, or JSON that is not a JSON-RPC result means not MCP, or not at that path.

**Then `tools/list` tells you it is a _tool_ server.** After `initialize`, the client sends a `notifications/initialized` notification and can start making requests. `tools/list` on the test server returned:

```json
{"jsonrpc":"2.0","id":2,
 "result":{"tools":[{"name":"ping",
                     "description":"Reply with a greeting, to prove a tool call round-trips.",
                     "inputSchema":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}}]}}
```

`name`, `description`, `inputSchema` — **the schema you register on a Gateway target is literally what its `tools/list` hands back.** The schema file and the discovery response are the same contract seen from the two ends of the wire, and `list_tools_sync()` is this call with the result wrapped as `MCPAgentTool` objects.

**In the SDK, the handshake is `with client:`.** `MCPClient.start()` opens the transport, sends `initialize`, and blocks until the result arrives. Run against both test servers:

| Endpoint | Outcome |
| --- | --- |
| the MCP server | block entered in 0.1 s; `list_tools_sync()` returned `['ping']` |
| the plain web server | `MCPClientInitializationError: the client initialization failed` in 0.1 s |

Note that the non-MCP endpoint failed **fast**, not at the 30-second `startup_timeout`. A server that is reachable but answers wrongly fails as soon as the transport sees the bad response — here a `501` — and the real cause is in the logged traceback (`httpx.HTTPStatusError: ... 501 Unsupported method`) rather than in the one-line exception message. The timeout path is for an endpoint that accepts the connection and then never completes the handshake, or cannot be reached at all.

> **Note:** two conventions make a URL _worth trying_, neither proves anything: streamable-HTTP MCP endpoints conventionally end in `/mcp` (the Gateway's does), and they accept `POST` of JSON with an `Accept` header listing both `application/json` and `text/event-stream`, since the server may stream a reply as SSE. The `curl` form above is worth running once against any new endpoint — it separates "not MCP" from "MCP, but my client is misconfigured", which the SDK's error alone does not.

## No authentication, deliberately

The Gateway is created with **No Authentication** for development, which is why the agent needs no auth headers. Treat the endpoint URL accordingly: an unauthenticated Gateway URL is a capability — anyone holding it can invoke every tool behind it — so it does not belong in source control or in saved notebook output. A later module adds AgentCore Identity for authenticated calls.

## Key takeaways

- Gateway is a managed MCP server fronting your services; the agent is an MCP client. Nothing behind the Gateway speaks MCP.
- The schema is the contract: `name` / `description` / `inputSchema`, the same three parts `@tool` generates — authored by hand because the Gateway cannot introspect a remote function.
- One Lambda serves several tools; the handler routes on `bedrockAgentCoreToolName`, stripping the `target___` prefix.
- `MCPClient` is lazy until `with`; the block owns the session, so discover tools _and_ invoke the agent inside it.
- The agent code barely changes: `@tool` functions out, `MCPClient` + `list_tools_sync()` in. The LLM sees identical schemas and cannot tell local from remote.
