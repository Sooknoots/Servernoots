# Day 6 Checklist (Ops Hardening + Backups + Restore Drill)

## Day 6 Goal

Make your suite reliable under failure by implementing:

- Kopia backup policies
- Watchtower update strategy
- Scrutiny/CrowdSec alert tuning
- Restore test + incident runbook

## Progress Status

Last updated: 2026-02-27

- [x] Day 6 complete (Kopia + restore drill + watchtower policy + alert tuning + checkpoint snapshot)
- [x] Day 5 dependency satisfied for Day 6 progression: Immich mobile-backup confirmation captured (host reboot validation deferred by operator)
- [x] Kopia backup policy/configuration verified (local repository + retention policy + snapshots)
- [x] Pre-Kopia restore drill verified using existing snapshot backup pipeline (`backup-system-snapshots.sh`)
- [x] Kopia-native restore drill verified (baseline mutation + snapshot restore + hash match)
- [x] Watchtower policy validation complete (monitor-only + one-shot run verified)
- [x] Policy + restore-drill scaffold prepared: `docs/19-day6-kopia-policy-template.md`

Execution evidence (2026-02-27):

- Pre-reqs: `checkpoints/day5-media-stable.tar.gz` present; media stack healthy via `docker compose ps`.
- Backup pass: `./scripts/backup-system-snapshots.sh` completed (`[OK] Backup complete`) with latest destination marker updated.
- Kopia installed locally: `~/.local/bin/kopia` (`0.22.3`).
- Kopia repo initialized: `master-suite/phase1/ai-control/snapshots/kopia-repo` with config file `master-suite/phase1/ai-control/snapshots/kopia.repository.config`.
- Kopia global retention policy applied: hourly `24`, daily `14`, weekly `8`, monthly `6`.
- Kopia snapshots created successfully for:
  - `/media/sook/Content/Servernoots/docs`
  - `/media/sook/Content/Servernoots/master-suite/phase1/ai-control`
  - media metadata sources (`media/docker-compose.yml`, `media/README.md`, `media/validate-immich-backup.sh`, `media/immich/backups`)
- Restore drill pass (snapshot pipeline):
  - File: `master-suite/phase1/ai-control/snapshots/restore-drill/restore-drill.txt`
  - Baseline SHA256 matched restored SHA256 after intentional mutation and restore from latest snapshot backup.
  - Result marker: `RESTORE_DRILL_OK`.
- Restore drill pass (Kopia-native):
  - Snapshot source: `/media/sook/Content/Servernoots/master-suite/phase1/ai-control`
  - Restored file path: `snapshots/restore-drill/restore-drill.txt` into `/tmp/kopia-restore-drill/restore-drill.txt`
  - Baseline SHA256 matched restored SHA256 after mutation.
  - Result marker: `KOPIA_RESTORE_DRILL_OK`.
- Immich backup re-check pass: `master-suite/phase1/media/validate-immich-backup.sh` succeeded; artifacts written under `media/immich/backups/2026-02-27-184136/`.
- Watchtower deployed in monitoring stack (`master-suite/phase1/monitoring/docker-compose.yml`) with controlled policy: `--label-enable --monitor-only --scope phase1-monitoring --cleanup --schedule '0 0 5 * * *'`.
- Watchtower one-shot validation pass: `docker compose run --rm watchtower --run-once --label-enable --monitor-only --scope phase1-monitoring --cleanup` returned `Session done Failed=0 Scanned=0 Updated=0`.
- `update-alerts` path confirmed via ntfy JSON stream (`/update-alerts/json?since=5m`) containing watchtower startup/one-shot messages.
- Alert-noise tuning evidence (updated 2026-02-27): synthetic checker now auto-loads `.env` for Overseerr credentials and no longer overflows argv when notify stats grow; latest run reports `status=ok, request_check=request_path_ok, fanout_check=fanout_processed:sent:none` (`EXIT_CODE=0`).
- Bridge notify stats suppression summary (`/state/telegram_notify_stats.json`, recent window):
  - `ops-alerts`: dominant `critical_only` suppression with observed `dedupe` / `incident_acked` / `incident_snoozed` controls active.
  - `media-alerts`: observed `sent`, `sent_partial`, `dedupe`, `media_noise`, and `deferred` outcomes.
