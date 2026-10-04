# Demo: AgentCore Browser

## Topic
Give WanderBot a managed headless Chrome session so it can browse the live web and return up-to-date destination information.

## Duration
~5 minutes

## What the Demo Shows
- Instantiating `AgentCoreBrowser` and passing it to a Strands `Agent` as a tool
- Setting `session_timeout` on the browser (default is 3600s)
- Watching the browser work in real time via the AgentCore **Live View**
- That browser sessions run **isolated** in AgentCore and can be **taken over** by a human from the Live View

## Architecture

```
WanderBot (Strands Agent)
    ↓  tool call
AgentCoreBrowser  (strands_tools.browser)
    ↓  managed session (default browser)
AWS-hosted headless Chrome
    ↓  navigate / screenshot / extract
en.wikivoyage.org
```

## Dependencies

The Strands browser tool runs on Playwright under the hood. Both of the following must be in `requirements.txt`:

- `playwright`
- `nest-asyncio`

You do not need to import or configure either of these in the agent code — they're runtime dependencies only.

## Key Concepts

| Concept | Description |
|---------|-------------|
| **AgentCoreBrowser** | Managed headless Chrome session exposed as a Strands tool |
| **`browser.browser`** | The tool object to pass to the `Agent` — not the `browser` instance |
| **`session_timeout`** | Max lifetime of the browser session (default 3600s) |
| **Live View** | Console feature that streams the browser session while it's running |
| **Takeover** | From the Live View, a human operator can take control of the browser |
| **Isolation** | Every session runs isolated inside AgentCore — not on your machine |

## Demo Flow (recording)
1. Walk through `demo.py` — import, instantiate with `session_timeout=600`, pass `browser.browser`
2. Call out `playwright` + `nest-asyncio` in `requirements.txt`
3. Deploy with `agentcore configure` + `agentcore deploy`
4. Invoke with a destination question
5. Open the AgentCore Browser → Sessions → **Live View**
6. Talk briefly about isolation + takeover
7. Return to the terminal — agent returns a Wikivoyage-sourced answer

## Talking Points

> "No Playwright install on your machine, no Chromium download — Playwright is a runtime dependency and AgentCore runs the browser in the cloud."

> "Every session is isolated inside AgentCore, and from the Live View you can take over control — useful when the agent hits a login wall or a CAPTCHA."

## Files
| File | Purpose |
|------|---------|
| `demo.py` | Agent code with `AgentCoreBrowser` wired in |
| `requirements.txt` | Runtime dependencies — includes `playwright` and `nest-asyncio` |
