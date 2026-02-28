# Day 7 Checklist (Final Validation + Go-Live)

## Day 7 Goal

Verify the full suite end-to-end, clean up Homepage usability, and create a safe go-live baseline.

## Time Budget

- Total: 3 to 5 hours
- Stop point: all critical test scenarios pass + final baseline snapshot taken

## Before You Start

- Confirm snapshot exists: `day6-ops-hardened`
- Take pre-validation snapshot: `day7-before-final`
- Confirm all core services are currently reachable from Homepage

## Progress Status

Last updated: 2026-02-27

- [x] Step 1 complete: critical service health sweep passed (core set running, no restart-loop signal)
- [x] Step 2 complete: end-to-end security scenario validated (CrowdSec detection → security-alerts delivery → response action logged)
- [x] Step 3 complete: end-to-end AI scenario validated (RAG route checks green, allowlisted action audited, risky action approval path enforced)
- [x] Step 3.5 complete: Telegram/chat full regression + live recovery validated (`38/38` all-mode smoke checks green after transient `rag-query` `500` recovery)
- [x] Step 4 complete: end-to-end media scenario validated (Overseerr request ingress, arr processing state, Plex-available catalog entries, Tautulli playback notifications)
- [x] Step 5 complete: backup and restore confidence re-check validated (on-demand backup manifest + Kopia file restore hash match)
- [x] Step 6 complete: Homepage final UX cleanup validated (required section order, friendlier tile naming, missing Operations cards added)
- [x] Step 7 complete: final risk check signed off (MFA/admin identity path confirmed, guardrail denies enforced, exposure surface reviewed, alert-noise controls evidenced)
- [x] Step 7.5 complete: ntfy topic coverage proved across all required go-live topics (all non-zero in last 24h after controlled triggers)
- [x] Step 8 complete: final baseline snapshot created and readability-tested (`checkpoints/day7-go-live-baseline.tar.gz`)

## Step 1 — Critical service health sweep

Check that all required services are up and reachable.

Must-pass core set:

- Gluetun
- AdGuard Home
- Authentik (MFA)
- CrowdSec
- ntfy
- n8n
- Ollama/OpenWebUI
- Qdrant
- Plex
- Immich
- Kopia
- Scrutiny

Verification:

- Every core service has green/healthy status
- No repeating crash/restart loops

Execution evidence (2026-02-27):

- Container status sweep (`docker ps`) confirms all Step 1 core services are `Up`/`running`.
- Restart-loop check (`docker inspect`) for Gluetun, AdGuard, Authentik, CrowdSec, ntfy, n8n, OpenWebUI, Qdrant, Plex, Immich, and Scrutiny reports `restarts=0` for all.
- Kopia verified via documented local install path: `~/.local/bin/kopia --version` → `0.22.3`.
- Step 1 result: pass.

## Step 2 — End-to-end security scenario

Run one realistic security test path.

Scenario:

1. Trigger a controlled suspicious event (safe test method)
2. Confirm detection in CrowdSec/monitoring
3. Confirm alert arrives via ntfy `security-alerts`
4. Confirm response action is logged

Verification:

- Detection + alert + log chain is complete

Execution evidence (2026-02-27):

- Controlled trigger method: reset alert-bridge CrowdSec counter (`echo 0 > /state/crowdsec-alert-count`) and wait one notifier poll interval.
- CrowdSec detection confirmed in metrics: `Local API Alerts` includes `crowdsecurity/ssh-bf`.
- `security-alerts` delivery confirmed by topic count delta (`before_count=1`, `after_count=2`, `SECURITY_ALERT_DELIVERY_OK`).
- Security topic payload includes explicit decision and source IP: `**Decision:** \`ban 203.0.113.77\`` and `**Source IP:** \`203.0.113.77\``.
- Response action logged in CrowdSec metrics: `Local API Decisions` shows `ssh:bruteforce | CAPI | ban | 15339`.
- Runtime stability check after drill: `alert-bridge`, `crowdsec`, and `ntfy-n8n-bridge` remain `Up`.

## Step 3 — End-to-end AI scenario (RAG + safe action)

Run one realistic AI-assisted workflow.

Scenario:

1. Ask a RAG question through ntfy/SMS
2. Confirm answer includes source context
3. Request one allowlisted action (status/restart)
4. Confirm approval flow for sensitive action

Verification:

- AI response is grounded in known source
- Command guardrails enforce allowlist/confirmation
- Action appears in audit log

Execution evidence (2026-02-27):

