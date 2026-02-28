# Operations Command Reference (Master Suite)

## Purpose

This is the operator-focused command guide for the current workspace.
It centralizes routine commands for:

- service lifecycle,
- verification and health checks,
- alert/routing/snapshot automation,
- and controlled administrative access.

Scope: runbook-friendly command reference (no code changes required).

---

## Operating principles

- Run commands from the service directory unless noted otherwise.
- Prefer read/check commands first, then change actions.
- Use snapshots before major phase changes.
- Keep admin surfaces private; use Tailscale mappings where configured.

---

## Global quick checks

From workspace root:

- `cd /media/sook/Content/Servernoots`
- Validate workflow JSON files:
  - `jq empty master-suite/phase1/ai-control/workflows/rag-query-webhook.json`
  - `jq empty master-suite/phase1/ai-control/workflows/rag-ingest-webhook.json`
  - `jq empty master-suite/phase1/ai-control/workflows/ops-commands-webhook.json`
  - `jq empty master-suite/phase1/ai-control/workflows/deep-research-webhook.json`

---

## Service lifecycle by stack

## AdGuard (`master-suite/phase1/adguard`)

- Start: `docker compose up -d`
- Check: `docker compose ps`
- Drift guard: `./check-bind-ip.sh`
- Drift guard with alert: `NTFY_URL=http://127.0.0.1:8091/security-alerts ./check-bind-ip.sh`

## Authentik (`master-suite/phase1/authentik`)

- First-time env setup: `cp .env.example .env`
- Start: `docker compose up -d`
- Check: `docker compose ps`

## CrowdSec (`master-suite/phase1/crowdsec`)

- Start: `docker compose up -d`
- Check: `docker compose ps`
- Logs: `docker logs --tail 80 crowdsec`
- LAPI status: `docker exec crowdsec cscli lapi status`
- Metrics: `docker exec crowdsec cscli metrics`

## Gluetun + downloader/arr path (`master-suite/phase1/gluetun`)

- Start: `docker compose up -d`
- Check: `docker compose ps`
- VPN logs: `docker logs --tail 80 gluetun`
- Egress IP check: `docker exec gluetun wget -qO- https://ipinfo.io/ip`
- Optional env helper: `./fill-env.sh`

## Homepage (`master-suite/phase1/homepage`)

- Start: `docker compose up -d`
- Check: `docker compose ps`

## Monitoring (`master-suite/phase1/monitoring`)

- Start: `docker compose up -d`
- Check: `docker compose ps`
- Logs:
  - `docker logs --tail 80 netdata`
  - `docker logs --tail 80 beszel`
  - `docker logs --tail 80 scrutiny`

## ntfy (`master-suite/phase1/ntfy`)

- Start: `docker compose up -d`
- Check: `docker compose ps`
- Test publish:
  - `curl -d "test message" http://127.0.0.1:8091/ops-alerts`
  - `curl -d "security test" http://127.0.0.1:8091/security-alerts`

## Alerts bridge (`master-suite/phase1/alerts`)

- Start: `docker compose up -d`
- Logs: `docker logs --tail 80 alert-bridge`
- Manual check publish: `curl -d "manual check" http://127.0.0.1:8091/ops-alerts`

## AI Control (`master-suite/phase1/ai-control`)

- Start stack: `docker compose up -d`
- Recreate Telegram bridge only: `docker compose up -d --force-recreate telegram-n8n-bridge`
- Check n8n logs: `docker logs --since 30s n8n 2>&1 | tail -n 120`

## Media (`master-suite/phase1/media`)

- Start: `docker compose up -d`
- Check: `docker compose ps`
- Key URLs:
  - Plex: `http://localhost:32400/web`
  - Tautulli: `http://localhost:8181`
  - Overseerr: `http://localhost:5055`

---

## Telegram and AI operations

From `master-suite/phase1/ai-control`:

### Telegram bridge checks

- Full bridge healthcheck: `./scripts/telegram-healthcheck.sh`
- Discover candidate Telegram IDs: `./scripts/telegram-get-user-ids.sh`

### Routing debug and evaluation

- Enable route debug markers and redeploy workflow: `./scripts/enable-routing-debug.sh`
- Disable route debug markers and redeploy workflow: `./scripts/disable-routing-debug.sh`
- Run routing regression test set: `./scripts/eval-routing.py`
- Run eval with alert-on-failure wrapper: `./scripts/run-routing-eval-and-alert.sh`
- Install twice-daily routing eval cron: `./scripts/install-routing-eval-cron.sh`

### User/RAG snapshots

