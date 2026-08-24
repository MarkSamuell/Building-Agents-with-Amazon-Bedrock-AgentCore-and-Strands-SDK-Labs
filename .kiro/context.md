# Project context

Labs for the course *Building Agents with Amazon Bedrock AgentCore and Strands
SDK*, course 1 of the AWS AI Agentic Engineer Nanodegree.
Last updated 2026-08-24, at set-up. Nothing built yet.

Read this first, then read `.kiro/course-notes.md` before answering anything about
the course itself -- this file is deliberately short because it loads on every
turn; the course knowledge lives in `course-notes.md` and is read on demand.

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

**Vocareum lab account `484086766087`** -- the course VM authenticates as
`assumed-role/voclabs` using temporary STS credentials. Anything deployed from
inside the lab bills to Vocareum's budget, not Mark's. Those credentials expire:
when they do, calls fail with `ExpiredToken`, and the session token must be
refreshed from the classroom and re-applied with
`aws configure set aws_session_token`. Adding credentials is always Mark's action.

**Mark's personal account** -- reachable only from a session on his own machine
through `~/.aws-personal/`. His own money, so state the cost and get confirmation
before creating any billable resource, and record every long-lived resource in
section 5 so a later session knows to tear it down.

## 5. Live AWS resources

| Resource | Region | Created | Standing cost | Torn down? |
| --- | --- | --- | --- | --- |
| WanderBot deploy scaffolding in **Vocareum account 484086766087**: ECR repo `bedrock-agentcore-wanderbot`, S3 bucket `bedrock-agentcore-codebuild-sources-484086766087-us-east-1`, IAM roles `AmazonBedrockAgentCoreSDKRuntime-us-east-1-a25b0cb827` and `...CodeBuild-us-east-1-a25b0cb827`, CodeBuild project `bedrock-agentcore-wanderbot-builder` | us-east-1 | 2026-08-24 | None to Mark -- lab account pays, and it goes when the lab does | n/a |

## 6. Status

| Item | State |
| --- | --- |
| Git repo | Initialised 2026-08-24, branch `main`, root commit `3d1a46a`. No remote -- pushing is Mark's action |
| Labs | None started |
| `course-notes.md` | Module 1 intro written 2026-08-24: why a framework, the three layers, the agent loop. Migrates to Study-Notes at course end |