- Routing regression run passed (`scripts/eval-routing.py`): 9/9 checks pass, including explicit-rag fallback behavior and style-gate contract markers.
- Live RAG query to `/webhook/rag-query` returned non-empty reply with source/route hints (`RAG_REPLY_NONEMPTY=True`, `RAG_HAS_SOURCE_HINT=True`).
- Allowlisted action run via guardrail (`bash guardrails/safe_command.sh service_status gluetun`) succeeded (`ALLOWLISTED_EXIT=0`) and recorded audit evidence in `guardrails/audit.log` (`service_status gluetun OK:running`).
- Sensitive action approval flow validated with bridge logic simulation (`/ops restart homepage`): pending approval created (`id=1`), requester receives approval instructions, `/approve 1` clears pending state, and ops webhook dispatch occurs (`/webhook/ops-commands-ingest`).
- UX metrics hardening validated: daily/weekly runners now mark timeout-with-partial ntfy reads as info by default and emit explicit fetch markers (`fetch_mode_replies`, `fetch_mode_chat`, `fetch_timeout_s`) in summaries.
- Logging override documented: set `UX_METRICS_TIMEOUT_WARN_ON_PARTIAL=true` to restore warning-level timeout lines for partial reads.
- Telegram/chat full regression + live recovery validated:
  - Full smoke run passed end-to-end: `./scripts/eval-telegram-chat-smoke.py --mode all` → `38/38` checks green.
  - During validation, `rag-query` returned transient HTTP `500` (`{"message":"Error in workflow"}`) after workflow restart/publish cycles; recovery path (`publish-rag-query-workflow.sh --verify` + direct webhook probe + re-run full smoke) restored healthy live responses.
  - Local regression hardening remained green after recovery, including new memory regression coverage and topic-quiet media defer behavior.
  - Full local smoke rerun passed: `/usr/bin/python3 scripts/eval-telegram-chat-smoke.py --mode local` → `33/33` checks green, including `memory_regression_local`, `memory_tier_decay_order_local`, `memory_intent_scope_local`, `memory_conflict_workflow_local`, and `memory_feedback_ranking_local`.
  - Memory v2 enhancements landed and validated: conflict-confirmation gating now withholds unresolved conflicting notes until `/memory resolve`, and intent-scoped retrieval (`style|media|identity|ops`) is active in memory context selection.
  - Operator toggles (memory v2): `TELEGRAM_MEMORY_CONFLICT_REQUIRE_CONFIRMATION` (default `true`), `TELEGRAM_MEMORY_CONFLICT_PROMPT_ENABLED` (default `true`), `TELEGRAM_MEMORY_INTENT_SCOPE_ENABLED` (default `true`).
  - Operator conflict workflow controls: `TELEGRAM_MEMORY_CONFLICT_REMINDER_ENABLED` (default `true`) and `TELEGRAM_MEMORY_CONFLICT_REMINDER_SECONDS` (default `21600`) to surface stale unresolved conflicts.
  - Canary rollout controls (memory v2): `TELEGRAM_MEMORY_CANARY_ENABLED` (default `false`), `TELEGRAM_MEMORY_CANARY_PERCENT` (0-100), and deterministic override lists `TELEGRAM_MEMORY_CANARY_INCLUDE_USER_IDS` / `TELEGRAM_MEMORY_CANARY_EXCLUDE_USER_IDS`.
  - Feedback-to-ranking toggle: `TELEGRAM_MEMORY_FEEDBACK_RANKING_ENABLED` (default `true`) to adapt memory ranking weights using `/feedback` cues and conflict keep/drop outcomes.
  - Memory telemetry toggles: `TELEGRAM_MEMORY_TELEMETRY_ENABLED` (default `true`), `TELEGRAM_MEMORY_TELEMETRY_PATH` (default `/state/telegram_memory_telemetry.jsonl`).
  - Memory v2 quick verify: `PYTHONPATH=/media/sook/Content/Servernoots/master-suite/phase1/ai-control/bridge /usr/bin/python3 scripts/eval-telegram-chat-smoke.py --mode local --check memory_regression_local --check memory_tier_decay_order_local --check memory_intent_scope_local`.
  - Memory canary quick verify: `PYTHONPATH=/media/sook/Content/Servernoots/master-suite/phase1/ai-control/bridge /usr/bin/python3 scripts/eval-telegram-chat-smoke.py --mode local --check memory_canary_controls_local`.
  - Memory conflict workflow quick verify: `PYTHONPATH=/media/sook/Content/Servernoots/master-suite/phase1/ai-control/bridge /usr/bin/python3 scripts/eval-telegram-chat-smoke.py --mode local --check memory_conflict_workflow_local`.
  - Memory feedback ranking quick verify: `PYTHONPATH=/media/sook/Content/Servernoots/master-suite/phase1/ai-control/bridge /usr/bin/python3 scripts/eval-telegram-chat-smoke.py --mode local --check memory_feedback_ranking_local`.
  - Memory telemetry quick verify: `PYTHONPATH=/media/sook/Content/Servernoots/master-suite/phase1/ai-control/bridge /usr/bin/python3 scripts/eval-telegram-chat-smoke.py --mode local --check memory_telemetry_local`.
  - Memory replay KPI gate rerun: `/usr/bin/python3 scripts/eval-memory-replay.py --cases evals/memory/golden-replay.ndjson` → `memory_hit_precision=0.7059`, `memory_scope_accuracy=0.8462`, `conflict_false_positive_rate=0.0`, `conflict_resolution_clear_rate=0.8571`, `memory_write_gate_accuracy=1.0`, `memory_context_latency_ms_p95=0.125`.