- Create snapshot now: `./scripts/snapshot-user-rag-state.sh`
- Snapshot wrapper with alert + retention pruning: `./scripts/run-user-rag-snapshot-and-alert.sh`
- Install nightly snapshot cron: `./scripts/install-user-rag-snapshot-cron.sh`

### Guardrail command runner

- Status check: `bash guardrails/safe_command.sh service_status gluetun`
- Restart (confirmation required): `bash guardrails/safe_command.sh restart_service homepage CONFIRM_RESTART`
- Disk summary: `bash guardrails/safe_command.sh disk_health_summary`

---

## Tailscale admin access operations

From `master-suite/phase1/tailscale`:

- Enable mapped admin ports: `./enable-admin-access.sh`
- Disable mapped admin ports: `./disable-admin-access.sh`
- Verify serve mappings: `tailscale serve status`

Ports mapped by script:

- `8443` Homepage
- `8444` Authentik
- `8445` n8n
- `8446` Netdata
- `8447` Beszel
- `8448` Scrutiny
- `8449` Overseerr
- `8450` Sonarr
- `8451` Radarr
- `8452` Prowlarr
- `8453` qBittorrent
- `8454` Tautulli
- `8455` Plex Web
- `8456` ntfy

---

## Media preparation scripts

From `master-suite/phase1/media`:

- Storage/permission bootstrap: `./day5-step1-storage-bootstrap.sh`
- Drive format/mount script: `sudo ./day5-format-plex-drives.sh`

Warning:

- `day5-format-plex-drives.sh` is destructive for targeted devices and should only be run after device validation.

---

## Topic and alert checks

Examples:

- Recent ops topic messages:
  - `curl -sS 'http://127.0.0.1:8091/ops-alerts/json?since=10m' | tail -n 30`
- Check tenant-denial audit signal:
  - `curl -sS 'http://127.0.0.1:2586/ops-alerts/json?since=10m' | tail -n 30 | grep -F 'TENANT_SCOPE_DENIED'`

---

## Common recovery actions

### Service unhealthy recovery

- Service unhealthy:
  1. `docker compose ps`
  2. `docker logs --tail 120 <container_name>`
  3. restart target service (`docker compose restart <service>`)

### Workflow import/runtime recovery

- Workflow import/runtime issue:
  1. validate workflow JSON with `jq`
  2. re-import via n8n CLI in container
  3. restart n8n container

- Deep research deploy/verify shortcut:
  - `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control`
  - `./scripts/publish-deep-research-workflow.sh --verify`

### Deep Research Regression Automation

- One-shot regression (start/status/report + link consistency):
  - `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control`
  - `make deep-research-regression`
  - PASS marker: `DEEP_RESEARCH_REGRESSION=PASS`
- Status-only check from latest summary:
  - `make deep-research-regression-status`
  - PASS marker: `DEEP_RESEARCH_REGRESSION_STATUS=PASS`
- Alert wrapper (publishes to `ops-alerts` on failure):
  - `make deep-research-regression-alert`
- Durable artifacts:
  - `checkpoints/deep-research-regression-latest.json`
  - `checkpoints/deep-research-regression-<timestamp>.json`
- Compatibility mirror:
  - `/tmp/deep-research-regression-latest.json`
- Cron automation:
  - Install: `make install-deep-research-regression-cron`
  - Uninstall: `make uninstall-deep-research-regression-cron`
  - Schedule override: `DEEP_RESEARCH_REGRESSION_CRON_SCHEDULE='35 6 * * *' make install-deep-research-regression-cron`

### Textbook webhook transient recovery

- Telegram failures:
  1. run `telegram-healthcheck.sh`
  2. verify `.env` token + allowlist
  3. verify bridge + n8n containers are running
  4. if textbook synthetic fails with `127.0.0.1:5678` webhook connection errors, run `curl -fsS http://127.0.0.1:5678/healthz` then rerun `./scripts/run-textbook-synthetic-check-and-alert.sh` after n8n recovery

### OpenWhisper port collision recovery

- If `docker compose up -d` fails with `Bind for 127.0.0.1:9000 failed: port is already allocated`, set `OPENWHISPER_HOST_PORT=9001` in `master-suite/phase1/ai-control/.env` (or another free loopback port) and rerun compose.

---

## Safety reminders

- Do not bypass guardrails with direct destructive shell commands from chat workflows.
- Do not expose admin ports publicly for convenience.
- Do not treat backup success as restore success; perform restore drills.

---

## Related docs

- `00-master-runbook.md`
- `06-day4-checklist.md`
- `11-tailnet-admin-expansion.md`
- `13-telegram-command-reference.md`
- `14-software-capabilities-matrix.md`
