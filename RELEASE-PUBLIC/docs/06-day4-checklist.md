# Day 4 Checklist (AI Bridge + RAG + Safe Commands)

## Day 4 Goal

Enable natural-language interaction safely by deploying:

- n8n (workflow orchestrator)
- Ollama bridge (using your existing install)
- Qdrant (RAG store)
- Command allowlist + confirmation workflow

## Progress Status

- [x] Step 1 scaffold complete: `n8n` deployed and reachable at `http://localhost:5678`
- [x] Step 4 scaffold complete: `qdrant` deployed and API responds at `http://localhost:6333`
- [x] Step 4 baseline check: test collection `day4_test` created and queried
- [x] Step 7 baseline complete: allowlist command runner created with confirmation token + audit log
- [x] Step 2 complete: ntfy inbound/outbound topics wired into n8n workflows (`ai-chat` + `ai-replies`/`ops-commands` -> `ai-replies`/`ops-alerts`)
- [x] Step 3 complete: AI workflow calls Ollama and returns model responses to `ai-replies` (fallback message on model/API failure)
- [x] AI reply tagging in place: both `ai-chat` and RAG query outputs to `ai-replies` set ntfy title `AI Reply` for bridge loop prevention
- [x] Step 5/6 first pass complete: one test source ingested into Qdrant via n8n and `ai-chat` queries return source-cited responses (`Sources: day4-test`)
- [x] Step 8 complete: `ops-audit-review` workflow posts last audit entries to `ops-alerts`, and Homepage links `Guardrail Audit Log`
- [x] Telegram bridge state hardening complete: per-user `tone_history` persists in `telegram_users.json` and is forwarded in webhook payloads
- [x] Routing reliability checks green in current run: `./scripts/telegram-healthcheck.sh` + `./scripts/eval-routing.py`
- [x] Routing regression automation installed: cron + alert wrapper for periodic eval failures
- [x] ntfy dedupe tuning verified: per-topic dedupe windows active for `ops-alerts`/`ops-audit`/`ai-audit`
- [x] Tenant isolation check passed: valid tenant request accepted and cross-tenant query attempt rejected in `rag-query` webhook tests

## Time Budget

- Total: 3 to 6 hours
- Stop point: read-only AI + one safe command with confirmation

## Before You Start

- Confirm snapshot exists: `day3-panel-alerts-stable`
- Take pre-change snapshot: `day4-before-ai`
- Confirm ntfy phone alerts still work

## Step 1 — Deploy n8n

Bring up n8n internally (no public exposure yet).

Minimum Day 4 setup:

- Admin account created
- Basic workflow folder structure created:
  - `01-input`
  - `02-rag`
  - `03-actions`
  - `99-alerts`

Verification:

- n8n UI opens
- You can save and activate a simple test workflow

## Step 2 — Connect n8n to ntfy

Create one inbound and one outbound path.

Inbound intent topics:

- `ai-chat`
- `ai-replies` (direct phone follow-up conversation)
- `ops-commands`

Outbound reply topics:

- `ai-replies`
- `ops-alerts`

Verification:

- Send test text to `ai-chat`
- n8n receives it and posts acknowledgment to `ai-replies`
- Reply from phone in `ai-replies`; bridge forwards only user posts while skipping AI-titled posts (`AI Reply`) to avoid loops

## Step 3 — Connect n8n to Ollama

Use your existing Ollama endpoint and test a single model response.

Minimum behavior:

- Input text from `ai-chat`
- Send to Ollama model
- Return answer to `ai-replies`

Verification:

- One natural-language question gets an AI response to phone
- Timeout and error paths return friendly failure message

## Step 4 — Deploy Qdrant

Bring up Qdrant and verify persistence path.

Verification:

- Qdrant API responds
- Collection can be created and queried
- Data persists after container restart

## Step 5 — Build first RAG ingest workflow

Add one simple ingest source first (choose Wallabag or a test folder).

Minimum ingest pipeline:

1. Receive new document or text
2. Chunk text
3. Create embeddings (via Ollama embedding model)
4. Store vectors + metadata in Qdrant

Metadata required:

- `source_name`
- `source_type`
- `ingest_date`
- `doc_id`

Verification:

- At least one document indexed
- Query returns relevant chunk + metadata

## Step 6 — Build first RAG query workflow

Create query path:

1. Receive user question from `ai-chat`
2. Retrieve top matches from Qdrant
3. Send context + question to Ollama
4. Return answer + source titles to `ai-replies`

Verification:

- Answer includes source names (not just generic text)
- If no match, reply clearly: "No trusted source found"
- Tenant enforcement rejects mismatched tenant IDs for Telegram users

## Step 7 — Add command safety guardrails (critical)

Do not allow raw shell commands.

Create an allowlist with only these actions initially:

- `service_status(<known_service>)`
- `restart_service(<known_service>)`
- `disk_health_summary()`

Safety requirements:

- Unknown command => reject
- High-impact action => require confirmation token
- Every action => log to `ops-alerts`

Verification:

- Allowed action works (example: status check)
- Non-allowlisted command is denied
- Restart command requires confirmation and logs result

## Step 8 — Add audit logging

For each command run, store:

- timestamp
- requester/topic
- action name
- parameters
- outcome

Verification:

- You can review last 10 actions quickly
- Failed actions include reason

## Step 9 — Homepage updates (AI Control section)

Add or update these tiles:

- n8n (Workflows)
- Ollama/OpenWebUI
- Qdrant
- ntfy Topics (quick reference)

Tile labels must include purpose line:

- "n8n — Receives messages and runs approved workflows."
- "Qdrant — Stores searchable knowledge for factual AI responses."

Verification:

- You can navigate AI control tools from one row

## Step 10 — Snapshot and rollback drill

- Take snapshot: `day4-ai-rag-stable`
- Run one rollback drill plan (document only or full test if time)

Verification:

- Snapshot exists
- You have written rollback steps if AI workflows misbehave

## Do Not Do on Day 4

- Do not enable autonomous agent terminal access yet
- Do not permit unrestricted command execution
- Do not expose n8n webhook endpoints publicly
- Do not skip audit logging

## Day 4 Definition of Done

You are done when all are true:

1. n8n receives messages and responds through ntfy
2. Ollama answers natural-language prompts
3. Qdrant stores and retrieves at least one indexed source
4. One safe command runs with explicit confirmation
5. Command/audit logs are visible
6. Snapshot `day4-ai-rag-stable` exists

## Day 5 Preview

Next: media + automation integration

- Plex + Tautulli
- arr stack + Overseerr
- Immich
- Alert and identity integration checks
