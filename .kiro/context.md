# Project context

Labs for the course *Building Agents with Amazon Bedrock AgentCore and Strands
SDK*, course 1 of the AWS AI Agentic Engineer Nanodegree.
Last updated 2026-08-24, at set-up. Nothing built yet.

Read this first, then read the relevant file under `course/` before answering
anything about the course itself -- this file is deliberately short because it
loads on every turn; the knowledge lives in `course/` and is read on demand.

---

## 1. Where things live

| Thing | Location |
| --- | --- |
| Labs (this repo) | `~/Documents/Personal Projects/Building-Agents-with-Amazon-Bedrock-AgentCore-and-Strands-SDK-Labs` |
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

- Record what was *verified* against a real API call or a run, separately from what
  a course page or blog *claimed*. Verified beats documented; documented beats
  remembered. Section 4 of the notes exists for exactly this.
- Record the traps and the dead ends, not just the working answer. The dead end is
  the part that is expensive to rediscover.
- Split into one file per topic only if it becomes unwieldy, and update section 1
  here if that happens.

## 3. Related prior work in this tree

`../Customer-Support-Chatbot-with-Amazon-Bedrock-Flows/.kiro/` covers the same
service family and is in scope from here:

- `agentcore-api-reference.md` -- verified AgentCore API shapes and traps
- `context.md` -- how that project is put together, and what went wrong
- `cost_report.md` -- what the AgentCore work actually cost

Check `agentcore-api-reference.md` before deriving an AgentCore API shape from
scratch.

## 4. AWS

Personal account, Mark's own money. State the cost and get confirmation before
creating any billable resource. Record every long-lived resource in section 5 so a
later session knows it exists and can tear it down.

## 5. Live AWS resources

| Resource | Region | Created | Standing cost | Torn down? |
| --- | --- | --- | --- | --- |
| _none_ | | | | |

## 6. Status

| Item | State |
| --- | --- |
| Git repo | Not initialised |
| Labs | None started |
| `course-notes.md` | Created 2026-08-24, skeleton only. Migrates to Study-Notes at course end |