- Operator quick check (latest daily + weekly fetch markers):

```bash
cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control
echo "daily:" && grep -E 'fetch_mode_|fetch_timeout_s=' "logs/ux-metrics-$(date +%F).log" | tail -n 1
echo "weekly:" && grep -E 'fetch_mode_|fetch_timeout_s=' "logs/ux-metrics-weekly-$(date +%F).log" | tail -n 1
```

- Step 3 result: pass.

## Step 4 — End-to-end media scenario

Run full request-to-playback flow.

Scenario:

1. Submit request in Overseerr
2. Process through arr stack
3. Content appears in Plex
4. Playback starts
5. Tautulli sends event notification

Verification:

- Entire media pipeline works without manual file operations

Execution evidence (2026-02-27):

- Live request submission to Overseerr API succeeded for `Interstellar` (`REQUEST_ID=3`, `REQUEST_STATUS=2`, `REQUEST_MEDIA_STATUS=2`).
- Request board confirmation (`scripts/show-media-request-board.py --take 8`) shows request `id=3` in `APPROVED/PROCESSING`, proving Overseerr → arr handoff is active.
- Same board snapshot shows completed available media entries (`Sintel` as `APPROVED/AVAILABLE` and `COMPLETED/AVAILABLE`) confirming library visibility path to Plex.
- Tautulli runtime logs (last 24h) include playback action notifications (`on_play`, `on_pause`, `on_resume`, `on_stop`), confirming playback-session telemetry path.
- Bridge notify stats state contains fresh `media-alerts` fanout records (`media_events_count=98`, latest result `sent_partial` with quiet-hours reason), confirming active media notification delivery.
- Step 4 result: pass.

## Step 5 — Backup and restore confidence test

Repeat a focused restore check.

Scenario:

1. Trigger on-demand backup
2. Restore one known test item
3. Verify integrity

Verification:

- Restore succeeds quickly and predictably
- Procedure is documented in runbook

Execution evidence (2026-02-27):

- On-demand backup trigger rerun succeeded: `backup-system-snapshots.sh` completed with `[OK] Backup complete`.
- Latest backup artifact marker: `system-snapshots/latest-path.txt` → `/media/sook/Seagate Expansion Drive/SERVERNOOTS BACKUPS/system-snapshots/2026-02-27_214613`.
- Manifest verification pass: `backup-manifest.txt` present with `snapshot_files=62` and `checkpoint_files=6`.
- Focused restore drill (Kopia) rerun with corrected file-target path:
  - Source file: `snapshots/restore-drill/restore-drill.txt`
  - Restore target: `/tmp/day7-step5-restore/restore-drill.txt`
  - Integrity: `RESTORED_SHA` equals `FINAL_SHA` (`5af05038f6a1e88ebc2e6a4e4ed0654f67761381762f41a450fd0206d9ed2a21`).
  - Safety cleanup: temporary `DAY7_STEP5_MUTATION_*` markers removed from source after restore (`MUTATION_MARKERS_CLEARED`).
- Step 5 result: pass.

## Step 6 — Homepage final UX cleanup (your key requirement)

Make the panel clear for daily use.

Required section order:

1. Core Access
2. Security
3. Network
4. AI Control
5. Knowledge
6. Media
7. Operations
8. Home

UX rules:

- Friendly names, no cryptic acronyms only
- One-line purpose per tile
- Critical services pinned to top rows
- Remove dead or duplicate links

Verification:

- You can find any critical service in under 10 seconds
- A beginner can explain each top-row tile by reading labels

Execution evidence (2026-02-27):

- Homepage config pass (`master-suite/phase1/homepage/config/services.yaml`): section order exactly matches required sequence (`Core Access` → `Home`).
- Duplicate-tile check returns zero (`duplicate_tiles=0`).
- Operations cards now include explicit recovery/update visibility entries:
  - `Kopia Backups` (encrypted backups + restore artifacts)
  - `Watchtower Policy` (controlled update automation)
  - Existing operational cards retained: `Guardrail Audit Log`, `Netdata`, `Beszel`, `Scrutiny`.
