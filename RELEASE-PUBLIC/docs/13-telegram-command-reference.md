# Telegram Command Reference (AI Control)

## Purpose

This document is the source of truth for Telegram command behavior in the AI Control stack.
It covers:

- command syntax,
- user/admin permissions,
- safety and approval flow,
- routing behavior,
- payload fields sent to n8n,
- and operator troubleshooting basics.

Status: documentation thread (analysis/design oriented). No implementation changes are required to use this reference.

Navigation: [Incident runbook checks](00-master-runbook.md#incident-ownership--suppression-telegram-admin)

---

## What the Telegram bridge does

High-level flow:

1. Telegram user sends text/photo/audio (or command).
2. `telegram-n8n-bridge` validates account + role + policy checks.
3. Message is routed to n8n webhook:
   - RAG path: `/webhook/rag-query`
   - Ops path: `/webhook/ops-commands-ingest`
4. n8n reply is normalized and sent back to Telegram.
5. Safety/audit systems capture action attempts and outcomes.

---

## Roles and permissions

Policy source note:

- Runtime role-command enforcement is policy-driven via `channels.telegram.role_command_allowlist` in `master-suite/phase1/ai-control/policy/policy.v1.yaml`.
- Command behavior described below is expected to match that allowlist; policy remains the canonical source when differences exist.

### User role

- Can use normal chat/RAG behavior.
- Can use `/memory` commands for personal memory controls.
- Cannot run `/ops` actions.
- Cannot use admin command sets (`/notify` except `/notify me`, `/user`, `/tone`, `/pending`, `/approve`, `/deny`, `/ratelimit`, `/incident`, `/ack`, `/snooze`, `/unsnooze`, `/status`, `/health`).
- Can manage personal profile personalization (`/profile ...`).

### Admin role

- Has all user capabilities.
- Can run `/ops` commands (with approval gate for risky actions).
- Can manage user registry (`/user ...`).
- Can manage notification profile (`/notify ...`).
- Can inspect/reset tone history (`/tone ...`).
- Can inspect rate limiter (`/ratelimit`).
- Can view bridge notification health summary (`/status`, `/health`).
- Can manage pending approvals (`/pending`, `/approve`, `/deny`).
- Can manage incident suppression state (`/incident`, `/ack`, `/snooze`, `/unsnooze`).

### Account state checks

- Unknown account -> registration flow or access denial (depending on policy/state).
- Disabled account -> blocked with `Account disabled` response.
- Incomplete registration -> challenge/registration prompts are shown.

---

## Command quick reference

## Media request quick card

Primary path for Plex additions:

- `/media movie <title> [year]`
- `/media tv <title> [year]`
- `/request ...` (alias of `/media ...`)

Examples:

- `/media movie Dune 2021`
- `/media tv Severance`
- `/request movie Interstellar 2014`

Expected flow:

1. Telegram command is accepted by `telegram-n8n-bridge`.
2. Request is submitted to Overseerr API.
3. Overseerr routes to Radarr/Sonarr.
4. Media pipeline/availability updates are published to `media-alerts`.
5. Telegram fanout sends readiness updates to subscribed users.

Notification notes:

- Active users can receive `media` category notifications.
- Admins can adjust profile with `/notify add media` (or `/notify set ...`).

Operator checks:

- Bridge health: `docker compose ps telegram-n8n-bridge ntfy-n8n-bridge n8n`
- Recent fanout stats:
  - `docker exec ntfy-n8n-bridge python -c "import json; d=json.load(open('/state/telegram_notify_stats.json')); [print(e.get('topic'), e.get('result'), e.get('recipients')) for e in d.get('events',[])[-20:]]"`
- Test media event:
  - `curl -sS -H 'Title: Media Ready Test' -H 'Priority: default' -d 'test media ready' http://127.0.0.1:8091/media-alerts`

If a request command fails:

- Verify `OVERSEERR_URL` and `OVERSEERR_API_KEY` in `ai-control/.env`.
- Recreate bridge services:
  - `docker compose up -d --force-recreate telegram-n8n-bridge ntfy-n8n-bridge`

If readiness alerts do not arrive:

- Confirm user has `media` in `notify_topics` (`telegram_users.json`).
- Check bridge logs for fanout lines/errors:
  - `docker logs --since 30s ntfy-n8n-bridge | grep -E 'telegram fanout topic=media-alerts|bridge error'`

## Core chat commands

- `/start`
  - Shows bridge status and role hint.
- `/rag <message>`
  - Sends message to RAG webhook.
- `/ops <command>`
  - Sends message to Ops webhook (admin only).

### Planned research-report UX (next milestone)

- `/research <query>`
  - Starts asynchronous deep research workflow and returns a tracking id.
- `/research status <id>`
  - Returns generation state (`queued|running|ready|failed`).
- `/research report <id>`
  - Sends a Telegram message containing a Nextcloud download link for the generated report artifact.

Delivery contract notes:

- Report artifacts are uploaded to Nextcloud and delivered as link-only in Telegram.
- Link expiration/size constraints are policy-driven (`channels.telegram.research_report_delivery.*` in `policy.v1.yaml`).

## Identity and diagnostics

- `/whoami`
  - Shows account profile (`user_id`, `role`, `status`, `registration`, `tenant`, name, username).
- `/status` (admin)
  - Shows bridge health summary, active user/admin counts, notification/incident state freshness, and 24h delivery outcomes.
- `/status json` (admin)
  - Returns machine-friendly JSON of the same status snapshot for automation and external checks.
  - Includes deferred digest queue depth and freshness fields (`digest_queue_users`, `digest_queue_items`, `digest_state_updated_at`).
- `/health` (admin)
  - Runs consolidated live checks: bridge snapshot, n8n reachability probe, notify validate probe (`PASS`/`FAIL`), and last fanout age.
- `/health quick` (admin)
  - Runs fast health summary without triggering notify validate publish/fanout probe.
- `/health json` (admin)
  - Returns machine-friendly JSON from the same consolidated health snapshot.
- `/selftest`
  - Runs bridge health checks (account state, RAG webhook, tenant/shared collection checks, ops webhook check for admin).
- `/ratelimit` (admin)
  - Displays current limiter activity report.

## Digest controls (admin)

- `/digest now`
  - Flushes deferred quiet-hours digest queue immediately and returns summary counters (`attempted`, `sent`, `failed`, `remaining`).
- `/digest stats`
  - Shows current digest queue depth, queue freshness, and last flush summary counters.

## Approval workflow (admin)

- `/pending`
  - Lists current pending risky ops approvals with TTL.
- `/approve <id>`
  - Approves and executes pending risky ops request.
- `/deny <id>`
  - Denies pending risky ops request.

## Notification preferences (admin)

- `/notify me` (all users)
  - Shows delivery eligibility for your account, selected topics, quiet-hours effect, quarantine state, and recent delivery failure/sent indicators.
  - Add `json` argument (`/notify me json`) for machine-friendly output of the same self-check snapshot.
- `/notify list`
- `/notify profile`
- `/notify test <critical|ops|audit|ai|media|maintenance>`
- `/notify validate`
- `/notify stats`
- `/notify set <all|none|topic1,topic2>`
- `/notify add <topic1,topic2>`
- `/notify remove <topic1,topic2>`
- `/notify emergency <on|off>`
- `/notify quarantine list`
- `/notify quarantine clear <telegram_user_id>`
- `/notify quarantine clear-all CONFIRM`

Restriction note:

- `/notify quarantine clear-all CONFIRM` is limited to designated security-admin IDs (`TELEGRAM_NOTIFY_QUARANTINE_CLEAR_ALL_ADMINS`, defaulting to `TELEGRAM_BOOTSTRAP_ADMINS`).
- `/notify quiet <off|HH-HH>`

`/notify validate` behavior:

- Publishes a synthetic priority-5 probe to the configured ntfy topic and waits for a correlated fanout event in notify stats state.
- Returns a single `PASS`/`FAIL` summary with stage (`publish`/`wait`/`fanout`), `probe_id`, detail/result, recipients, and latency.
- Useful for fast post-change checks after redeploys, recipient edits, and policy updates.

## Incident ownership controls (admin)

- `/incident list`
- `/incident show <incident_id>`
- `/ack <incident_id>`
- `/snooze <incident_id> <minutes>`
- `/unsnooze <incident_id>`

Suppression behavior:

- Alerts include `Incident ID: INC-...` for command targeting.
- `/ack` suppresses repeated fanout for that incident during the ack TTL window.
- `/snooze` suppresses repeated fanout until the snooze window expires.
- `/unsnooze` clears active snooze immediately.

See also: [Incident runbook checks](00-master-runbook.md#incident-ownership--suppression-telegram-admin)

## User registry management (admin)

- `/user help`
- `/user add <telegram_user_id> <admin|user>`
- `/user role <telegram_user_id> <admin|user>`
- `/user disable <telegram_user_id>`
- `/user enable <telegram_user_id>`
- `/user list`
- `/user linked-discord`

## Memory controls (per user)

- `/memory show`
- `/memory on`
- `/memory off`
- `/memory add <note>`
- `/memory clear`

## Profile controls (per user)

- `/profile show`
- `/profile apply`
- `/profile apply <seed_id>`
- `/profile apply text <profile text>`
- `/profile clear`

Behavior notes:

- `/profile apply` loads a private seed profile for the caller from the configured Discord seed catalog when available.
- `/profile apply <seed_id>` applies a specific profile seed entry from the Discord seed catalog.
- `/profile apply text ...` sets a manual profile seed for the caller.
- `/profile clear` disables and removes stored profile personalization fields.
- Discord/profile-data questions can return quick suggestions with direct `/profile apply <seed_id>` commands when no seed is active.

## Discord identity link controls (per user)

- `/discord show`
- `/discord link`
- `/discord link <discord_name_or_handle>`
- `/discord unlink`

Behavior notes:

- `/discord link` starts an interactive prompt asking for Discord account name/handle.
- The bridge matches this against the local Discord seed catalog and ties Telegram + Discord identities.
- On successful link, matched private profile seed/image fields are applied to Telegram personalization payloads.
- `/discord show` displays current linked Discord identity metadata.

## Tone controls (admin)

- `/tone show <telegram_user_id>`
- `/tone reset <telegram_user_id>`

---

## Message routing behavior

Mode selection:

- Explicit `/ops ...` -> ops mode.
- Explicit `/rag ...` -> rag mode.
- No explicit mode -> uses `TELEGRAM_DEFAULT_MODE` (`rag` by default).

Content accepted:

- text,
- photo (forwarded as `image_url`),
- voice/audio (forwarded as `audio_url` and metadata).

Short input guard:

- Very short text messages are rejected with a prompt for more detail.
- Threshold is controlled by `TELEGRAM_SHORT_INPUT_MIN_CHARS` (default: `3`).

Unknown slash commands:

- Unknown `/...` commands receive a help-style fallback message.

---

## Risky ops approval model

Risk trigger:

- `/ops` messages matching risky action keywords are put into pending approval instead of immediate execution.
- Typical risky patterns include terms like `restart`, `stop`, `shutdown`, `reboot`, `delete`, `remove`, `update`, `restore`, `deploy`, etc.

Approval lifecycle:

1. Requester sends risky `/ops` command.
2. Bridge creates pending approval with unique `id` and expiry.
3. Admin approves with `/approve <id>` or denies with `/deny <id>`.
4. On approval, bridge executes ops webhook payload and notifies both admin/requester.
5. Expired approvals are auto-pruned.

TTL:

- Controlled by `TELEGRAM_APPROVAL_TTL_SECONDS` (default in code: `300`).

---

## Tenant and identity model

Tenant convention:

- Tenant id is derived per Telegram user as `u_<telegram_user_id>`.

Payload identity fields:

- `user_id`, `role`, `tenant_id`, `full_name`, `telegram_username`.

Expected behavior:

- Requests should remain tenant-scoped.
- Cross-tenant attempts should be denied by workflow policy.
- Security denials can surface in audit/alert channels (for example `TENANT_SCOPE_DENIED`).

---

## Memory and tone capabilities

### Memory

- Per-user memory can be enabled/disabled.
- Users can store short notes used as optional context in requests.
- Retention and size limits are policy-controlled:
  - `TELEGRAM_MEMORY_TTL_DAYS` (default: `30`)
  - `TELEGRAM_MEMORY_MAX_ITEMS` (default: `20`)
  - `TELEGRAM_MEMORY_MAX_CHARS` (default: `1200`)

### Tone smoothing

- Tone tags (`warm`, `neutral`, `concise`) can be extracted from replies.
- Last 3 tones are retained in user registry as `tone_history`.
- Admins can inspect and reset tone history with `/tone` commands.

---

## Notification policy capabilities

`/notify` commands change admin notification preferences stored in registry.

Policy controls include:

- notifications on/off,
- critical-only mode,
- minimum priority threshold,
- message length cap,
- dedupe window (global + per-topic overrides),
- drop patterns.

`/notify profile` shows loaded policy details including dedupe and drop pattern values.

Incident suppression state is shared through the bridge state volume so admin commands can update fanout behavior in real time.

Quiet-hours deferred digest:

- Set per-admin quiet window with `/notify quiet 22-07` (UTC hours).
- Disable quiet mode with `/notify quiet off`.
- Non-critical alerts are queued during quiet hours and sent later as a digest.
- Critical alerts still deliver immediately.
- Deferred queue flushes automatically once quiet hours end while bridge polling is active.

---

## Registration behavior

For new users, bridge may run a registration flow:

1. Prompt for full name.
2. Assign default role (`user`) and activate account.
3. Optional admin challenge flow can elevate a specific user profile to admin after challenge answers.

Notes:

- Access policy can be constrained by `TELEGRAM_ALLOWED_USER_IDS`.
- Admin bootstrap IDs can be seeded with `TELEGRAM_BOOTSTRAP_ADMINS`.

---

## Webhook payload contract (Telegram -> n8n)

Primary fields:

- `source` (`telegram`)
- `chat_id`
- `user_id`
- `role`
- `tenant_id`
- `full_name`
- `telegram_username`
- `message`
- `image_url`, `has_image`
- `audio_url`, `audio_kind`, `audio_mime`, `audio_duration`, `audio_file_id`, `audio_file_name`, `has_audio`
- `memory_enabled`, `memory_summary`
- `tone_history`
- `user_profile_seed`, `user_profile_image_url`
- `timestamp`

---

## Key configuration variables

Minimum required:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_USER_IDS` (recommended for restricted access)

Common routing/config:

- `TELEGRAM_DEFAULT_MODE` (default `rag`)
- `N8N_RAG_WEBHOOK` (default `/webhook/rag-query`)
- `N8N_OPS_WEBHOOK` (default `/webhook/ops-commands-ingest`)
- `TELEGRAM_REPLY_SHOW_SOURCES` (default `false`)
- `TELEGRAM_REPLY_MAX_CHARS` (default `1800`)

Safety and anti-abuse:

- `TELEGRAM_RATE_LIMIT_WINDOW_SECONDS` (default `30`)
- `TELEGRAM_RATE_LIMIT_MAX_REQUESTS` (default `6`)
- `TELEGRAM_SHORT_INPUT_MIN_CHARS` (default `3`)
- `TELEGRAM_APPROVAL_TTL_SECONDS` (default `300`)

Notification policy:

- `TELEGRAM_NOTIFICATIONS_ENABLED`
- `TELEGRAM_NOTIFY_CRITICAL_ONLY`
- `TELEGRAM_NOTIFY_MIN_PRIORITY`
- `TELEGRAM_NOTIFY_MAX_MESSAGE_CHARS`
- `TELEGRAM_NOTIFY_DROP_PATTERNS`
- `TELEGRAM_DEDUPE_WINDOW_SECONDS`
- `TELEGRAM_DEDUPE_WINDOW_SECONDS_BY_TOPIC`
- `NTFY_PUBLISH_BASE` (bridge-local ntfy publish endpoint for `/notify validate`, default `http://ntfy`)
- `TELEGRAM_NOTIFY_VALIDATE_TOPIC` (probe publish topic, default `ops-validate`)
- `TELEGRAM_NOTIFY_VALIDATE_TIMEOUT_SECONDS` (default `20`)
- `TELEGRAM_NOTIFY_VALIDATE_POLL_SECONDS` (default `1.0`)
- `TELEGRAM_NOTIFY_VALIDATE_PUBLISH_FALLBACKS` (comma-separated fallback bases, default `http://ntfy:80,http://127.0.0.1:8091`)
- `TELEGRAM_NOTIFY_STATS_SQLITE_PATH` (optional override for sqlite-backed notify stats, default sibling `telegram_state.db` next to `TELEGRAM_NOTIFY_STATS_STATE`)

Notification delivery reliability:

- `TELEGRAM_SEND_MAX_RETRIES`
- `TELEGRAM_SEND_BACKOFF_SECONDS`
- `TELEGRAM_SEND_BACKOFF_MAX_SECONDS`

Quiet-hours + deferred digest policy:

- `TELEGRAM_QUIET_HOURS_UTC_OFFSET_HOURS`
- `TELEGRAM_DIGEST_MAX_ITEMS_PER_USER`
- `TELEGRAM_DIGEST_LINE_MAX_CHARS`

Incident suppression policy:

- `TELEGRAM_INCIDENT_ACK_TTL_SECONDS`
- `TELEGRAM_INCIDENT_RETENTION_SECONDS`
- `TELEGRAM_INCIDENT_LIST_LIMIT`

Memory policy:

- `TELEGRAM_MEMORY_ENABLED_BY_DEFAULT`
- `TELEGRAM_MEMORY_TTL_DAYS`
- `TELEGRAM_MEMORY_MAX_ITEMS`
- `TELEGRAM_MEMORY_MAX_CHARS`

Profile personalization policy:

- `TELEGRAM_PROFILE_SEED_PATH`
- `TELEGRAM_PROFILE_MAX_CHARS`
- `TELEGRAM_PROFILE_PREVIEW_CHARS`

---

## Operator troubleshooting (basic)

Health and connectivity checks:

1. Verify bridge container is running.
1. Run Telegram health script (`scripts/telegram-healthcheck.sh`).
1. Confirm n8n webhook endpoints respond.
1. Check user registry state in `telegram_users.json`.
1. Check alert/audit topics for policy denials or routing errors.
1. Verify profile command telemetry events in bridge logs: `docker logs --since 5m telegram-n8n-bridge | grep -E 'profile_action user_id='`
1. Run Telegram/chat smoke checks: `/usr/bin/python3 ./scripts/eval-telegram-chat-smoke.py`, `./scripts/run-telegram-chat-smoke-and-alert.sh`, `./scripts/install-telegram-chat-smoke-cron.sh`, `./scripts/uninstall-telegram-chat-smoke-cron.sh`
1. In Telegram (admin), run `/status` to verify delivery outcomes and state freshness.
1. In Telegram (admin), configure quiet hours and verify: `/notify quiet 22-07` and `/notify profile`.
1. In Telegram (admin), force digest flush when needed: `/digest now` and `/digest stats`.

Common symptom map:

- `Access denied` -> user missing from allowed list/registry.
- `Account disabled` -> admin must re-enable user.
- `/ops is admin-only` -> user role is not admin.
- `No pending approval with id` -> expired/invalid approval id.
- frequent `Too many requests` -> adjust request burst behavior or limiter settings.

---

## Related documents

- [00-master-runbook.md](00-master-runbook.md)
- [06-day4-checklist.md](06-day4-checklist.md)
- [12-discord-bot-expansion.md](12-discord-bot-expansion.md)
- [master-suite/phase1/ai-control/README.md](../master-suite/phase1/ai-control/README.md)
