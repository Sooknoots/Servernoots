# AI Control (Phase 1 Day 4 scaffold)

**Public Release Notice:**
This is a public release. All secrets, tokens, and user-specific data have been removed. You must generate your own credentials and configuration. See INSTALLATION.md for details.

## Docs navigation

- Operator runbook: [`docs/00-master-runbook.md`](../../../docs/00-master-runbook.md)
- 24h textbook download verification: [`docs/00-master-runbook.md#textbook-hosted-download-links-24h-ttl--live-verification`](../../../docs/00-master-runbook.md#textbook-hosted-download-links-24h-ttl--live-verification)

## What this stack includes

- `n8n` (workflow orchestrator)
- `qdrant` (vector database)
- `ollama-loopback-proxy` (host-loopback bridge for Ollama API)
- `openwhisper` (local OpenAI-compatible voice transcription API)
- `guardrails/safe_command.sh` (strict allowlist command runner)

## Policy-as-config runtime file

- Canonical runtime policy artifact: `policy/policy.v1.yaml`
- Current wired consumers:
  - Shared parser module: `bridge/policy_loader.py` (single policy parsing implementation for bridge services).
  - Shared shell extractor: `policy/policy_extract.sh` (single policy extraction implementation for shell guardrail consumers).
  - `guardrails/safe_command.sh` reads `commands.allowlist.services` via `policy/policy_extract.sh` when `POLICY_FILE` is present (fallback: `guardrails/allowed-services.txt`).
  - `bridge/ntfy_to_n8n.py` applies `alerts.required_topics` and `alerts.topic_categories` to Telegram fanout topic controls.
  - `bridge/telegram_to_n8n.py` applies `channels.telegram.default_admin_notify_topics`, `channels.telegram.topic_labels`, dedupe windows, `approval.default_ttl_seconds`, `approval.max_pending_per_user`, and `rate_limit.default.requests_per_minute` + `rate_limit.burst` from policy.
  - `scripts/discord-rag-proxy.py` + `scripts/discord-rag-proxy-server.py` apply policy-backed defaults for `rate_limit.voice_session_cooldown_seconds` and Discord memory payload gates (`memory.*`, `retention.raw_audio_persist`) via shared loader.
- Container policy mounts in this compose stack:
  - `n8n` uses `POLICY_FILE=/opt/policy/policy.v1.yaml`
  - `ntfy-n8n-bridge` uses `POLICY_FILE=/app/policy/policy.v1.yaml`
  - `telegram-n8n-bridge` uses `POLICY_FILE=/app/policy/policy.v1.yaml`

## Start

- `cd $INSTALL_DIR/master-suite/phase1/ai-control`
- `cp .env.example .env`
- `cp .env.secrets.example .env.secrets`
- Fill secrets in `.env.secrets` (keep `.env` for non-secret config)
- `chmod 600 .env .env.secrets`
- `./scripts/dc up -d`

Secrets handling (recommended):

- Use `./scripts/dc ...` instead of raw `docker compose ...`.
- `./scripts/dc` automatically layers `--env-file .env --env-file .env.secrets` when `.env.secrets` exists.
- This keeps sensitive values out of the main `.env` and out of git (`.env`, `.env.secrets`, `.env.local` are ignored).

## Telegram bridge (optional, recommended for remote chat)

Set these in `.env` before starting compose:

- `cp .env.example .env`
- edit `.env` with real Telegram values

- `TELEGRAM_BOT_TOKEN=<your_bot_token>`
- `TELEGRAM_ALLOWED_USER_IDS=<comma-separated Telegram numeric user IDs>`
- `OVERSEERR_URL=http://host.docker.internal:5055`
- `OVERSEERR_API_KEY=<overseerr_api_key>`
- `TELEGRAM_MEDIA_READY_GATE_ENABLED=true`
- `TELEGRAM_MEDIA_READY_STATUS_REQUIRED=5`
- `TELEGRAM_MEDIA_FIRST_SEEN_ONLY_ENABLED=true`
- `TELEGRAM_MEDIA_FIRST_SEEN_RETENTION_SECONDS=31536000`
- `TELEGRAM_STATE_BACKEND=json` (set `sqlite` to enable DB-backed runtime state)
- `TELEGRAM_STATE_SQLITE_PATH=/state/telegram_state.db`
- `TELEGRAM_DEFAULT_ADMIN_NOTIFY_TOPICS=critical,ops,audit`
- `TELEGRAM_EMERGENCY_ADMIN_USERNAMES=<your_admin_username>` (replace with your Telegram username)
- `N8N_TEXTBOOK_WEBHOOK=/webhook/textbook-fulfillment`
- `TELEGRAM_TEXTBOOK_REQUEST_TTL_SECONDS=1800`
- `TELEGRAM_TEXTBOOK_COVER_PREVIEW_ENABLED=true` (set `false` to disable inline Telegram image previews while keeping cover links in text)
- `TEXTBOOK_SMTP_HOST=<smtp_host>` (optional, enables bridge-side email dispatch)
- `TEXTBOOK_SMTP_PORT=587`
- `TEXTBOOK_SMTP_USER=<smtp_user>`
- `TEXTBOOK_SMTP_PASSWORD=<smtp_password>`
- `TEXTBOOK_SMTP_FROM=<from_email>`
- `TEXTBOOK_SMTP_USE_SSL=false`
- `TEXTBOOK_SMTP_USE_STARTTLS=true`
- `TEXTBOOK_SEARCH_PROVIDERS=googlebooks,openlibrary,internetarchive,gutendex`
- `TEXTBOOK_ENFORCE_FILE_DOMAIN_ALLOWLIST=true`
- `TEXTBOOK_ALLOWED_FILE_DOMAINS=example.edu,books.google.com,openlibrary.org,archive.org,gutenberg.org,www.gutenberg.org,*.edu,*.gov`
- `TEXTBOOK_DOWNLOAD_LINK_ENABLED=true` (host and issue bridge-managed download links)
- `TELEGRAM_TEXTBOOK_DOWNLOAD_HOST_PORT=8113` (host port for download service)
- `TEXTBOOK_DOWNLOAD_PUBLIC_BASE_URL=http://127.0.0.1:8113` (base URL users will receive)
- `TEXTBOOK_DOWNLOAD_TTL_SECONDS=86400` (24h link lifetime)
- `TEXTBOOK_DOWNLOAD_MAX_BYTES=52428800` (max fetch/cache size per file)
- Runbook live verification (200 -> 410 proof): [`docs/00-master-runbook.md#textbook-hosted-download-links-24h-ttl--live-verification`](../../../docs/00-master-runbook.md#textbook-hosted-download-links-24h-ttl--live-verification)
- `TELEGRAM_WORKSPACE_TTL_SECONDS=86400`
- `TELEGRAM_WORKSPACE_CLEANUP_INTERVAL_SECONDS=300`
- `TELEGRAM_WORKSPACE_MAX_DOCS=8`
- `TELEGRAM_MEMORY_CONFLICT_REQUIRE_CONFIRMATION=true` (withhold unresolved conflicting notes from retrieval until `/memory resolve`)
- `TELEGRAM_MEMORY_CONFLICT_PROMPT_ENABLED=true` (append conflict-resolution reminder in memory summary)
- `TELEGRAM_MEMORY_CONFLICT_REMINDER_ENABLED=true` + `TELEGRAM_MEMORY_CONFLICT_REMINDER_SECONDS=21600` (flag unresolved conflicts as stale for operator follow-up)
- `TELEGRAM_MEMORY_INTENT_SCOPE_ENABLED=true` (scope memory retrieval by inferred query intent: `style|media|identity|ops`)
- `TELEGRAM_MEMORY_CANARY_ENABLED=false` (enable cohort rollout mode for Memory v2 behavior)
- `TELEGRAM_MEMORY_CANARY_PERCENT=100` (percent cohort when canary mode is enabled)
- `TELEGRAM_MEMORY_CANARY_INCLUDE_USER_IDS=<csv>` / `TELEGRAM_MEMORY_CANARY_EXCLUDE_USER_IDS=<csv>` (deterministic override lists)
- `TELEGRAM_MEMORY_FEEDBACK_RANKING_ENABLED=true` (apply correction/approval feedback signals to memory ranking multipliers)
- `TELEGRAM_MEMORY_TELEMETRY_ENABLED=true` (emit structured memory telemetry events)
- `TELEGRAM_MEMORY_TELEMETRY_PATH=/state/telegram_memory_telemetry.jsonl` (JSONL sink for memory telemetry)
- `TELEGRAM_CHILD_GUARDRAILS_ENABLED=true` (enforce child-account media/content guardrails)
- `TELEGRAM_CHILD_ACCOUNT_ADULT_MIN_AGE=18` (age threshold for Adult vs Child account class)
- `TELEGRAM_CHILD_MEDIA_ALLOWED_RATINGS=G,PG,TV-Y,TV-Y7,TV-G,TV-PG` (rating allowlist for Child accounts)
- `TELEGRAM_CHILD_MEDIA_ALLOWED_RATINGS_UNDER_13=...` / `TELEGRAM_CHILD_MEDIA_ALLOWED_RATINGS_13_15=...` / `TELEGRAM_CHILD_MEDIA_ALLOWED_RATINGS_16_17=...` (age-band rating allowlists for under-18 accounts)
- `TELEGRAM_CHILD_MEDIA_DENY_UNKNOWN_RATINGS=true` (block media with missing/unknown ratings for Child accounts)
- `TELEGRAM_CHILD_MEDIA_BLOCK_IF_ADULT_FLAG=true` (block titles marked adult in provider metadata)
- `TELEGRAM_CHILD_MEDIA_BLOCKED_GENRE_IDS=27` (TMDB/Overseerr genre IDs to block for Child accounts; default blocks Horror)
- `TELEGRAM_CHILD_MEDIA_BLOCKED_KEYWORDS=...` (VidAngel-style sensitive descriptor guardrails: sexual content, violence/gore, profanity, substance use, self-harm, disturbing themes)
- Memory v2 quick verify:
  - `PYTHONPATH=/media/sook/Content/Servernoots/master-suite/phase1/ai-control/bridge /usr/bin/python3 scripts/eval-telegram-chat-smoke.py --mode local --check memory_regression_local --check memory_tier_decay_order_local --check memory_intent_scope_local`
- Memory canary controls quick verify:
  - `PYTHONPATH=/media/sook/Content/Servernoots/master-suite/phase1/ai-control/bridge /usr/bin/python3 scripts/eval-telegram-chat-smoke.py --mode local --check memory_canary_controls_local`
- Memory conflict workflow quick verify:
  - `PYTHONPATH=/media/sook/Content/Servernoots/master-suite/phase1/ai-control/bridge /usr/bin/python3 scripts/eval-telegram-chat-smoke.py --mode local --check memory_conflict_workflow_local`
- Memory feedback ranking quick verify:
  - `PYTHONPATH=$INSTALL_DIR/master-suite/phase1/ai-control/bridge /usr/bin/python3 scripts/eval-telegram-chat-smoke.py --mode local --check memory_feedback_ranking_local`
- Memory telemetry quick inspect:
  - `docker exec telegram-n8n-bridge sh -lc 'tail -n 20 /state/telegram_memory_telemetry.jsonl'`
- `OPENWHISPER_MODEL=small`
- `OPENWHISPER_DEVICE=cpu`
- `OPENWHISPER_COMPUTE_TYPE=int8`
- `OPENWHISPER_BEAM_SIZE=1`
- `STT_BASE_URL=http://openwhisper:9000`
- `STT_TRANSCRIPT_PATH=/v1/audio/transcriptions`
- `STT_MODEL=whisper-1`
- `STT_DEBUG_RESPONSE_ENABLED=false` (when true, Telegram webhook replies include `debug.stt` diagnostics)
- `NTFY_BASE=http://ntfy` (base URL for n8n workflow ntfy HTTP nodes)
- `NTFY_ALERT_TOPIC=ops-alerts` (ops/admin alert topic used by workflow alert posts)
- `NTFY_REPLIES_TOPIC=ai-replies` (AI reply topic used by workflow reply posts)
- `NTFY_AUDIT_TOPIC=ai-audit` (audit topic used by workflow audit posts)

Ops-alerts evidence automation:

- One-shot evidence capture:
  - `make ops-alerts-evidence`
  - `make ops-alerts-evidence-status`
- Install daily cron automation (recommended):
  - `make install-ops-alerts-evidence-cron`
  - default schedule: `50 6 * * *`
  - override schedule: `OPS_ALERTS_EVIDENCE_CRON_SCHEDULE='50 6 * * *' make install-ops-alerts-evidence-cron`
- Remove cron automation:
  - `make uninstall-ops-alerts-evidence-cron`

## Desktop dictate button (WhisperTalk-style)

If your hands are tired and you want a press-to-record workflow that inserts text where your cursor is focused:

- Script: `scripts/dictate-button.py`
- What it does: `Record -> Stop -> Transcribe via OpenWhisper -> insert at current cursor`.
- Audio devices: by default, it uses your system default microphone and speakers.
  - Input priority: Pulse/PipeWire default source via `parec` (if available), then ALSA default via `arecord`.
  - Output cues: start/stop sounds are sent to default system sink when supported.
- Primary insert backends:
  - X11: `xdotool`
  - Wayland: `wtype`
  - Fallback: clipboard (`wl-copy` or `xclip`) with auto-paste attempt (`Ctrl+V`/`Ctrl+Shift+V`)

Install minimal local dependencies (Ubuntu/Debian):

- `sudo apt update && sudo apt install -y alsa-utils xdotool xclip`
- Optional Wayland typing backend: `sudo apt install -y wtype wl-clipboard`
- Hold-to-talk hotkey backend (X11): `sudo apt install -y xbindkeys`

Run from `master-suite/phase1/ai-control`:

- `python3 scripts/dictate-button.py`

Global hotkey mode (WhisperTalk-like):

- Toggle command (press once to start recording, press again to stop + transcribe + insert):
  - `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control && python3 scripts/dictate-button.py --toggle`
- Hold-to-talk commands:
  - key-down: `python3 scripts/dictate-button.py --start`
  - key-up: `python3 scripts/dictate-button.py --stop`
- One-command hold setup (`Super+Alt+Z` press/release) on X11:
  - `./scripts/setup-dictate-hold-hotkey.sh`
  - This installs/updates `~/.xbindkeysrc` entries and reloads `xbindkeys`.
- Suggested binding: `Ctrl+Super` to that command in your desktop keyboard shortcuts.

GNOME quick bind example:

- `gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "['/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/dictate/']"`
- `gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/dictate/ name 'Dictate Toggle'`
- `gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/dictate/ command 'bash -lc "cd $INSTALL_DIR/master-suite/phase1/ai-control && python3 scripts/dictate-button.py --toggle"'`
- `gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/dictate/ binding '<Ctrl><Super>d'`

Notes for shortcut mode:

- You can change `'<Ctrl><Super>d'` to any open combo your DE accepts.
- The script uses desktop notifications (`notify-send`) to show start/stop status when available.
- Keep your target text box focused before the second press so insertion lands at cursor.
- GNOME custom keybindings do not support key-release events; use `xbindkeys` hold mode for true press-and-hold behavior.
- True hold mode is currently X11-focused. Wayland often restricts global key release capture by design.

Options:

- `--endpoint http://127.0.0.1:9001/v1/audio/transcriptions`
- `--insert-mode auto|x11|wayland|clipboard`
- `--arecord-device <alsa_device_name>`
- `--min-seconds 0.35` (minimum captured duration before STT)
- `--min-rms 80` (minimum loudness before STT)
- `--no-audio-cues` (disable speaker cues)

Troubleshooting capture status:

- `Recording too short`: hold/talk longer before stop.
- `Captured silence / mic input too low`: mic source is wrong or gain is too low.
- `No speech detected`: audio reached STT but spoken content was not recognized.
- `Copied transcript to clipboard (paste manually)`: typing/paste backend was unavailable; transcript is in clipboard.

Notes:

- Default endpoint resolves to `http://127.0.0.1:${OPENWHISPER_HOST_PORT:-9001}/v1/audio/transcriptions`.
- Keep the target app text box focused when you stop recording so insertion lands at your cursor.

Local SMTP service (Mailpit, included in this compose stack):

- Default local SMTP relay host: `mailpit:1025`
- Local inbox UI: `http://127.0.0.1:8025`
- For local Mailpit, keep `TEXTBOOK_SMTP_USE_SSL=false` and `TEXTBOOK_SMTP_USE_STARTTLS=false`
- One-command SMTP healthcheck: `./scripts/smtpcheck`

Switch SMTP providers (real inbox delivery):

- One-command provider switcher (updates `.env`, backs up previous file, recreates `telegram-n8n-bridge`):
  - `./scripts/smtp-provider-switch.sh --provider gmail --user you@gmail.com --from you@gmail.com --password '<gmail_app_password>'`
- Supported provider presets: `mailpit`, `gmail`, `sendgrid`, `brevo`, `mailgun`, `postmark`, `ses`, `custom`
- SendGrid example:
  - `./scripts/smtp-provider-switch.sh --provider sendgrid --from verified@yourdomain.tld --password '<sendgrid_api_key>'`
- Return to local Mailpit mode:
  - `./scripts/smtp-provider-switch.sh --provider mailpit`

Nextcloud (self-hosted textbook/file links):

- Start Nextcloud stack:
  - `docker compose up -d nextcloud-db nextcloud`
- Open web UI:
  - `http://127.0.0.1:${NEXTCLOUD_HOST_PORT:-8085}`
- Default bootstrap creds come from `.env`:
  - `NEXTCLOUD_ADMIN_USER`
  - `NEXTCLOUD_ADMIN_PASSWORD`
- Change `NEXTCLOUD_DB_PASSWORD` and `NEXTCLOUD_ADMIN_PASSWORD` from defaults before production use.
- If you serve Nextcloud via domain/reverse proxy, set:
  - `NEXTCLOUD_TRUSTED_DOMAINS`
  - `NEXTCLOUD_OVERWRITEHOST`
  - `NEXTCLOUD_OVERWRITEPROTOCOL`
- For textbook delivery links, keep domain allowlist updated in `.env`:
  - `TEXTBOOK_ALLOWED_FILE_DOMAINS=...,<your-nextcloud-domain>`

Behavior:

- `/media <movie|tv> <title> [year]` (or `/request ...`) submits request to Overseerr; Overseerr then hands off to Radarr/Sonarr
- onboarding now includes age capture (Step 2/2) and assigns account class (`Adult` or `Child`)
- users can review/update age class with `/profile age show|set <years>|clear`
- Child accounts apply stricter media guardrails: only configured allowed ratings are shown/requestable (VidAngel-style convention mapping)
- if multiple matches are found, bridge requires explicit confirmation with `/media pick <1-3>` before submission
- `/textbook request <details>` starts lawful textbook fulfillment flow (official sources only)
- `/textbook` flow searches candidate textbooks from configurable legal catalogs (default: Google Books + OpenLibrary + Internet Archive + Gutendex), supports `/textbook pick <1-3>`, then requires explicit confirmation before dispatch to `N8N_TEXTBOOK_WEBHOOK`
- inline textbook cover photo previews are controlled by `TELEGRAM_TEXTBOOK_COVER_PREVIEW_ENABLED` (links are still shown in text when disabled)
- after fulfillment confirms an emailable file candidate, bot prompts consent for memory/RAG ingestion (`/textbook ingest yes|no`)
- `/textbook resend` retries email dispatch for the last fulfillment using recorded file URL and destination email
- textbook dispatch now hosts source files behind a temporary bridge URL and sends that hosted link
- hosted textbook links expire automatically after `TEXTBOOK_DOWNLOAD_TTL_SECONDS` (default 24h)
- `/textbook delivered` marks last fulfillment as user-confirmed delivered
- `/textbook failed <reason>` marks last fulfillment as user-reported failed and stores the reason
- textbook fulfillment now returns explicit lifecycle fields: `fulfillment_id`, `delivery_status`, `delivery_mode`, and `status_timeline`
- `/textbook status` now shows latest fulfillment lifecycle metadata when there is no pending request
- when a deliverable file is available and SMTP is configured, bridge dispatches an email link and updates lifecycle to `email_dispatched`; otherwise status is `dispatch_skipped_not_configured` or `dispatch_failed`
- bridge enforces optional file URL domain allowlisting before dispatch (status `dispatch_failed_untrusted_source` on deny)
- repeated `/textbook confirm` for the same `fulfillment_id` is idempotent (no duplicate email send)
- ingestion is only executed after explicit user opt-in and uses `N8N_RAG_INGEST_WEBHOOK` (default `/webhook/rag-ingest`)
- when a file URL is available, ingest attempts file-first text extraction (text/markdown/html/json + epub, and pdf via parser when available), then falls back to validation summary text
- telegram bridge now uses a deterministic custom image build (`bridge/Dockerfile.telegram`) with pinned dependency `pypdf==4.3.1` for PDF extraction
- dependency install is hash-locked (`--require-hashes`) via `bridge/requirements-telegram.txt` for stronger supply-chain reproducibility
- user can save delivery email with `/textbook email <address>` (also persisted as user memory note)
- `/workspace create <name>` creates a temporary private knowledge workspace (default TTL: 24h)
- `/workspace add <url-or-text>` ingests temporary manual/product context into private RAG with `source_type=workspace_temp`
- `/workspace mode <auto|workspace|memory|status>` controls retrieval context for chat queries
  - `workspace` disables long-term memory context for query payloads
  - `memory` prioritizes long-term memory context (workspace metadata still attached)
  - `auto` keeps default mixed behavior with workspace metadata hints
- `/workspace status` shows active workspace metadata and remaining TTL
- `/workspace close` immediately removes active workspace docs from tenant Qdrant and clears workspace state
- expired workspaces are auto-cleaned in bridge polling loop; matching temporary docs are deleted by `doc_id`
- `/rag <message>` routes to `N8N_RAG_WEBHOOK` (default `/webhook/rag-query`)
- `/ops <command>` routes to `N8N_OPS_WEBHOOK` (default `/webhook/ops-commands-ingest`)

Textbook workflow deployment note:

- Preferred one-command path:
  - `./scripts/publish-textbook-workflow.sh --verify`
- Fast verify-only path (no import/publish/restart):
  - `./scripts/verify-textbook-webhook.sh`

- Importing `workflows/textbook-fulfillment-webhook.json` creates the workflow in `inactive` state by default.
- Publishing with `n8n publish:workflow --id <workflow_id>` is required to register production webhook paths.
- When using the n8n CLI inside a running container, restart n8n after publish so webhook registration takes effect:
  - `docker compose restart n8n`
- Quick verify:
  - `curl -sS -H 'Content-Type: application/json' -d '{"textbook_request":"test","delivery_email":"x@y.z","lawful_sources_only":true,"user_id":"1"}' http://127.0.0.1:5678/webhook/textbook-fulfillment`
- If webhook is not active, n8n returns `404` with `The requested webhook "POST textbook-fulfillment" is not registered.`
- Coding help requests are allowed for `admin` role accounts only; non-admin users are redirected to non-coding support (runbook/docs, media, weather, general Q&A)
- Non-admin users can request coding help with `/coding on`; the request is sent to active admins for `/approve <id>` or `/deny <id>`
- Coding access approve/deny decisions are audit logged to `/state/telegram_coding_access_audit.jsonl` (override with `TELEGRAM_CODING_ACCESS_AUDIT`)
- Admins can review latest coding access decisions with `/coding audit <n>`
- Plain text follows `TELEGRAM_DEFAULT_MODE` (default `rag`)
- Photo messages are forwarded with `image_url` so workflows can do vision handling
- Voice notes and audio files are forwarded with `audio_url` so workflows can transcribe and answer
- Admins can customize Telegram alert feed with `/notify` commands (`list`, `set`, `add`, `remove`)
- Admins can opt in/out as emergency contacts with `/notify emergency on|off`
- Critical alerts are sent to matching topic subscribers and emergency contacts
- `media-alerts` fanout is supported for Telegram so users can be notified when media pipeline/availability events are published
- media "ready" alerts are gated by an explicit Overseerr availability check (`status >= TELEGRAM_MEDIA_READY_STATUS_REQUIRED`) before Telegram delivery
- repeated Plex-availability alerts for the same media title are suppressed after first delivery (`TELEGRAM_MEDIA_FIRST_SEEN_ONLY_ENABLED=true`), so Telegram only gets first-time availability updates
- media-category notifications default to community library updates (broadcast to active users), but can be forced to private delivery by including `notify_targets=<telegram_user_id,...>` in the ntfy message body
- media-category notifications bypass quiet-hours deferral so community availability updates are delivered immediately
- recipients that fail with `telegram_http_400` are auto-quarantined immediately (and preemptively skipped on later fanout cycles) to reduce repeated `sent_partial` noise
- repeated incident events now collapse into updates for existing Telegram incident messages when possible (instead of always sending a new message)
- Regular active Telegram users are auto-subscribed to `media` notifications by default

SQLite runtime state migration (Sprint-4 scaffold):

- Keep default behavior (`TELEGRAM_STATE_BACKEND=json`) until migration is complete.
- One-shot migration command:
  - `python3 scripts/migrate-telegram-state-json-to-sqlite.py --sqlite /path/to/telegram_state.db --delivery /path/to/telegram_delivery_state.json --dedupe /path/to/telegram_dedupe_state.json --notify-stats /path/to/telegram_notify_stats.json --digest-queue /path/to/telegram_digest_queue.json --incidents /path/to/telegram_incidents.json`
- After migration, set `TELEGRAM_STATE_BACKEND=sqlite`, set `TELEGRAM_STATE_SQLITE_PATH`, and restart `ntfy-n8n-bridge`.
- One-command cutover to SQLite backend (includes migration + restart):
  - `./scripts/cutover-telegram-state-backend-sqlite.sh`
- One-command rollback to JSON backend:
  - `./scripts/rollback-telegram-state-backend-json.sh`

Secret rotation drill (Sprint-5):

- Rehearsal mode (no secret changes; restart + health validation + synthetic monitor):
  - `./scripts/run-secret-rotation-drill.sh`
- Apply mode (writes new secrets, then validates):
  - `NEW_TELEGRAM_BOT_TOKEN='<new_token>' NEW_OVERSEERR_API_KEY='<new_api_key>' ./scripts/run-secret-rotation-drill.sh --apply`
- Script always creates a timestamped `.env` backup and prints a rollback command.
- Apply mode rejects placeholder/dummy-looking values (for example `PASTE_NEW_*`, `REPLACE_*`, `CHANGE_ME*`) before mutating `.env`.

Media request board shortcut:

- Run request board with environment auto-loaded:
  - `./scripts/reqboard --with-telegram`
- Any flags are passed through to `show-media-request-board.py` (for example `--json`, `--take 50`, `--telegram-limit 800`).

Stale pending media request tracker:

- Diagnose unresolved requests older than 60 minutes:
  - `./scripts/reqtrack --stale-minutes 60`
- Emit escalation prompts to ntfy (`ops-alerts` for admins, `media-alerts` for users):
  - `./scripts/reqtrack --stale-minutes 60 --emit-ntfy`
- Attempt safe auto-fix (auto-approve only for stale `PENDING` requests):
  - `./scripts/reqtrack --stale-minutes 60 --attempt-fixes --auto-approve-pending --emit-ntfy`
- Approval-token remediation flow (`propose` -> `apply`):
  - Propose: `REQTRACK_FIX_APPROVAL_SECRET='<secret>' ./scripts/reqtrack --stale-minutes 60 --attempt-fixes --auto-approve-pending --fix-approval-mode propose --json`
  - Apply: `REQTRACK_FIX_APPROVAL_SECRET='<secret>' ./scripts/reqtrack --stale-minutes 60 --attempt-fixes --auto-approve-pending --fix-approval-mode apply --fix-approval-token '<token>' --json`
  - Audit stream: `./scripts/reqtrack --stale-minutes 60 --attempt-fixes --auto-approve-pending --fix-audit-file /tmp/reqtrack-fix-audit.ndjson --fix-actor ops-bot --json`
- Guardrailed remediation dry run (no mutation; shows `fix_summary` and per-item guardrail reason):
  - `./scripts/reqtrack --stale-minutes 60 --attempt-fixes --auto-approve-pending --fix-dry-run --max-fixes-per-run 2 --fix-min-age-minutes 180 --fix-actions approve_pending --emit-ntfy --json`
- Optional safe retry remediation class (for stale approved/processing requests with old update timestamp):
  - `./scripts/reqtrack --stale-minutes 60 --attempt-fixes --fix-retry-enabled --fix-actions approve_pending,retry_request --fix-retry-min-since-update-minutes 180 --emit-ntfy --json`
- Optional per-entity suppression windows (reduce repeated notifications for same requester/title):
  - `./scripts/reqtrack --stale-minutes 60 --emit-ntfy --suppress-by-requester-minutes 180 --suppress-by-title-minutes 120 --json`
- JSON mode for automation/cron parsing:
  - `./scripts/reqtrack --json --take 150 --stale-minutes 60`
- Render dashboard status artifact (consumed by Homepage tile):
  - `./scripts/render-media-request-tracker-dashboard-status.sh`
- Bundled daily reqtrack health command (tracker + KPI + dashboard artifact):
  - `./scripts/run-reqtrack-daily-health.sh`
  - Install daily cron: `./scripts/install-reqtrack-daily-health-cron.sh`
  - Custom schedule: `REQTRACK_DAILY_HEALTH_CRON_SCHEDULE='10 6 * * *' ./scripts/install-reqtrack-daily-health-cron.sh`
  - Remove daily cron: `./scripts/uninstall-reqtrack-daily-health-cron.sh`
- Escalation policy:
  - `PENDING` -> admin prompt (approval/permission path)
  - `APPROVED/PROCESSING` but not available -> user prompt first for request clarity, admin prompt when queue/config appears stuck

Telegram payload fields sent to n8n:

- `message`, `image_url`, `has_image`
- `audio_url`, `audio_kind` (`voice`/`audio`), `audio_mime`, `audio_duration`, `audio_file_name`, `has_audio`
- `chat_id`, `user_id`, `source`, `timestamp`
- `memory_enabled`, `memory_summary`
- `user_profile_seed`, `user_profile_image_url` (optional private per-user personalization seed; not treated as RAG source)
- `interaction_user_id`, `active_user_ids`, `profile_context_allowed` (Discord gating fields)

Telegram Discord-profile linking:

- Users can link Telegram identity to Discord seed identity with:
  - `/discord link` (interactive prompt)
  - `/discord link <discord_name_or_handle>`
  - `/discord show`
  - `/discord unlink`
- Link behavior:
  - The bridge prompts for Discord name/handle and matches against `work/discord-seed/discord_user_profiles.json`.
  - On successful match, it stores `linked_discord_user_id` metadata and applies matched private profile seed/image to Telegram payload personalization.
  - `/discord unlink` removes the account link metadata (does not delete the seed catalog file).

Audio transcription path in `Day4 - RAG Query`:

- If Telegram payload has `has_audio=true` and no text message, n8n calls `STT_BASE_URL + STT_TRANSCRIPT_PATH` and passes `audio_url` for server-side transcription.
- Current defaults point to in-stack `openwhisper`: `http://openwhisper:9000/v1/audio/transcriptions`.
- The transcription model field is controlled by `STT_MODEL` (default `whisper-1`) and passed through to the API.
- Set `STT_DEBUG_RESPONSE_ENABLED=true` to include lightweight STT diagnostics (`has_audio`, `transcription_error`, fallback marker) in Telegram webhook responses.
- Runbook incident steps (persistent toggle + one-request override): [`docs/00-master-runbook.md#stt-debug-response-toggle-incident-triage`](../../../docs/00-master-runbook.md#stt-debug-response-toggle-incident-triage)
- To keep prior behavior, you can set `STT_BASE_URL=http://host.docker.internal:11435` and `STT_MODEL=whisper-large-v3-turbo`.

Retrieval routing policy (`Day4 - RAG Query`):

- Default behavior is **web-first** for normal questions.
- RAG is used only when the query looks like internal/docs intent (examples: `runbook`, `docs`, `knowledge base`, `day 5`, `phase 1`, `servernoots`) **and** Qdrant confidence is high enough.
- If RAG is requested but confidence is low, workflow falls back to web-first and explicitly states internal context was weak.
- Weather questions prefer live weather fetch path.
- Web search path now uses provider fallback: DuckDuckGo first, then Wikipedia search API if primary snippets are empty.
- Optional override for fallback endpoint: `WEB_FALLBACK_URL` (defaults to `https://en.wikipedia.org/w/api.php`).
- Temporary audit tag is appended to replies: `[route:<decision> score:<top_score>]`.
- Toggle this with `ROUTING_DEBUG=true|false` in `docker-compose.yml` (`n8n` environment).

Standardized smalltalk + expected-input replies (`Day4 - RAG Query`):

- A pre-generated response library now handles simple conversational intents before model calls.
- Current intent keys: `greeting`, `thanks`, `farewell`, `checkin`, `capabilities`, `examples`, `user_profile`, `memory_limits`, `status`, `clarify_request`, `retry_request`, `handoff_human`, `safety_refusal`.
- This keeps short interactions consistent and lowers unnecessary LLM usage.
- Templates can personalize with learned user context when present (`full_name`, `telegram_username`, `role`, `tenant_id`).
- Tone variants are selected by blending channel/role defaults with inferred user style from each message.
- Inference cues include politeness (`please`, `thanks`), greetings, warm emoji, urgency/frustration terms, all-caps bursts, punctuation intensity, and directive length.
- Baseline defaults remain: Telegram user=`warm`, Telegram admin=`concise`, ntfy=`neutral`.
- Tone smoothing keeps a per-user rolling memory of the last 3 inferred tones and blends this with current inference + baseline to reduce abrupt tone flips across turns.
- Tone memory is stored in workflow static data when available (with in-process fallback).
- Telegram bridge now also persists tone history in `telegram_users.json` and forwards `tone_history` in webhook payloads for reliable cross-turn smoothing.
- Persona Contract v1 is now emitted on routed payloads and final replies: `persona_contract_version`, `tone_target`, `brevity_target`, `style_must`, `style_must_not`, `safety_mode`.
- Contract targets are derived in `Prepare Query` and propagated through `Build General Prompt`, `Format Smalltalk Reply`, `Format RAG Reply`, and `Format General Reply`.
- Debug tags now include contract markers (`pc:<version> tone_target:<value> brevity:<value> safety:<value>`) to support telemetry parsing and rollout verification.
- A perceived turn metric is inferred per message (`perceived_score`, `perceived_label`) and shown in debug tags as `ux:<label> ux_score:<value>`.
- Correction or additional-information attempts are weighted negative (examples: `actually`, `that is wrong`, `more context`, `additional info`, `try again`).
- Prompt generation now appends persisted user memory when `memory_enabled=true` and `memory_summary` is present.
- Prompt generation also appends optional private seed context (`user_profile_seed`) and image reference (`user_profile_image_url`) for personalization/voice interactions.
- Private seed context is designed to be non-citable: it is injected as user context, not indexed into Qdrant sources.
- For `source=discord`, profile context is only accepted when the target `user_id` is actively interacting (`interaction_user_id == user_id`) or appears in `active_user_ids` (or `profile_context_allowed=true` for explicit trusted override).
- Implementation lives in the `Prepare Query` code node (`smalltalkLibrary`) and routes through `If Smalltalk Mode`.
- To extend: add a new `key`, one or more regex `patterns`, and a `build(ctx)` template in that library.

Discord seed import helper:

- Build private per-user seed profiles from Discord export ZIP:
  - `/usr/bin/python3 scripts/import-discord-user-seed.py '/home/sook/Downloads/Council of Degenerates.zip' --out 'work/discord-seed' --min-messages 3`
- Outputs:
  - `work/discord-seed/discord_user_profiles.json` (profile map + avatar path + seed text)
  - `work/discord-seed/discord_user_seed_payloads.ndjson` (one payload stub per Discord user)

Discord active-context loader helper:

- Build a safe per-request payload fragment (only includes seed/image when user is active/interacting):
  - `/usr/bin/python3 scripts/discord-profile-context-loader.py --profiles work/discord-seed/discord_user_profiles.json --user-id 183726312861466635 --interaction-user-id 183726312861466635 --active-user-ids 183726312861466635,779823628312772608`

Discord RAG proxy helper (recommended):

- Wrapper enforces server-side profile gating and strips caller-provided seed/image fields.
- Command contract v1 supported:
  - `/ask <question>` -> forwards to RAG webhook (`/webhook/rag-query`)
  - `/ops <action>` -> forwards to ops webhook (`/webhook/ops-commands-ingest`) and requires `role=admin`
  - `/status` -> returns proxy + n8n health summary (`/healthz` probe)
  - `/memory show|opt-in|opt-out|clear` -> per-user memory-control scaffold (`/memory clear confirm` required by default policy)
- Voice control scaffold (M6) supported:
  - `/join`, `/leave`, `/listen on`, `/listen off`, `/voice status`, `/voice stop`
  - Default behavior returns `route=discord-voice-scaffold` and writes audit events.
  - Optional forwarding to voice webhook can be enabled with `--voice-forward` (target `--voice-webhook`, default `/webhook/discord-voice-command`).
  - With `--voice-forward`, non-control voice events containing `audio_url`/`has_audio`/`voice_mode` are forwarded as `command=voice_loop` to the voice webhook.
  - Voice-loop transport hardening: forwarded `voice_loop` events now require `voice_session_id` and at least one content signal (`audio_url` or `transcript` or `has_audio=true`); invalid events are rejected with `route=discord-voice-loop-invalid` and audited as denied.
  - Cooldown policy is enabled by default for voice control commands (`--voice-cooldown-seconds`, default from `policy/rate_limit.voice_session_cooldown_seconds` or fallback `30`); `/voice status` is cooldown-exempt.
  - Moderator/admin override is supported with `--voice-moderator-role-ids <csv>` (admins always bypass cooldown).
  - Cooldown state is persisted in `--voice-state-file` (default `logs/discord-voice-state.json`).
  - Memory state is persisted in `--memory-state-file` (default `logs/discord-memory-state.json`).
  - Memory attribution gate threshold can be overridden with `--memory-min-speaker-confidence` (default from policy or `0.8`).
  - Forwarded payloads now include memory scaffold fields: `voice_memory_opt_in`, `memory_write_mode`, `raw_audio_persist`, `speaker_confidence`, `memory_min_speaker_confidence`, and `memory_write_allowed`.
  - Persistence-side write gating now applies at response writeback time: `memory_summary` is extracted from downstream webhook responses and persisted only when policy checks pass (opt-in requirement + confidence threshold policy).
  - `rag-query` response contract now returns top-level `memory_summary` for both Telegram and non-Telegram branches, enabling consistent proxy writeback extraction.
- Example:
  - `echo '{"user_id":"183726312861466635","guild_id":"123","channel_id":"456","role":"user","interaction_user_id":"183726312861466635","active_user_ids":["183726312861466635"],"message":"/ask hey"}' | /usr/bin/python3 scripts/discord-rag-proxy.py --profiles work/discord-seed/discord_user_profiles.json --n8n-base http://127.0.0.1:5678 --allow-guild-ids 123 --allow-channel-ids 456 --audit-log logs/discord-command-audit.jsonl`
- Optional scope allowlists:
  - `--allow-guild-ids <csv>`
  - `--allow-channel-ids <csv>`
  - `--allow-role-ids <csv>`
- Audit JSONL includes timestamp, command, decision, reason, scope IDs, role, and webhook target.

Discord voice loop dry-run helper (M7 scaffold):

- Script: `scripts/discord-voice-loop-dryrun.py`
- Purpose: dry-run contract for `STT -> rag-query routing -> TTS text output` without requiring live Discord voice transport.
- CLI mode (single event):
  - `printf '{"user_id":"183726312861466635","guild_id":"g1","channel_id":"c1","role":"user","tenant_id":"u_183726312861466635","message":"hello from voice dry run","voice_session_id":"vs-1"}' | python3 scripts/discord-voice-loop-dryrun.py --n8n-base http://127.0.0.1:5678 --rag-webhook /webhook/rag-query --stt-base http://127.0.0.1:9001`
- HTTP mode (contract endpoint):
  - `python3 scripts/discord-voice-loop-dryrun.py --serve --host 127.0.0.1 --port 8101`
  - `POST http://127.0.0.1:8101/discord-voice-command` (or `/voice-loop`)
- `audio_url` is supported for STT via `--stt-path` (default `/v1/audio/transcriptions/by-url`); if `message`/`transcript` is present, STT is skipped.
- OpenWhisper by-url parity evidence (2026-02-28): native `POST /v1/audio/transcriptions/by-url` path validated end-to-end with `scripts/discord-voice-loop-dryrun.py`; proof artifact: `/tmp/openwhisper-byurl-e2e-proof.json` (fixture: `/tmp/openwhisper-byurl-e2e-event.json`).
- If STT provider returns `404` on `--stt-path`, the helper automatically retries using OpenWhisper-compatible `POST /v1/audio/transcriptions?source_url=<audio_url>&model=<model>`.

M8 memory persistence proof shortcuts:

- From `master-suite/phase1/ai-control`:
  - `make m8-proof-all` (clean + verbose proof rerun + compact status)
  - `make m8-proof-fresh` (clean + verbose proof rerun)
  - `make m8-proof-quick` (clean + non-verbose proof rerun)
  - `make m8-proof-status` (compact `M8_PROOF_STATUS=PASS|FAIL|NO_SUMMARY`)
  - `make m8-proof-clean` (remove prior `/tmp/discord-m8-*` artifacts)
- Under-the-hood proof scripts:
  - `scripts/eval-discord-memory-persistence-proof-pack.py`
  - `scripts/eval-discord-memory-persistence-cli-proof.py`
  - `scripts/eval-discord-memory-persistence-http-proof.py`

M9 channel parity shortcuts:

- From `master-suite/phase1/ai-control`:
  - `make m9-parity` (run cross-channel contract parity probes and write durable artifacts)
  - `make m9-parity-status` (compact `M9_PARITY_STATUS=PASS|FAIL|NO_SUMMARY`)
- Artifacts:
  - `checkpoints/m9-parity-summary.json`
  - `checkpoints/m9-contract-parity.json`
- Runner script:
  - `scripts/eval-discord-channel-parity-pack.py`

M3 policy release-gate shortcuts:

- From `master-suite/phase1/ai-control`:
  - `make m3-policy-gate` (topic contract + memory contract + cross-channel parity in one run)
  - `make m3-policy-gate-status` (compact `M3_POLICY_GATE_STATUS=PASS|FAIL|NO_SUMMARY`)
- Artifacts:
  - `checkpoints/m3-policy-release-gate-summary.json`
  - `/tmp/m3-policy-release-gate-summary.json`
- Runner script:
  - `scripts/eval-m3-policy-release-gate.py`

Systemd service template:

- Unit file: `systemd/discord-rag-proxy.service`
- Local endpoint: `POST http://127.0.0.1:8099/discord-rag`
- Environment knobs:
  - `DISCORD_ALLOW_GUILD_IDS`, `DISCORD_ALLOW_CHANNEL_IDS`, `DISCORD_ALLOW_ROLE_IDS`
  - `RAG_WEBHOOK`, `OPS_WEBHOOK`, `VOICE_WEBHOOK`, `N8N_HEALTH_PATH`
  - `VOICE_STATE_FILE`, `VOICE_COOLDOWN_SECONDS`, `VOICE_MODERATOR_ROLE_IDS`
  - `DISCORD_AUDIT_LOG`
- Install:
  - `sudo cp systemd/discord-rag-proxy.service /etc/systemd/system/`
  - `sudo systemctl daemon-reload && sudo systemctl enable --now discord-rag-proxy.service`

One-command rollback (disable debug tags + redeploy workflow):

- `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control`
- `./scripts/disable-routing-debug.sh`

One-command enable (re-enable debug tags + redeploy workflow):

- `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control`
- `./scripts/enable-routing-debug.sh`

One-command RAG Query publish/recover (register `/webhook/rag-query`):

- `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control`
- `./scripts/publish-rag-query-workflow.sh --verify`

One-command core chat workflow publish/recover (register both `/webhook/rag-query` and `/webhook/textbook-fulfillment`):

- `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control`
- `./scripts/publish-core-chat-workflows.sh --verify`
- This helper imports/publishes both workflows first, then performs a single `n8n` restart.

Routing evaluation (baseline regression check):

- `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control`
- `./scripts/eval-routing.py`
- Contract markers are enforced by default.
- Temporary escape hatch: `./scripts/eval-routing.py --no-require-contract`
- Test-only probe cases can be explicitly allowed in local runs with `EVAL_ALLOW_TEST_PROBES=1 ./scripts/eval-routing.py`.
- Style-gate markers are also enforced by default via debug tags: `sg:<pass|fail>` and `sgr:<reason>`.
- Confidence tier marker is emitted in debug tags as `conf:<high|medium|low>`.
- Test-only terminal-fail probe token `__stylegate_force_fail__` is reserved for regression fixtures; expected marker outcome is `sg:fail` with `sgr:fail_forced_probe`.
- Current implementation keeps style gate enabled in formatter code nodes; use workflow rollback/republish scripts to disable if needed.
- Test cases are in `scripts/routing-eval-cases.json`.
- Exit code is non-zero if any case fails (good for cron/CI checks).

Memory replay evaluation foundation (KPI + schema):

- KPI contract: `evals/memory/kpi-contract.md`
- Replay case schema: `evals/memory/replay-schema.json`
- Starter fixtures: `evals/memory/golden-replay.sample.ndjson`
- Golden fixtures (expanded): `evals/memory/golden-replay.ndjson`
- Replay runner: `scripts/eval-memory-replay.py`
- Use this flow when extending memory behavior:
  - define/adjust KPI targets first,
  - add or update replay fixtures,
  - run memory smoke checks before promoting changes.
- Baseline replay run:
  - `python3 scripts/eval-memory-replay.py --cases evals/memory/golden-replay.ndjson`
- JSON report run:
  - `python3 scripts/eval-memory-replay.py --cases evals/memory/golden-replay.ndjson --json`
- Optional privacy-safe naturalness comparison (aggregate stats only; no raw ZIP content persisted):
  - `python3 scripts/eval-memory-replay.py --cases evals/memory/golden-replay.ndjson --naturalness-zip '/path/Sooknoots Empire.zip' --naturalness-zip '/path/Council of Degenerates.zip'`

Daily automation (cron + ntfy alert on failure):

- Install twice-daily jobs (03:15 and 12:15 local): `./scripts/install-routing-eval-cron.sh`
- Manual run now: `./scripts/run-routing-eval-and-alert.sh`
- Alert runner now executes strict mode (`eval-routing.py --require-contract`) by default.
- Synthetic alert-path tests (without editing case files):
  - `./scripts/run-routing-eval-and-alert.sh --dry-fail contains`
  - `./scripts/run-routing-eval-and-alert.sh --dry-fail route`
  - `./scripts/run-routing-eval-and-alert.sh --dry-fail contract`
  - `./scripts/run-routing-eval-and-alert.sh --dry-fail http`
  - `./scripts/run-routing-eval-and-alert.sh --dry-fail error`
- Logs: `logs/routing-eval-YYYY-MM-DD.log`

Telegram/chat smoke checks:

- List available checks: `python3 scripts/eval-telegram-chat-smoke.py --list`
- List by mode: `python3 scripts/eval-telegram-chat-smoke.py --list --mode local` (or `--mode live`)
- Run full suite: `python3 scripts/eval-telegram-chat-smoke.py`
- Run local-only checks (no live webhook dependency): `python3 scripts/eval-telegram-chat-smoke.py --mode local`
- Run selected checks only: `python3 scripts/eval-telegram-chat-smoke.py --check webhook_basic --check tenant_isolation`
- Personality live checks: `python3 scripts/eval-telegram-chat-smoke.py --mode live --check personality_correction_ack_live --check personality_uncertainty_no_hallucination_live --check personality_low_confidence_tier_live --check personality_recovery_mode_live --check personality_smalltalk_budget_marker_live --check personality_rag_budget_marker_live --check personality_ops_budget_marker_live`
- Run selected local checks only: `python3 scripts/eval-telegram-chat-smoke.py --mode local --check rate_limit_debounce_local`
- Per-user personality preferences: `/profile style show`, `/profile style set tone <warm|neutral|concise>`, `/profile style set brevity <short|balanced|detailed>`, `/profile style reset`
- Micro-feedback tuning: `/feedback too_short|too_long|too_formal|too_vague|good` (auto-adjusts style preferences and records feedback stats)
- Stored profile style preferences are forwarded as `persona_pref_tone` / `persona_pref_brevity` and override auto-inferred targets when set.
- Persona drift telemetry is tracked per user (`persona_drift_stats`) and summarized in `/profile show` as mismatch streak and mismatch ratio.
- Low-confidence replies now enforce uncertainty phrasing; when missing, style-gate rewrites prepend: `Based on available context, I may be missing details.`
- Route-specific response budgets are enforced via style-gate limits (smalltalk: `short=220`, `balanced=520`, `detailed=900`; rag: `short=340`, `balanced=980`, `detailed=1700`; general: `short=280`, `balanced=760`, `detailed=1300`).
- Debug tags include effective response budget as `rb:<maxChars>` for deterministic live verification.
- Alert wrapper (full): `./scripts/run-telegram-chat-smoke-and-alert.sh`
- Alert wrapper (targeted): `./scripts/run-telegram-chat-smoke-and-alert.sh --check webhook_basic --check tenant_isolation`
- Alert wrapper (targeted local-only): `./scripts/run-telegram-chat-smoke-and-alert.sh --mode local --check rate_limit_debounce_local`
- Wrapper auto-heals rag-query webhook first via `scripts/ensure-rag-webhook-ready.sh`, then runs textbook verify (if enabled), then smoke checks.
- In `--mode local`, wrapper skips rag-query and textbook webhook prechecks and runs local smoke checks only.
- Logs: `logs/telegram-chat-smoke-YYYY-MM-DD.log`

Daily UX metrics summary (tone/perceived quality):

- Install daily report job (06:20 local): `./scripts/install-ux-metrics-cron.sh`
- Manual run now: `./scripts/run-ux-metrics-and-alert.sh`
- Source topic: `ai-replies` debug tags (`ux:<label> ux_score:<value>`)
- Daily report also includes negative cue counts from `ai-chat` as `negative_cues correction=<n> additional_info=<n> retry=<n> frustration=<n> cue_samples=<n>`
- Daily report includes per-cue percentages as `negative_cue_rates correction=<pct> additional_info=<pct> retry=<pct> frustration=<pct>`
- Daily report includes uncertainty/repeat-mistake KPI line: `uncertainty_compliance=<pct> low_conf_samples=<n> compliant=<n> repeat_mistake_rate=<pct> repeat_mistake_count=<n> repeat_mistake_samples=<n>`
- Daily report also includes `top_negative_cues=<cue:count,...>` (top 3 non-zero)
- Daily status now includes `warn_reasons=...` when negative rate or cue-rate thresholds are exceeded
- Daily and weekly reports now include `warn_codes=...` (machine-readable codes like `NEG_RATE`, `CUE_RETRY`, `DELTA_NEG_RATE`, `UNCERTAINTY_COMPLIANCE`, `REPEAT_MISTAKE`)
- Daily/weekly `warn_reasons` now use aligned labels/order for parsing (e.g. `negative_rate>=...`, `<cue>_rate>=...`, plus weekly delta checks)
- Alert topic: `ops-alerts` with status (`OK`, `Warning`, `No Data`)
- Config knobs: `UX_METRICS_SINCE` (default `24h`), `UX_NEG_RATE_WARN_THRESHOLD` (default `0.35`), `NTFY_CHAT_TOPIC` (default `ai-chat`)
- Daily cue warn thresholds: `UX_DAILY_CUE_WARN_CORRECTION` (default `0.25`), `UX_DAILY_CUE_WARN_ADDITIONAL_INFO` (default `0.25`), `UX_DAILY_CUE_WARN_RETRY` (default `0.20`), `UX_DAILY_CUE_WARN_FRUSTRATION` (default `0.10`)
- KPI gate thresholds: `UX_UNCERTAINTY_COMPLIANCE_MIN` (default `0.95`), `UX_REPEAT_MISTAKE_WARN_THRESHOLD` (default `0.08`)

Weekly UX rollup (7-day trend):

- Install weekly rollup job (Monday 06:35 local): `./scripts/install-ux-metrics-weekly-cron.sh`
- Manual run now: `./scripts/run-ux-metrics-weekly-rollup-and-alert.sh`
- Reads last-per-day summaries from `logs/ux-metrics-YYYY-MM-DD.log`
- Computes top negative cue patterns from daily `negative_cues` lines first; falls back to direct `ai-chat` scan if daily cue data is missing
- Includes weekly cue percentages as `weekly_negative_cue_rates correction=<pct> additional_info=<pct> retry=<pct> frustration=<pct>`
- Includes weekly uncertainty/repeat-mistake KPI line: `uncertainty_compliance=<pct> low_conf_samples=<n> compliant=<n> repeat_mistake_rate=<pct> repeat_mistake_count=<n> repeat_mistake_samples=<n>`
- Weekly status now warns when cue rates exceed thresholds and reports `warn_reasons=...`
- Posts aggregate and deltas (`delta_avg_vs_prev_day`, `delta_neg_rate_vs_prev_day`) to `ops-alerts`
- Weekly cue knobs: `NTFY_CHAT_TOPIC` (default `ai-chat`), `UX_WEEKLY_CHAT_FETCH_TIMEOUT_SECONDS` (default `30`)
- Weekly cue warn thresholds: `UX_WEEKLY_CUE_WARN_CORRECTION` (default `0.25`), `UX_WEEKLY_CUE_WARN_ADDITIONAL_INFO` (default `0.25`), `UX_WEEKLY_CUE_WARN_RETRY` (default `0.20`), `UX_WEEKLY_CUE_WARN_FRUSTRATION` (default `0.10`)
- Weekly KPI gate threshold override: `UX_WEEKLY_REPEAT_MISTAKE_WARN_THRESHOLD` (defaults to `UX_REPEAT_MISTAKE_WARN_THRESHOLD`)

Media synthetic monitoring (Sprint-3):

- Manual run: `./scripts/run-media-synthetic-check-and-alert.sh`
- Install daily cron job (07:05 local): `./scripts/install-media-synthetic-check-cron.sh`
- Checks include:
  - Request-path health via Overseerr (`/api/v1/status` + `/api/v1/search`)
  - `media-alerts` fanout-path processing check via bridge notify stats state
- On any failure, script exits non-zero, emits failure alert to `ops-alerts`, and writes heartbeat file at `logs/media-synthetic-heartbeat.json`.
- Key knobs:
  - `MEDIA_SYNTHETIC_REQUEST_QUERY` (default `Sintel`)
  - `MEDIA_SYNTHETIC_REQUEST_MEDIA_TYPE` (default `movie`)
  - `MEDIA_SYNTHETIC_OVERSEERR_FALLBACK_URL` (default `http://127.0.0.1:5055`; used when primary `OVERSEERR_URL` is unreachable from host shell)
  - `MEDIA_SYNTHETIC_FANOUT_WAIT_SECONDS` (default `90`)
  - `MEDIA_SYNTHETIC_HEARTBEAT_FILE` (default `logs/media-synthetic-heartbeat.json`)
  - `TELEGRAM_MEDIA_NOISE_FILTER_ENABLED` (default `true`; suppresses synthetic/probe informational fanout noise)
  - `TELEGRAM_MEDIA_NOISE_MARKERS` (default includes `synthetic_id=`, `media synthetic check media-synthetic-`, `media sweep probe`, `media cursor probe`, `cursor_probe=`, `verification_run=`, `quiet_topic_drill=`, `media ready verification`)
  - `TELEGRAM_MEDIA_FIRST_SEEN_ONLY_ENABLED` (default `true`; suppresses repeated "available in Plex" alerts for previously announced titles)
  - `TELEGRAM_MEDIA_FIRST_SEEN_RETENTION_SECONDS` (default `31536000`; how long first-seen media keys are retained)

Textbook synthetic monitoring:

- Manual run: `./scripts/run-textbook-synthetic-check-and-alert.sh`
- Install daily cron job (07:35 local): `./scripts/install-textbook-synthetic-check-cron.sh`
- Remove cron job: `./scripts/uninstall-textbook-synthetic-check-cron.sh`
- Checks include:
  - textbook webhook registration/reachability via `scripts/verify-textbook-webhook.sh`
  - textbook local smoke checks (defaults: `textbook_pick_alias_local`, `textbook_untrusted_source_local`, `textbook_delivery_ack_retry_local`)
- On failure, script exits non-zero, emits failure alert to `ops-alerts`, and writes heartbeat file at `logs/textbook-synthetic-heartbeat.json`.
- Key knobs:
  - `TEXTBOOK_WEBHOOK_VERIFY_ENABLED` (default `true`)
  - `TEXTBOOK_SYNTHETIC_RAG_PREFLIGHT_ENABLED` (default `true`; runs `ensure-rag-webhook-ready.sh` before textbook checks)
  - `TEXTBOOK_SYNTHETIC_SMOKE_MODE` (default `local`)
  - `TEXTBOOK_SYNTHETIC_CHECKS` (default `textbook_pick_alias_local,textbook_untrusted_source_local,textbook_delivery_ack_retry_local`)
  - `TEXTBOOK_SYNTHETIC_HEARTBEAT_FILE` (default `logs/textbook-synthetic-heartbeat.json`)
  - `TEXTBOOK_SYNTHETIC_CRON_SCHEDULE` (default `35 7 * * *`)

Media stale-request tracker automation:

- Manual run: `./scripts/run-media-request-tracker-and-alert.sh`
- Environment loading for reqtrack helpers: `.env` is sourced first, then `.env.secrets` (secrets override non-secret defaults).
- Monthly alert-path drill (synthetic stale requests; no real request mutation):
  - `./scripts/reqtrack --dry-drill --emit-ntfy --json`
- Controlled dedupe/escalation proof drill (stateful, temp state file):
  - `DRILL_STATE=/tmp/reqtrack-drill-state.json`
  - `./scripts/reqtrack --dry-drill --dry-drill-stateful --emit-ntfy --state-file "$DRILL_STATE" --json`
  - `./scripts/reqtrack --dry-drill --dry-drill-stateful --emit-ntfy --state-file "$DRILL_STATE" --json` (expect dedupe: `notify_candidate_count=0`)
  - `./scripts/reqtrack --dry-drill --dry-drill-stateful --emit-ntfy --state-file "$DRILL_STATE" --dry-drill-admin-age-minutes 130 --dry-drill-user-age-minutes 140 --json` (expect level-up re-alert)
- One-command helper for the same 3-step proof:
  - `./scripts/run-reqtrack-stateful-drill.sh`
- One-command release gate (incident JSON contract + KPI JSON contract + stateful dedupe/level-up drill using isolated ntfy topics):
  - `./scripts/run-reqtrack-release-gate.sh`
  - Command-contract regression smoke (CLI + Telegram admin command path): `./scripts/run-reqtrack-command-contract-smoke.sh`
  - Optional keep drill state for inspection: `REQTRACK_RELEASE_GATE_KEEP_DRILL_STATE=true ./scripts/run-reqtrack-release-gate.sh`
  - Install daily cron (default `30 6 * * *`): `./scripts/install-reqtrack-release-gate-cron.sh`
  - Remove daily cron: `./scripts/uninstall-reqtrack-release-gate-cron.sh`
  - Schedule override at install time: `REQTRACK_RELEASE_GATE_CRON_SCHEDULE='15 6 * * *' ./scripts/install-reqtrack-release-gate-cron.sh`
  - Weekly rollup runner: `./scripts/run-reqtrack-release-gate-weekly-rollup-and-alert.sh`
  - Install weekly rollup cron (default `50 6 * * 1`): `./scripts/install-reqtrack-release-gate-weekly-cron.sh`
  - Remove weekly rollup cron: `./scripts/uninstall-reqtrack-release-gate-weekly-cron.sh`
  - Weekly rollup overrides:
    - Window days: `REQTRACK_RELEASE_GATE_WEEKLY_DAYS=14 ./scripts/run-reqtrack-release-gate-weekly-rollup-and-alert.sh`
    - Disable ntfy emit: `REQTRACK_RELEASE_GATE_WEEKLY_EMIT_NTFY=false ./scripts/run-reqtrack-release-gate-weekly-rollup-and-alert.sh`
    - Weekly schedule override: `REQTRACK_RELEASE_GATE_WEEKLY_CRON_SCHEDULE='20 7 * * 1' ./scripts/install-reqtrack-release-gate-weekly-cron.sh`
- Install cron job (every 15 minutes by default): `./scripts/install-media-request-tracker-cron.sh`
- Remove cron job: `./scripts/uninstall-media-request-tracker-cron.sh`
- Cron schedule override at install time:
  - `REQTRACK_CRON_SCHEDULE='*/10 * * * *' ./scripts/install-media-request-tracker-cron.sh`
- Runtime knobs (from `.env`):
  - `REQTRACK_STALE_MINUTES` (default `60`)
  - `REQTRACK_TAKE` (default `120`)
  - `REQTRACK_TIMEOUT` (default `20`)
  - `REQTRACK_ESCALATION_LEVELS` (default `60,120,240`; minute ladder for re-alert levels)
  - `REQTRACK_MIN_REALERT_MINUTES` (default `0`; minimum interval before re-alerting an already-active incident)
  - `REQTRACK_MAX_NOTIFY_CANDIDATES` (default `25`; cap notified incidents per run after level/age sort)
  - `REQTRACK_MAX_ADMIN_LINES` (default `20`; cap incident lines in admin-topic body)
  - `REQTRACK_MAX_USER_LINES` (default `10`; cap incident lines in user-topic body)
  - `REQTRACK_MIN_USER_NOTIFY_LEVEL` (default `1`; require this escalation level before user-topic notifications)
  - `REQTRACK_STATE_FILE` (default `logs/media-request-tracker-state.json`; persistent incident dedupe state)
  - `REQTRACK_STATE_RETENTION_DAYS` (default `30`; prune old resolved incidents from state)
  - `REQTRACK_DRY_DRILL_ADMIN_AGE_MINUTES` (default `70`; synthetic age for admin drill item)
  - `REQTRACK_DRY_DRILL_USER_AGE_MINUTES` (default `80`; synthetic age for user drill item)
  - `REQTRACK_KPI_WINDOW_HOURS` (default `24`; KPI digest lookback window)
  - `REQTRACK_ATTEMPT_FIXES` (default `false`)
  - `REQTRACK_AUTO_APPROVE_PENDING` (default `false`; only used when `REQTRACK_ATTEMPT_FIXES=true`)
  - `REQTRACK_FIX_ACTIONS` (default `approve_pending`; allowlist of remediation actions)
  - `REQTRACK_MAX_FIXES_PER_RUN` (default `3`; hard cap on remediation attempts per run)
  - `REQTRACK_FIX_MIN_AGE_MINUTES` (default `120`; minimum stale age before remediation attempts)
  - `REQTRACK_FIX_REQUIRE_ADMIN_TARGET` (default `true`; only attempt remediation for admin-target diagnostics)
  - `REQTRACK_FIX_DRY_RUN` (default `false`; evaluate remediation eligibility without mutating Overseerr)
  - `REQTRACK_FIX_APPROVAL_MODE` (default `direct`; `direct|propose|apply`)
  - `REQTRACK_FIX_APPROVAL_SECRET` (required for `propose|apply`; signing secret for approval tokens)
  - `REQTRACK_FIX_APPROVAL_TOKEN` (used by `apply`; token returned from `propose` output)
  - `REQTRACK_FIX_PROPOSAL_TTL_MINUTES` (default `60`; approval token TTL)
  - `REQTRACK_FIX_PROPOSAL_FILE` (default `logs/media-request-tracker-fix-proposals.json`; proposal persistence)
  - `REQTRACK_FIX_AUDIT_ENABLED` (default `true`; write immutable remediation decision NDJSON records)
  - `REQTRACK_FIX_AUDIT_FILE` (default `logs/media-request-tracker-fix-audit.ndjson`; remediation audit sink)
  - `REQTRACK_FIX_ACTOR` (default `reqtrack`; actor label attached to remediation audit events)
- Log file: `logs/media-request-tracker-YYYY-MM-DD.log`
- Alert behavior: first alert on first stale detection, then only when escalation ladder level increases (deduped between levels), with optional cooldown/caps via noise-control knobs above

Incident operator controls (state file):

- List active incidents:
  - `./scripts/reqtrack --incident-action list --incident-filter active --json`
- List all incidents (active + resolved):
  - `./scripts/reqtrack --incident-action list --incident-filter all --json`
- Acknowledge an incident:
  - `./scripts/reqtrack --incident-action ack --incident-key 'request:<id>' --incident-by operator --incident-note 'acknowledged' --json`
- Snooze an incident for 2 hours:
  - `./scripts/reqtrack --incident-action snooze --incident-key 'request:<id>' --snooze-minutes 120 --incident-by operator --incident-note 'investigating' --json`
- Clear incident snooze:
  - `./scripts/reqtrack --incident-action unsnooze --incident-key 'request:<id>' --incident-by operator --json`
- Close incident manually:
  - `./scripts/reqtrack --incident-action close --incident-key 'request:<id>' --incident-by operator --incident-note 'resolved manually' --json`

KPI digest (state-only rollup):

- Print KPI summary (last 24h default):
  - `./scripts/reqtrack --kpi-report`
- Print KPI summary with custom window and JSON output:
  - `./scripts/reqtrack --kpi-report --kpi-window-hours 48 --json`
- Expanded KPI dimensions now include:
  - Window actions: `acked`, `reopened`, `level2plus_notified`
  - Active-age buckets: `lt_1h`, `h1_4`, `h4_24`, `gte_24h`
  - Long-running active backlog: `long_running_active_24h`
  - Recurring incident quality sample: `quality.top_realerted`
- Send KPI digest to admin ntfy topic:
  - `./scripts/reqtrack --kpi-report --emit-kpi-ntfy`
- Historical exports (for trends outside chat/ntfy):
  - NDJSON: `./scripts/reqtrack --kpi-report --export-history-format ndjson --export-history-file /tmp/reqtrack-history.ndjson --export-history-window-hours 168 --export-history-limit 1000 --json`
  - CSV: `./scripts/reqtrack --kpi-report --export-history-format csv --export-history-file /tmp/reqtrack-history.csv --export-history-window-hours 168 --export-history-limit 1000 --json`
  - One-command runner (uses env defaults): `./scripts/run-media-request-tracker-history-export.sh`
  - Runner knobs: `REQTRACK_EXPORT_FORMAT`, `REQTRACK_EXPORT_FILE`, `REQTRACK_EXPORT_WINDOW_HOURS`, `REQTRACK_EXPORT_LIMIT`, `REQTRACK_EXPORT_DIR`
- Daily KPI digest runner (writes `logs/media-request-tracker-kpi-YYYY-MM-DD.log`):
  - `./scripts/run-media-request-tracker-kpi-and-alert.sh`
- Install daily KPI digest cron (default `15 9 * * *`):
  - `./scripts/install-media-request-tracker-kpi-cron.sh`
- Remove daily KPI digest cron:
  - `./scripts/uninstall-media-request-tracker-kpi-cron.sh`
- KPI cron schedule override at install time:
  - `REQTRACK_KPI_CRON_SCHEDULE='30 8 * * *' ./scripts/install-media-request-tracker-kpi-cron.sh`
- Weekly KPI rollup runner (default 168h window; writes `logs/media-request-tracker-kpi-weekly-YYYY-MM-DD.log`):
  - `./scripts/run-media-request-tracker-kpi-weekly-rollup-and-alert.sh`
- One-line weekly KPI wrapper:
  - `./scripts/kpiweekly`
  - JSON example: `./scripts/kpiweekly --json`
- Install weekly KPI rollup cron (default `40 6 * * 1`):
  - `./scripts/install-media-request-tracker-kpi-weekly-cron.sh`
- Remove weekly KPI rollup cron:
  - `./scripts/uninstall-media-request-tracker-kpi-weekly-cron.sh`
- Weekly window/schedule overrides:
  - `REQTRACK_KPI_WEEKLY_WINDOW_HOURS=168 REQTRACK_KPI_WEEKLY_CRON_SCHEDULE='10 7 * * 1' ./scripts/install-media-request-tracker-kpi-weekly-cron.sh`

Telegram admin command equivalents (tracker state):

- List tracker incidents:
  - `/reqtrack list active`
- KPI digest in Telegram (24h default):
  - `/reqtrack kpi`
- KPI digest with custom window:
  - `/reqtrack kpi 48`
- KPI digest as compact JSON in Telegram:
  - `/reqtrack kpi json`
  - `/reqtrack kpi 48 json`
  - Large JSON replies are auto-chunked into multiple Telegram messages with `[reqtrack-json i/n]` headers
  - Chunk size tuning: `TELEGRAM_REQTRACK_JSON_CHUNK_MAX_CHARS` (default follows Telegram review cap)
- Explicit pretty mode (human-readable):
  - `/reqtrack kpi pretty`
- Weekly KPI digest window in Telegram:
  - `/reqtrack kpiweekly`
- Weekly KPI JSON:
  - `/reqtrack kpiweekly json`
- Weekly KPI explicit pretty mode:
  - `/reqtrack kpiweekly pretty`
- Acknowledge:
  - `/reqtrack ack request:<id> acknowledged`
- Snooze (default 120m if minutes omitted):
  - `/reqtrack snooze request:<id> 120 investigating`
- Unsnooze:
  - `/reqtrack unsnooze request:<id>`
- Close manually:
  - `/reqtrack close request:<id> resolved`
- Check bridge-visible state path:
  - `/reqtrack state`

Media request board helper (Overseerr):

- Live board (table): `set -a && source .env && set +a && python3 scripts/show-media-request-board.py`
- JSON output: `set -a && source .env && set +a && python3 scripts/show-media-request-board.py --json`
- Limit rows: `set -a && source .env && set +a && python3 scripts/show-media-request-board.py --take 50`
- Merge Telegram notify status (heuristic): `set -a && source .env && set +a && python3 scripts/show-media-request-board.py --with-telegram`
- Merge mode reads `media-alerts` delivery events from `ntfy-n8n-bridge` notify stats and marks `tg=Y` when a post-request Telegram send event exists.

Personalized Plex recommendations and private Telegram notifications:

- Script: `scripts/run-personalized-plex-recs.py`
- Example profile file: `work/media-user-profiles.example.json` (copy to `work/media-user-profiles.json` and edit)
- Required env: `TAUTULLI_URL`, `TAUTULLI_API_KEY`
- Optional env for auto-download requests: `OVERSEERR_URL`, `OVERSEERR_API_KEY`
- Optional auto-request guardrails:
  - `MEDIA_AUTO_REQUEST_DAILY_CAP_PER_USER` (default `1`; max automatic Overseerr requests per user per 24h window)
  - `MEDIA_DO_NOT_REQUEST_FILE` (default `work/media-do-not-request.txt`; one title per line, case-insensitive)
- Default behavior:
  - Builds per-user taste profile from Tautulli movie history + `preferred_genres`
  - Matches recent Plex additions and sends private Telegram alerts through ntfy topic `media-recommendations`
  - Uses `notify_targets=<telegram_user_id>` directive so fanout is private
  - Persists dedupe/request state in `logs/media-personalization-state.json`
- Dry run: `set -a && source .env && set +a && python3 scripts/run-personalized-plex-recs.py --dry-run`
- Live run (notify only): `set -a && source .env && set +a && python3 scripts/run-personalized-plex-recs.py`
- Live run + auto-request up to 2 movies per user: `set -a && source .env && set +a && python3 scripts/run-personalized-plex-recs.py --auto-request-per-user 2`
- Example do-not-request list template: `work/media-do-not-request.example.txt`
- Cron runner wrapper: `scripts/run-personalized-plex-recs-and-alert.sh`
- Install daily cron job (08:20 local default): `./scripts/install-personalized-plex-recs-cron.sh`
- Remove cron job: `./scripts/uninstall-personalized-plex-recs-cron.sh`
- Daily digest wrapper: `scripts/run-personalized-plex-recs-daily-digest-and-alert.sh`
- Install daily digest cron job (09:30 local default): `./scripts/install-personalized-plex-recs-digest-cron.sh`
- Remove daily digest cron job: `./scripts/uninstall-personalized-plex-recs-digest-cron.sh`
- Install second daily digest (21:30 local default): `./scripts/install-personalized-plex-recs-digest-evening-cron.sh`
- Remove second daily digest: `./scripts/uninstall-personalized-plex-recs-digest-evening-cron.sh`
- Cron schedule override at install time:
  - `MEDIA_PERSONALIZED_CRON_SCHEDULE='35 9 * * *' ./scripts/install-personalized-plex-recs-cron.sh`
  - `MEDIA_PERSONALIZED_DIGEST_CRON_SCHEDULE='45 9 * * *' ./scripts/install-personalized-plex-recs-digest-cron.sh`
  - `MEDIA_PERSONALIZED_DIGEST_EVENING_CRON_SCHEDULE='30 21 * * *' ./scripts/install-personalized-plex-recs-digest-evening-cron.sh`
- Optional runtime knobs for cron wrapper (via `.env`):
  - `MEDIA_PERSONALIZED_DRY_RUN` (`true|false`, default `false`)
  - `MEDIA_PERSONALIZED_PROFILES_PATH` (default script argument)
  - `MEDIA_PERSONALIZED_STATE_PATH` (default script argument)
  - `MEDIA_PERSONALIZED_AUTO_REQUEST_PER_USER` (overrides CLI default)
  - `MEDIA_AUTO_REQUEST_DAILY_CAP_PER_USER` (default `1`)
  - `MEDIA_PERSONALIZED_HEARTBEAT_FILE` (default `logs/media-personalized-heartbeat.json`)
  - `MEDIA_PERSONALIZED_MONITOR_STATE_FILE` (default `logs/media-personalized-monitor-state.json`)
  - `MEDIA_PERSONALIZED_ALERT_TOPIC` (default `ops-alerts`)
  - `MEDIA_PERSONALIZED_ALERT_ON_SKIP` (`true|false`, default `true`)
  - `MEDIA_PERSONALIZED_ZERO_ACTIVITY_THRESHOLD` (default `3`; alerts after N consecutive runs with `notified=0` and `auto_requested=0`)
  - `MEDIA_PERSONALIZED_DIGEST_TOPIC` (default `ops-alerts`)
  - `MEDIA_PERSONALIZED_DIGEST_WINDOW_HOURS` (default `24`)

UX log parser helper (JSON for dashboards/automation):

- Script: `scripts/parse-ux-metrics-log.py`
- Parse latest block from a log file: `python3 scripts/parse-ux-metrics-log.py logs/ux-metrics-YYYY-MM-DD.log --pretty`
- Parse latest block as one-line NDJSON: `python3 scripts/parse-ux-metrics-log.py logs/ux-metrics-YYYY-MM-DD.log --latest-ndjson`
- Parse only weekly summaries from mixed logs: `python3 scripts/parse-ux-metrics-log.py logs/ux-metrics-weekly-YYYY-MM-DD.log --kind weekly --all --ndjson`
- `--kind` accepts `daily`, `weekly`, `both`, or `auto` (`both`/`auto` mean no kind filtering)
- Add `--require-kind` to fail fast if no matching kind blocks are found (exits with code `4`; useful for CI/guards)
- Parser exit codes: `4` = no matching kind blocks (with `--require-kind`), `5` = log file not found
- Parser unknown options now return exit `2` with `Unknown option: ...` + usage (aligned with wrapper behavior)
- Parser missing required args now return exit `2` with `Missing required argument: ...` + usage
- Parse all summary blocks in a log file: `python3 scripts/parse-ux-metrics-log.py logs/ux-metrics-weekly-YYYY-MM-DD.log --all --pretty`
- Emit NDJSON (one block per line): `python3 scripts/parse-ux-metrics-log.py logs/ux-metrics-weekly-YYYY-MM-DD.log --all --ndjson`
- Wrapper for jq/pipelines: `scripts/ux-metrics-to-ndjson.sh logs/ux-metrics-YYYY-MM-DD.log logs/ux-metrics-weekly-YYYY-MM-DD.log`
- Wrapper latest-only mode: `scripts/ux-metrics-to-ndjson.sh --latest logs/ux-metrics-YYYY-MM-DD.log logs/ux-metrics-weekly-YYYY-MM-DD.log`
- Wrapper kind filter: `scripts/ux-metrics-to-ndjson.sh --kind weekly --latest logs/ux-metrics-YYYY-MM-DD.log logs/ux-metrics-weekly-YYYY-MM-DD.log`
- Wrapper aliases: `--kind both` or `--kind auto` (no filtering)
- Wrapper strict mode: `scripts/ux-metrics-to-ndjson.sh --kind weekly --require-kind --latest logs/ux-metrics-YYYY-MM-DD.log logs/ux-metrics-weekly-YYYY-MM-DD.log`
- Output includes machine-readable fields: `warn_reasons` (text labels) and `warn_codes` (stable codes)

Exit codes (parser/wrapper strict modes):

- `4`: no matching kind blocks found when `--require-kind` is set
- `5`: log file not found

Security defaults:

- If `TELEGRAM_ALLOWED_USER_IDS` is set, all other users are denied.
- Keep commands behind existing n8n guardrail workflow.
- Risky `/ops` commands require explicit approval: `/approve <id>` or `/deny <id>`.
- Approval requests expire automatically (`TELEGRAM_APPROVAL_TTL_SECONDS`, default `300`).
- Admins can list current approval queue with `/pending`.
- Per-user burst limiter is enabled for chat requests (`TELEGRAM_RATE_LIMIT_MAX_REQUESTS` / `TELEGRAM_RATE_LIMIT_WINDOW_SECONDS`, defaults `6` per `30s`).
- Admins can inspect limiter activity with `/ratelimit` (includes notice debounce on/off status).
- Utility/admin commands (`/ratelimit`, `/pending`, `/whoami`, `/selftest`, `/approve`, `/deny`, `/notify`, `/tone`, `/user`) are handled directly and are not routed to AI.
- Very short text inputs are intercepted before AI routing (`TELEGRAM_SHORT_INPUT_MIN_CHARS`, default `3`).
- Low-signal one-token messages (for example `ds`, `sa`, `ag`) are intercepted with a concise local prompt (`TELEGRAM_LOW_SIGNAL_FILTER_ENABLED=true`, `TELEGRAM_LOW_SIGNAL_TOKEN_MAX_CHARS=2`).
- Rate-limit warning replies are debounced per user so a burst only emits one `Too many requests` notice until the user becomes allowed again (`TELEGRAM_RATE_LIMIT_NOTICE_DEBOUNCE_ENABLED=true`).
- Noisy admin info commands are cooldown-limited per user (`TELEGRAM_ADMIN_COMMAND_COOLDOWN_SECONDS`, default `15`) and only one cooldown warning is emitted during each active window for configured commands in `TELEGRAM_ADMIN_COMMAND_COOLDOWN_COMMANDS` (defaults: `/status,/ratelimit,/notify stats,/digest stats`).

Per-user memory (opt-in):

- `/memory on|off|show|add <note>|clear`
- Memory is injected into AI payload as `memory_enabled` + `memory_summary`.
- Retention controls: `TELEGRAM_MEMORY_TTL_DAYS` (default `30`), `TELEGRAM_MEMORY_MAX_ITEMS` (default `20`), `TELEGRAM_MEMORY_MAX_CHARS` (default `1200`).
- Admin default notification topics are seeded from `TELEGRAM_DEFAULT_ADMIN_NOTIFY_TOPICS`.
- Emergency contact defaults are seeded from `TELEGRAM_EMERGENCY_ADMIN_USERNAMES`.

Telegram notification preference commands (admin):

- `/notify list`
- `/notify health`
- `/notify set <all|none|topic1,topic2>`
- `/notify add <topic1,topic2>`
- `/notify remove <topic1,topic2>`
- `/notify emergency <on|off>`
- `/notify quiet <off|HH-HH>`
- `/notify quiet <topic> <off|HH-HH>`
- `/notify delivery list [limit]`
- `/notify delivery retry <telegram_user_id|all> [limit]`
- `/notify media-first-seen stats [limit]`
- `/notify media-first-seen clear <title words>`
- `/notify media-first-seen clear all CONFIRM`
- `/notify quarantine list`
- `/notify quarantine media-bypass-status`
- `/notify quarantine clear <telegram_user_id>`
- `/notify quarantine media-bypass-once CONFIRM`
- `/notify quarantine clear-all CONFIRM`
- `media-bypass-once` is a guarded one-shot override that allows the next `media-alerts` fanout cycle to include currently quarantined recipients once.
- `delivery retry` only retries transient failure records; permanent errors (for example `telegram_http_400`) are skipped.
- `clear-all` is restricted to designated security-admin Telegram IDs from `TELEGRAM_NOTIFY_QUARANTINE_CLEAR_ALL_ADMINS` (defaults to `TELEGRAM_BOOTSTRAP_ADMINS`).

Telegram media request examples:

- Step 1: `/media movie Dune 2021` (or `/media tv Severance`)
- Step 2: confirm one result with `/media pick <number>`
- Alias format also works: `/request movie Interstellar 2014`

Telegram textbook request examples:

- Step 1: `/textbook request title: Calculus: Early Transcendentals, author: Stewart, edition: 8th, isbn: 9781285741550, course: MATH-2413`
- Step 2: `/textbook email student@school.edu`
- Step 3: `/textbook 1` (alias) or `/textbook pick 1`
- Step 4: `/textbook confirm`
- Step 5 (optional): `/textbook ingest yes` or `/textbook ingest no`
- Status check anytime: `/textbook status`
- Post-delivery controls: `/textbook delivered`, `/textbook failed mailbox bounce`, `/textbook resend`
- Bot now shows `options_found`, provides refinement guidance (especially edition/ISBN), and includes book cover links for visual match before `/textbook confirm`.
- Bot also attempts Telegram inline cover previews (`sendPhoto`) for shortlist options and selected candidate when image URLs are available.

Telegram temporary workspace examples:

- `/workspace create bmw-x5-manuals`
- `/workspace add https://example.com/manuals/bmw-x5-2022.pdf`
- `/workspace add brake fluid specification is DOT4 for model-year 2022 notes`
- `/workspace mode workspace`
- `/workspace mode status`
- `/workspace status`
- `/workspace close`

Tone history commands (admin):

- `/tone show <telegram_user_id>`
- `/tone reset <telegram_user_id>`

One-command health check:

- `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control`
- `./scripts/telegram-healthcheck.sh`
- Validates token presence, bridge container status, and `rag-query` direct Telegram-style reply.

Bring bridge online after `.env` is set:

- `docker compose up -d telegram-n8n-bridge`

Find your Telegram numeric IDs quickly:

- `./scripts/telegram-get-user-ids.sh`
- If no updates appear, send a message to your bot in Telegram and rerun.

## Local URLs

- n8n: `http://localhost:5678`
- Qdrant API: `http://localhost:6333`
- Qdrant gRPC: `localhost:6334`
- Ollama bridge target for workflows: `http://host.docker.internal:11435/api/generate`
- OpenWhisper health: `http://localhost:9001/health` (default; controlled by `OPENWHISPER_HOST_PORT`)

Troubleshooting note:

### OpenWhisper port collision recovery

- If `docker compose up -d` fails with `Bind for 127.0.0.1:9000 failed: port is already allocated`, set `OPENWHISPER_HOST_PORT=9001` in `.env` (or another free loopback port) and rerun compose. This avoids collisions with stacks that already bind `127.0.0.1:9000` (for example, Authentik).

### Textbook webhook transient recovery

- If textbook synthetic checks fail with webhook connection errors to `127.0.0.1:5678`, verify n8n health (`curl -fsS http://127.0.0.1:5678/healthz`) and rerun `./scripts/run-textbook-synthetic-check-and-alert.sh`; transient reachability flaps have recovered cleanly with this sequence.
- Operator runbook reference: `../../../docs/00-master-runbook.md`.

## Guardrails usage

- `bash guardrails/safe_command.sh service_status gluetun`
- `bash guardrails/safe_command.sh restart_service homepage CONFIRM_RESTART`
- `bash guardrails/safe_command.sh disk_health_summary`

## Safety behavior

- Unknown action => denied
- Non-allowlisted service => denied
- Restart action => requires `CONFIRM_RESTART`
- Every command appends an audit record to `guardrails/audit.log`

## Next Day 4 tasks

- Build n8n workflows:
  - inbound topics: `ai-chat`, `ops-commands`
  - outbound topics: `ai-replies`, `ops-alerts`
- Connect n8n to existing Ollama/OpenWebUI path
- Add Qdrant ingest/query workflows

## Current Day 4 wiring status

- `ai-chat` -> n8n -> Ollama (`qwen3-coder:30b`) -> `ai-replies`
- `ai-replies` (phone user message) -> n8n RAG query webhook -> `ai-replies` (AI response)
- `ops-commands` -> n8n -> guarded response -> `ops-alerts`
- ntfy topic bridge service forwards inbound topic events into n8n webhooks
- AI-generated messages on `ai-replies` are posted with title `AI Reply` and ignored by the bridge to prevent reply loops
- Telegram bridge can be used as an alternate frontend into the same n8n RAG + guardrail flows
