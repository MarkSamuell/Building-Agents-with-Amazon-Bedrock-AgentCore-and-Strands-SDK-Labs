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

Not because arithmetic is interesting. Because LLMs _tokenize digits_, so multi-digit arithmetic is genuinely unreliable in a way that is easy to see and impossible to argue with. It is the cheapest possible demonstration where the failure is visible before the import and gone after it. The lesson is tool-use; the arithmetic is a prop.

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
| **`/ping`** | GET | Report `{"status": "Healthy"}`, or `HealthyBusy` while background work is still running, which keeps the session alive |

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
# nova-2-lite is chosen for being fast, cheap and strong at tool use -- the
# three things that matter for an agent, where the model is called repeatedly.
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

> **Note:** the entrypoint is declared `async def`, but `agent(user_message)` is an ordinary blocking call, so nothing here is actually concurrent — the coroutine holds the event loop until the agent finishes. It works and costs nothing for one request at a time. Real streaming needs `agent.stream_async(...)` with `yield` instead.

## Who decides that the payload key is `message`?

You do. The documentation is explicit that AgentCore _"passes request payloads directly to your container without validation"_ and that _"your container implementation determines which fields are required"_. There is no platform-defined schema, which is why AWS's own examples variously use `prompt`, `query` and `transcript` for the same idea. `message` is this file's private convention, and the caller simply has to match it.

> **Note:** `payload.get("message", "Hello!")` means a caller who sends `{"prompt": "..."}` gets no error — they get WanderBot cheerfully answering "Hello!". Convenient while testing, a silent bug anywhere real. `payload["message"]` fails loudly instead, which is usually what you want. Worse, the bug hides from the obvious test: send the message `"Hello"` and the reply is indistinguishable from the fallback firing. Only a message with specific content in it can tell you the key was read at all.

## Why is the Agent rebuilt on every request?

For _isolation_, and it is the most consequential line in the file. A Strands `Agent` accumulates conversation in `agent.messages`, so a module-level agent would keep every exchange the container ever handled — and traveller B would see traveller A's conversation. Rebuilding per request guarantees each caller starts clean. `model` can stay at module level precisely because it holds no conversation.

The cost is that **WanderBot has no memory at all**. Every request starts from an empty history, so a follow-up like "and what about 5 nights?" arrives with nothing to refer back to. Multi-turn conversation has to be added deliberately later, either by wiring in AgentCore Memory or by rehydrating history from the payload.

## The model id is not a model id

`us.amazon.nova-2-lite-v1:0` is a _cross-region inference profile_, not a foundation model. The `us.` prefix tells Bedrock it may route the request to whichever US region has capacity.

This has a consequence that only surfaces at deployment: the execution role must allow `bedrock:InvokeModel` on **both** ARNs below, and the foundation-model ARN has an _empty account segment_, because foundation models are not account-scoped.

```
arn:aws:bedrock:*:<account>:inference-profile/us.amazon.nova-2-lite-v1:0
arn:aws:bedrock:*::foundation-model/amazon.nova-2-lite-v1:0
```

Granting only the profile ARN produces an authorization failure that names nothing useful, and looks at first glance as though the model does not exist.

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