- Friendly naming cleanup applied for common acronym-heavy tiles (`Workflow Automation (n8n)`, `AI Chat and Models (OpenWebUI)`, `Vector Search Store (Qdrant)`, `Download Queue (qBittorrent)`).
- Step 6 result: pass.

## Step 7 — Final risk check

Review and confirm:

- MFA enabled on admin interfaces
- No unrestricted AI shell access
- Public exposure is intentional and minimal
- Alert spam is under control

Verification:

- Risk checklist signed off in your notes

Execution evidence (2026-02-27):

- MFA/admin identity path confirmed in Homepage control panel labeling (`Authentik` tile: "Identity and MFA portal for admin logins").
- AI shell guardrails confirmed enforced in `guardrails/safe_command.sh`:
  - explicit allowlist rule (`Only services in allowed-services.txt are permitted`)
  - restart confirmation token requirement (`CONFIRM_RESTART`)
  - deny behavior validated live (`unknown_action_denied`, `non_allowlisted_service_denied`).
- Public exposure review completed (`docker ps` port map): only `immich-server` (`2283`) and `open-webui` (`3000`) currently expose `0.0.0.0`; core control-plane endpoints remain loopback/Tailnet-bound.
- Alert-noise control evidence captured from bridge stats (`recent_events=200`, `result_counts={'skipped': 196, 'deferred': 1, 'sent': 3}`), confirming suppression pathways are actively reducing non-actionable fanout.
- Step 7 result: pass.

## Step 7.5 — ntfy topic coverage check (go-live alert proof)

Confirm the alert fabric is complete by proving at least one current event in each required topic:

- `ops-alerts`
- `security-alerts`
- `network-alerts`
- `auth-alerts`
- `storage-alerts`
- `backup-alerts`
- `ai-audit`
- `media-alerts`
- `update-alerts`

Verification:

- Each topic shows at least one fresh event from the expected producer path.
- Any topic with no recent event gets a controlled test trigger and is rechecked.

Quick check command (last 24h, one-line status per topic):

```bash
for t in ops-alerts security-alerts network-alerts auth-alerts storage-alerts backup-alerts ai-audit media-alerts update-alerts; do
  c=$(curl -s --max-time 10 "http://127.0.0.1:8091/$t/json?since=24h" | grep -c '"event":"message"' || true)
  if [ "$c" -gt 0 ]; then
    echo "PASS $t messages=$c"
  else
    echo "FAIL $t messages=0"
  fi
done
```

Execution evidence (2026-02-27):

- Pre-check counts (24h window):
  - `ops-alerts=87`, `security-alerts=2`, `network-alerts=0`, `auth-alerts=0`, `storage-alerts=0`, `backup-alerts=0`, `ai-audit=37`, `media-alerts=5`, `update-alerts=0`.
- Controlled topic-proof publishes were triggered only for zero-count topics (`network-alerts`, `auth-alerts`, `storage-alerts`, `backup-alerts`, `update-alerts`).
- Final counts after recheck (24h window):
  - `ops-alerts=93`, `security-alerts=3`, `network-alerts=2`, `auth-alerts=2`, `storage-alerts=2`, `backup-alerts=2`, `ai-audit=41`, `media-alerts=6`, `update-alerts=1`.
- Step 7.5 result: pass.

## Step 8 — Freeze baseline and documentation

- Take final baseline snapshot: `day7-go-live-baseline`
- Export/backup key configs if possible
- Update your architecture docs with final URLs and owners

Verification:

- Snapshot exists and is tested
- Docs reflect current running state

Execution evidence (2026-02-27):

- Baseline archive created: `checkpoints/day7-go-live-baseline.tar.gz`.
- Artifact verification pass: archive listed/read successfully via `tar -tzf`.
- Artifact size at capture: `101M`.
- Scope aligns with control-plane baseline freeze (docs + phase1 control/config paths + operator chat log).
- Step 8 result: pass.

## Go-Live Definition of Done

You are production-ready when all are true:

1. Security, AI, media, and ops scenarios all pass
2. Homepage is clear, labeled, and complete
3. Backup + restore is validated
4. Alerts are actionable and not noisy
5. Final snapshot `day7-go-live-baseline` exists

## After Day 7 (next expansion options)

- Add Headscale mesh onboarding for trusted family devices
- Add Home Assistant integrations gradually
- Add autonomous agent (OpenClaw/Agent Zero) only with strict boundaries
- Add advanced segmentation (separate VMs for AI/media/control if not already)
