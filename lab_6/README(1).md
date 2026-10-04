# Exercise: AgentCore Browser

## Overview
Give WanderBot a live web browser. You'll wire up `AgentCoreBrowser` as a tool on the Strands Agent so it can look up destination information from Wikivoyage in real time.

**Estimated time:** 10 minutes

## Learning Objectives
1. Import and instantiate `AgentCoreBrowser` from `strands_tools.browser`
2. Pass `browser.browser` as a tool to a Strands Agent
3. Set a `session_timeout` appropriate to the workload

## Architecture
```
WanderBot (Strands Agent)
    ↓  tool call
AgentCoreBrowser  (default browser)
    ↓
AWS-managed headless Chrome
    ↓
en.wikivoyage.org
```

## Dependencies

The Strands browser tool runs on **Playwright** under the hood. Two packages must be in `requirements.txt`:

- `playwright`
- `nest-asyncio`

You do not need to import them in the agent code — they're runtime dependencies only. They're already present in the provided `requirements.txt`.

## Prerequisites
- Previous lesson resources deployed
- AWS credentials configured

---

## Exercise Steps

### Step 1 — Import `AgentCoreBrowser`
In `starter.py`:

```python
from strands_tools.browser import AgentCoreBrowser
```

### Step 2 — Instantiate the browser and wire it to the agent
Inside `invoke()`:

```python
browser = AgentCoreBrowser(session_timeout=600)
agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[browser.browser],
)
response = agent(user_message)
return response
```

> Notes:
> - Pass `browser.browser` (the tool), not `browser` (the instance).
> - `session_timeout=600` gives you 10 minutes — the default is 3600s.

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
agentcore invoke '{"message": "What neighbourhoods should I stay in when visiting Tokyo?"}'
```

```bash
agentcore invoke '{"message": "Give me a brief travel overview of Barcelona."}'
```

While a call is running, open **AWS Console → Amazon Bedrock → AgentCore → Browser → Sessions** and click into the active session to watch the Live View.

## Key Insight
The default AgentCore Browser is one import, one parameter, and one tool entry. No local Chromium, no Playwright install on your machine, no session management — the infrastructure handles it.

## Common Errors
| Error | Fix |
|-------|-----|
| `AgentCoreBrowser` not found | Check import: `from strands_tools.browser import AgentCoreBrowser` |
| Browser tool fails to start | Confirm `playwright` and `nest-asyncio` are in `requirements.txt` |
| Agent responds without browsing | Make sure `browser.browser` (not `browser`) is in the `tools` list |

---

## Bonus: Use a Custom AgentCore Browser

The default browser is great for getting started, but it does **not** record sessions and does **not** include web bot auth. If you want either of those, create your own browser resource.

### Step 1 — Create an IAM role
Create an IAM role that allows the **Bedrock AgentCore** service to:
- Use the browser feature
- Read/write to the S3 bucket where recordings will be stored

You don't need to build anything beyond this — the role is a one-time setup so AgentCore can host your browser and write recordings.

### Step 2 — Create the browser in the Console
In the AWS Console:

> **Amazon Bedrock → AgentCore → Browser → Create browser**

Configure:
- **Name:** something identifiable (e.g. `wanderbot-browser`)
- **Execution role:** the IAM role from Step 1
- **Recording:** enable, point at your S3 bucket
- **Web bot auth:** enable (reduces CAPTCHA friction on many sites)
- (Optional) **Browser extensions:** attach any you want loaded into the session

Save and copy the **browser identifier**.


Redeploy and invoke as usual. This time, after the session ends, open **AgentCore → Browser → Sessions → Recordings** — the replay is stored in your S3 bucket and is viewable inline in the console.

## Files
| File | Purpose |
|------|---------|
| `starter.py` | Starter agent code — two TODOs |
| `solution.py` | Reference solution — default browser |
| `requirements.txt` | Runtime dependencies, including `playwright` and `nest-asyncio` |