- Bridge stability fix applied: `ntfy-n8n-bridge` mount for `telegram-bridge-state` changed to writable (removed `:ro`), and runtime check shows `NO_READONLY_ERRORS`.
- Cross-topic probes published to ntfy: paired synthetic events for `security-alerts` and `ops-alerts` confirmed present via topic JSON streams.
- Security channel validation: `security-alerts` synthetic message appears in ntfy JSON stream; this topic remains channel-level (not part of Telegram fanout topic map).
- Day 6 checkpoint captured: `checkpoints/day6-ops-hardened.tar.gz` (verified readable via `tar -tzf`, updated `2026-02-27 20:10`).

Remaining items:

- Day 5 dependency remains documented as deferred reboot policy; this does not block Day 6 completion.
- Day 7 kickoff notes are ready for final-validation execution.

Immediate next command set:

- Execute Day 7 final-validation sweep and produce `day7-go-live-baseline` snapshot evidence.

## Time Budget

- Total: 3 to 5 hours
- Stop point: successful backup + verified restore test

## Before You Start

- Confirm snapshot exists: `day5-media-stable`
- Take pre-change snapshot: `day6-before-ops`
- Confirm Homepage and ntfy are healthy

## Step 1 — Define backup policy (what, where, how long)

Create a written policy before configuring tools.

Minimum policy:

- **What to back up**: app configs, databases, workflow files, media metadata, photo metadata
- **What not to back up**: re-downloadable media payloads (optional), caches, temp files
- **Where**: local backup target + optional offsite encrypted target
- **Retention**: daily snapshots + weekly + monthly window

Verification:

- Policy file exists and is readable in 1 page

## Step 2 — Configure Kopia

Set up repositories and schedules.

Minimum backup sets:

1. Core services (auth/security/control)
2. AI/RAG data (n8n workflows, Qdrant collections metadata)
3. Media metadata (Plex/Tautulli/arr configs)

Verification:

- One manual backup job completes
- Backup list shows snapshot entry
- Encryption is enabled

## Step 3 — Test restore (mandatory)

Run a small restore test now.

Safe restore drill:

1. Pick one low-risk config file
2. Back it up
3. Modify the file intentionally
4. Restore from Kopia snapshot
5. Confirm file matches original

Verification:

- Restore succeeds without guesswork
- You can describe restore steps from memory

## Step 4 — Configure Watchtower with caution

Use controlled updates, not blind auto-update for critical apps.

Recommended approach:

- Auto-update only low-risk tools first
- Exclude critical identity/security services initially
- Notify via ntfy on update success/failure

Verification:

- Dry run or scheduled run completes
- You receive update report notification

## Step 5 — Tune alerting noise

Tune Scrutiny, CrowdSec, and ops notifications so you only get useful alerts.

Minimum alert channels:

- `security-alerts`: bans, intrusion warnings, auth anomalies
- `ops-alerts`: backup failures, update failures, service down
- `media-alerts`: optional Plex/Tautulli events

Verification:

- One test alert from each class reaches phone
- No excessive duplicate spam in 15-minute test window

## Step 6 — Build incident runbook (simple)

Create one short runbook with:

- Service down response steps
- Disk warning response steps
- Auth lockout response steps
- Restore failure escalation steps

Verification:

- Runbook can be followed by someone else
- Each scenario has first action + fallback action

## Step 7 — Homepage Operations polish

Ensure Operations section is clear and practical.

Required Operations cards:

- Kopia — "Encrypted backups and restore"
- Watchtower — "Container update automation"
- Scrutiny — "Drive health warnings"
- Netdata/Beszel — "Live + historical performance"

Verification:

- Operations row can answer: "Are we safe, healthy, and recoverable?"

## Step 8 — Resilience checkpoint

Do one mini-failure simulation:

- Stop a non-critical container
- Confirm alert arrives
- Recover service
- Confirm recovery message arrives

Verification:

- Detection, alert, and recovery all work end-to-end

## Step 9 — Snapshot and document freeze

- Take snapshot: `day6-ops-hardened`
- Record versions of critical services
- Note any temporary exceptions (for later cleanup)

Verification:

- Snapshot exists and is boot-tested
- Docs updated with current state

## Do Not Do on Day 6

- Do not auto-update Authentik/CrowdSec without rollback plan
- Do not skip restore testing
- Do not treat backup success as restore success

## Day 6 Definition of Done

You are done when all are true:

1. Kopia backup runs and snapshots exist
2. At least one restore test is verified
3. Watchtower policy is controlled and documented
4. Alerts are tuned and actionable
5. Snapshot `day6-ops-hardened` exists

## Day 7 Preview

Final integration and confidence pass:

- End-to-end scenario testing (security, AI, media)
- UX cleanup on Homepage labels and ordering
- Final architecture review + backlog for next expansion
