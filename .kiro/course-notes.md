> Working copy of a Study-Notes file. Moves to `AI/AWS AI Agentic Engineer Nanodegree/1- Building Agents with Amazon Bedrock AgentCore and Strands SDK.md` when the course finishes.

# Why an Agent Framework?

A foundation model does exactly one thing: text in, text out. It cannot look anything up, cannot reliably do arithmetic, and cannot act on the world. Everything interesting that an "AI agent" appears to do comes from code _around_ the model, not from the model itself.

**The manual alternative** Without a framework you write that surrounding code yourself, and it is always the same code: describe your functions to the model in the prompt, parse the reply to work out _which_ function it wants and with what arguments, validate those arguments, call the function, format the result, append it to the conversation, and call the model again — repeating until the model stops asking. The loop is mechanical, and it fails silently in exactly the places that matter, such as a schema the model misreads or a tool result appended in the wrong shape.

**What Strands supplies** The loop itself, tool schemas generated automatically from your Python function signatures and docstrings, conversation state across turns, and adapters so the same agent runs against a different model provider unchanged.

## Why not just write the loop myself?

You can — it is perhaps eighty lines. The reason not to is that _the loop is not where the difficulty lives_. The difficulty is in tool-schema generation that the model actually understands, streaming partial responses, retries when a tool throws, capping runaway tool-calling, and keeping conversation state correct when a tool result arrives out of order. A framework is worth it for the second-order concerns, not the first-order one.

# The Three Layers

The course introduction names Bedrock, Strands and AgentCore Runtime in one sentence, which makes them look like three stages of one pipeline. They are not. They are three _independent_ layers, and knowing which does what prevents most of the confusion later.

| Layer | What it is | Alone, without the others |
| --- | --- | --- |
| **Amazon Bedrock** | An inference API. Messages in, text out. _Stateless_ — no tools, no loop, no memory. | Perfectly usable on its own via `Converse` or `InvokeModel`. |
| **Strands Agents SDK** | A library running _inside your own process_ that drives the agent loop and the tool plumbing. | A local Python script is already a complete, working agent. Needs no AWS hosting at all. |
| **AgentCore Runtime** | _Managed hosting_ for an agent — an HTTPS endpoint, session isolation, identity, observability. | Framework-agnostic. Hosts LangGraph, CrewAI or plain Python just as happily as Strands. |

The layering is a _containment_. The agent and its tools live in your own process; that process is optionally wrapped by AgentCore Runtime; Bedrock is a remote API called outwards from inside. So removing the outer wrapper leaves a working local script, swapping Bedrock for OpenAI changes nothing inside, and swapping Strands for LangGraph changes nothing outside.

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

## Container or zip?

The configure menu offers two deployment types, and the difference is worth knowing even though the course fixes on one.

| | **Container** (the course's choice) | **Direct code** (zip) |
| --- | --- | --- |
| Artifact | an ARM64 Docker image in ECR | a zip of code and dependencies in S3 |
| Steps | Dockerfile → build → push to ECR → deploy | package → upload → deploy |
| Iteration speed | slower; every change is a rebuild | faster, which is the point of it |
| Suits | custom system dependencies, existing container pipelines | rapid prototyping |

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

_Why it needs `uv` is unverified._ The only observable fact is that it refuses to start without it.

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

> **Note:** this step creates real, billable resources — an S3 object, an ECR repository holding an image, CodeBuild minutes, and the runtime itself. ECR storage and the runtime persist until deleted, so a deployed agent left behind keeps costing. Check the AWS pricing pages for current rates.

## Testing the deployed agent

`agentcore invoke` sends a JSON payload to the runtime, using the config file to find it. The course sends two messages deliberately: an ordinary greeting, which the model answers from its own knowledge, then an arithmetic question, which forces the calculator to fire. The second is the only proof that tool-calling survived deployment — a greeting would look identical whether or not the tool was wired up.

> **Note:** the course teaches the Python starter toolkit, whose signature is `configure` writing a `.bedrock_agentcore.yaml`. Running it now prints a deprecation notice: _"The Starter Toolkit CLI is no longer supported"_, directing you to the Node.js AgentCore CLI (`npm install -g @aws/agentcore`), which scaffolds with `create`, stores config under `agentcore/`, and is the only place new AgentCore features appear. `agentcore import` migrates existing agents. Both are invoked as `agentcore` and both have a `deploy`, so `agentcore --help` is what settles which is on your PATH.

> **Note:** a real deploy confirms the build runs in **CodeBuild**, in "codebuild mode", with no CodePipeline anywhere — the toolkit's own output says so. Course material describing a CodePipeline stage is wrong.
