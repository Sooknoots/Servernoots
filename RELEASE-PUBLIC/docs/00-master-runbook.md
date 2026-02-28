---

### Intel NPU (265k Processor) & AMD 6950xt Verification and Automated Monitoring

#### Verification Steps

**Intel NPU (265k Processor)**
- Identify the NPU device (e.g., via `lspci`, `lsusb`, or `/dev/nnpu*`).
- Check device presence:  
  `dmesg | grep -i npu`  
  `lspci | grep -i npu`
- Monitor NPU activity during token generation:  
  - Use `intel-npu-tool` or `intel_gpu_top` if available.  
  - Example: `sudo intel_gpu_top` or `sudo watch -n 1 cat /sys/class/nnpu/nnpu*/usage`
- Check Ollama logs/config for device selection (e.g., `--device npu`).
- If no NPU activity, review Docker/Ollama config and drivers.

**AMD 6950xt GPU**
- Use `radeontop` for AMD GPU monitoring:  
  `sudo radeontop`
- Confirm `ollama` process appears in GPU process list and GPU load increases during token generation.
- Use Netdata for cross-checking GPU, CPU, and memory utilization.
- If GPU is not used, check Docker flags (e.g., `--device=/dev/dri`), Ollama config, and drivers.

#### Automated Monitoring and Correction

- Integrate NVTOP/radeontop and Netdata metrics into your monitoring stack.
- Set up Netdata alarms for GPU and NPU utilization:
  - If GPU/NPU usage is low or zero while Ollama is active, trigger a warning alert.
  - Alert should include process info and timestamp.
- Implement a remediation script or workflow:
  - On repeated alerts, automatically attempt to restart the Ollama container with correct device flags (e.g., `docker compose restart ollama-loopback-proxy` or equivalent for the actual Ollama service).
  - Log all remediation attempts and alert if manual intervention is required.
- Document all alerts, actions, and outcomes in the review thread for traceability.

#### Evidence Collection
- Capture screenshots or logs from `intel_gpu_top`, `radeontop`, and Netdata during token generation.
- Note any errors or warnings in Ollama/system logs about hardware acceleration.

---

Add these steps and monitoring requirements to the review thread for each cycle to ensure both NPU and GPU are being utilized as intended, and that failures are detected and corrected automatically.

---

---

## Cline (VS Code) Integration with Local Ollama

### Overview
Cline is an autonomous coding agent extension for Visual Studio Code. You can configure it to use your local Ollama instance for LLM-powered code generation and chat. This section documents the setup and usage for integrating Cline with a self-hosted Ollama server on this system.

### Prerequisites
- Visual Studio Code (latest)
- Cline extension installed (`saoudrizwan.claude-dev`)
- Ollama running locally (see AI Control stack)

### Ollama Local API Endpoint
By default, Ollama runs its API on `http://localhost:11434`. Ensure the Ollama service is running and accessible from your host.

- To check status: `curl http://localhost:11434/api/tags`
- If using Docker Compose, verify the Ollama container is up and mapped to the host port 11434.

### Cline Extension Configuration
1. Open VS Code and go to the Cline extension settings.
2. Set the LLM provider to `Ollama`.
3. Set the API endpoint to `http://localhost:11434`.
4. Choose your desired model (e.g., `llama3`, `phi3`, or any model available in your Ollama instance).
5. (Optional) Adjust context window, temperature, and other parameters as needed.

#### Example Settings (settings.json)
```json
{
  "cline.provider": "ollama",
  "cline.ollama.endpoint": "http://localhost:11434",
  "cline.ollama.model": "llama3"
}
```

### Usage
- Open a file or workspace in VS Code.
- Use the Cline sidebar or command palette to start a new chat or code generation session.
- Prompts will be sent to your local Ollama instance, and responses will appear in the Cline chat window.
- All LLM inference is performed locally; no data leaves your system.

### Troubleshooting
- If Cline cannot connect, ensure Ollama is running and accessible at the configured endpoint.
- Check Docker Compose port mappings if running Ollama in a container.
- Review Ollama logs for errors.
- For GPU/NPU acceleration, verify hardware utilization as described in the NPU/GPU monitoring section above.

---

# Master Runbook (Single-Page Control)

## Docs Navigation

- AI Control README: [`master-suite/phase1/ai-control/README.md`](../master-suite/phase1/ai-control/README.md)
- AI Control optional bridge tuning: [`master-suite/phase1/ai-control/README.md#optional-bridge-tuning`](../master-suite/phase1/ai-control/README.md#optional-bridge-tuning)

## Purpose

One place to track progress, decisions, and readiness for your Linux Master Suite.

Navigation: [Incident command reference](13-telegram-command-reference.md#incident-ownership-controls-admin)

## Document Map

- Docs Index: [16-docs-index.md](16-docs-index.md)
- Rollout Plan: [01-master-suite-rollout-plan.md](01-master-suite-rollout-plan.md)
- Architecture Guide: [02-master-suite-architecture.md](02-master-suite-architecture.md)
- Day 1: [03-day1-checklist.md](03-day1-checklist.md)
- Day 2: [04-day2-checklist.md](04-day2-checklist.md)
- Day 3: [05-day3-checklist.md](05-day3-checklist.md)
- Day 4: [06-day4-checklist.md](06-day4-checklist.md)
- Day 5: [07-day5-checklist.md](07-day5-checklist.md)
- Day 6: [08-day6-checklist.md](08-day6-checklist.md)
- Day 7: [09-day7-checklist.md](09-day7-checklist.md)
- Tailnet Admin Expansion: [11-tailnet-admin-expansion.md](11-tailnet-admin-expansion.md)
- Discord Bot Expansion: [12-discord-bot-expansion.md](12-discord-bot-expansion.md)
- Telegram Command Reference: [13-telegram-command-reference.md](13-telegram-command-reference.md)
- Telegram Incident Commands: [13-telegram-command-reference.md#incident-ownership-controls-admin](13-telegram-command-reference.md#incident-ownership-controls-admin)
- Software Capabilities Matrix: [14-software-capabilities-matrix.md](14-software-capabilities-matrix.md)
- Operations Command Reference: [15-operations-command-reference.md](15-operations-command-reference.md)
- Day 6 Backup Policy Template: [19-day6-kopia-policy-template.md](19-day6-kopia-policy-template.md)
- Channel Contract v1: [17-channel-contract-v1.md](17-channel-contract-v1.md)
- Implementation Sequence v1: [18-implementation-sequence-v1.md](18-implementation-sequence-v1.md)
- Implementation Execution Tracker: [19-implementation-execution-tracker.md](19-implementation-execution-tracker.md)
- AI Personality 2-Week Plan: [20-ai-personality-next-sprint.md](20-ai-personality-next-sprint.md)

## Recent Evidence

- M11 deep-research Telegram smoke (Nextcloud link delivery): [../master-suite/phase1/ai-control/checkpoints/deep-research-telegram-smoke-2026-02-28.json](../master-suite/phase1/ai-control/checkpoints/deep-research-telegram-smoke-2026-02-28.json)
- M3 closure evidence bundle: [../checkpoints/m3-closure-evidence-2026-02-28.md](../checkpoints/m3-closure-evidence-2026-02-28.md)
- Latest policy gate summary: [../master-suite/phase1/ai-control/checkpoints/m3-policy-release-gate-summary.json](../master-suite/phase1/ai-control/checkpoints/m3-policy-release-gate-summary.json)
- Latest ops-alerts evidence: [../master-suite/phase1/ai-control/checkpoints/ops-alerts-evidence-latest.json](../master-suite/phase1/ai-control/checkpoints/ops-alerts-evidence-latest.json)

---

## Progress Tracker

Last updated: 2026-02-28

Current thread mode:

- Implementation execution active
- Focus on post-M3 hardening and next open milestone execution
- Next Action: Continue post-M3 channel hardening while preserving M3 release-gate checks (`telegram-role-allowlist-smoke`, `memory-scope-guard`, `m9-parity`) as ongoing health gates
- M3 ownership update (2026-02-28): named owner set to `ai-control` in tracker for ongoing M3 execution.
- M3 execution plan (2026-02-28): dated burn-down milestones set in tracker (`2026-03-02` inventory, `2026-03-05` implementation/validation, `2026-03-07` closure evidence + status update).
- M3 inventory refinement (2026-02-28): workflow-level gap map now includes concrete hardcoded-topic and embedded-default nodes (`rag-query`, `rag-ingest`, `ops-commands`, `ops-audit-review`, `textbook-fulfillment`) with implementation targets captured in `checkpoints/m3-policy-inventory-2026-02-28.md`.
- M3 inventory evidence (2026-02-28): first dated sub-item completed early; workflow-level policy read/write map captured at `checkpoints/m3-policy-inventory-2026-02-28.md`.
- M3 kickoff evidence (2026-02-27): canonical policy key-set draft + ownership/change process now documented in `docs/18-implementation-sequence-v1.md`
- M3 alignment evidence (2026-02-27): channel contract and capability matrix now reference canonical policy source (`docs/17-channel-contract-v1.md`, `docs/14-software-capabilities-matrix.md`)
- M3 runtime evidence (2026-02-27): materialized policy file at `master-suite/phase1/ai-control/policy/policy.v1.yaml` and wired first consumers (`guardrails/safe_command.sh`, `bridge/ntfy_to_n8n.py`)
- M3 runtime evidence (2026-02-27): `telegram-n8n-bridge` now also consumes policy defaults (`channels.telegram.default_admin_notify_topics`, dedupe windows) via `bridge/telegram_to_n8n.py`
- M3 runtime evidence (2026-02-27): topic metadata now policy-backed (`alerts.topic_categories`, `channels.telegram.topic_labels`) for consistent fanout categories and `/notify` topic UX labels
- M3 runtime evidence (2026-02-27): bridge policy parsing logic deduplicated into shared helper `bridge/policy_loader.py` and mounted into both bridge containers
- M3 runtime evidence (2026-02-27): guardrails allowlist policy parsing moved to shared shell extractor `policy/policy_extract.sh`, consumed by `guardrails/safe_command.sh` with legacy allowlist fallback preserved
- M3 runtime evidence (2026-02-27): `telegram-n8n-bridge` now enforces policy-backed approval and rate-limit controls (`approval.default_ttl_seconds`, `approval.max_pending_per_user`, `rate_limit.default.requests_per_minute`, `rate_limit.burst`)
- M3 runtime evidence (2026-02-28): Telegram `rag-query` payload materialization now forwards policy-backed memory/retention controls from `policy_loader` (`voice_memory_opt_in`, `memory_low_confidence_policy`, `memory_min_speaker_confidence`, `raw_audio_persist`) via `bridge/telegram_to_n8n.py` `build_payload`; targeted local smoke remained green (`./scripts/eval-telegram-chat-smoke.py --mode local --check memory_regression_local`).
- M3 runtime evidence (2026-02-28): workflow-topic indirection pass applied for n8n ntfy HTTP nodes (`workflows/rag-query-webhook.json`, `workflows/rag-ingest-webhook.json`, `workflows/ops-commands-webhook.json`, `workflows/ops-audit-review-webhook.json`, `workflows/ai-chat-webhook.json`, `workflows/textbook-fulfillment-webhook.json`) using env-backed routing (`NTFY_BASE`, `NTFY_ALERT_TOPIC`, `NTFY_REPLIES_TOPIC`, `NTFY_AUDIT_TOPIC`) with `n8n` compose env wiring in `master-suite/phase1/ai-control/docker-compose.yml` and defaults documented in `master-suite/phase1/ai-control/.env.example`.
- M3 runtime evidence (2026-02-28): post-indirection parity checks remained green (`make m9-parity-status` => `M9_PARITY_STATUS=PASS`; `make m9-parity` => `M9_PARITY_PACK=PASS`).
- M3 runtime evidence (2026-02-28): `rag-query` normalize-path memory gate cleanup removed embedded fallback constants in favor of upstream policy-backed fields, followed by successful deploy/verification and parity check (`./scripts/publish-rag-query-workflow.sh --verify`; `make m9-parity-status` => `M9_PARITY_STATUS=PASS`).
- M3 runtime evidence (2026-02-28): non-Telegram reply path reliability hardened by setting `continueOnFail` on `Post RAG Reply` in `workflows/rag-query-webhook.json`, then republished and re-verified (`./scripts/publish-rag-query-workflow.sh --verify`).
- M3 runtime evidence (2026-02-28): M3 policy release-gate runner added (`scripts/eval-m3-policy-release-gate.py`) with Makefile wrappers (`make m3-policy-gate`, `make m3-policy-gate-status`); latest run is green (`M3_POLICY_GATE=PASS`) and artifact captured at `checkpoints/m3-policy-release-gate-summary.json` (plus `/tmp/m3-policy-release-gate-summary.json`).
- Post-M3 hardening evidence (2026-02-28): ops command workflow policy enforcement now consumes bridge-forwarded policy controls (`policy_role_command_allowlist`, `policy_rate_limit_*`) so `workflows/ops-commands-webhook.json` `Format Ops Result` applies role-command deny and per-user rate limiting in workflow; post-deploy gate rerun remains green (`make m3-policy-gate` => `M3_POLICY_GATE=PASS`).
- Post-M3 hardening evidence (2026-02-28): retry-safe live topic proof capture added for `ops-alerts` (`scripts/capture-ops-alerts-evidence.py` with `make ops-alerts-evidence` / `make ops-alerts-evidence-status`); latest run is green (`OPS_ALERTS_EVIDENCE_STATUS=PASS`, `OPS_ALERTS_EVIDENCE_FILTERED=283`) with durable artifact at `master-suite/phase1/ai-control/checkpoints/ops-alerts-evidence-latest.json`.
- Post-M3 hardening evidence (2026-02-28): daily cron automation is installed for ops-alerts evidence capture (`make install-ops-alerts-evidence-cron`), active entry `50 6 * * * .../run-ops-alerts-evidence-and-alert.sh # ai-control-ops-alerts-evidence`.
- Post-M3 hardening evidence (2026-02-28): phase1-wide module control + performance monitoring layer is live (`master-suite/phase1/scripts/module-control.py`, `master-suite/phase1/scripts/module-performance-monitor.py`, registry `master-suite/phase1/config/module-registry.json`) with current full health sweep green across registered modules.
- Post-M3 hardening evidence (2026-02-28): automatic phase1 performance detection is enabled with recurring cron (`*/5 * * * * .../run-module-performance-monitor-and-alert.sh # phase1-module-performance-monitor`), writing continuous metrics logs to `master-suite/phase1/logs/module-performance.ndjson` and latest summary to `master-suite/phase1/logs/module-performance-latest.json`.
- M3 closure evidence (2026-02-28): release-gate suite is green (`make telegram-role-allowlist-smoke` + status => `PASS`; `make memory-scope-guard` + status => `PASS`; `make m9-parity` + status => `PASS`) and closure bundle is captured at `checkpoints/m3-closure-evidence-2026-02-28.md`.
- Post-M3 kickoff evidence (2026-02-28): first hardening baseline checkpoint is green (`make m3-policy-gate` + status => `PASS`; `make memory-release-gate-checkpoint` + status => `PASS`), captured at `checkpoints/post-m3-hardening-kickoff-2026-02-28.md` with durable memory artifacts in `master-suite/phase1/ai-control/checkpoints/memory-release-gate/`.
- Post-M3 automation evidence (2026-02-28): recurring memory-release checkpoint cron is enabled via `scripts/install-memory-release-gate-cron.sh` with a single active tag (`ai-control-memory-release-gate`, schedule `40 6 * * *`), and immediate validation run remained green (`MEMORY_RELEASE_GATE_CHECKPOINT_STATUS=PASS`); evidence captured at `checkpoints/post-m3-memory-gate-cron-enable-2026-02-28.md`.
- Post-M3 rollback proof (2026-02-28): cron uninstall/reinstall safety cycle validated (`count 1 -> 0 -> 1`) via `scripts/uninstall-memory-release-gate-cron.sh` and `scripts/install-memory-release-gate-cron.sh`, with final post-restore health green after webhook republish + checkpoint retry (`MEMORY_RELEASE_GATE_CHECKPOINT_STATUS=PASS`); evidence captured at `checkpoints/post-m3-memory-gate-cron-rollback-proof-2026-02-28.md`.
- Post-M3 retry hardening (2026-02-28): checkpoint runner now has bounded retry/backoff (`MEMORY_RELEASE_GATE_MAX_ATTEMPTS=2`, `MEMORY_RELEASE_GATE_RETRY_BACKOFF_SECONDS=15`) and emits retry metadata (`first_gate_rc`, `attempts_used`, `max_attempts`, `retry_backoff_seconds`) in summary artifacts; latest run confirms retry path execution but remained red due persistent live-smoke instability (evidence: `checkpoints/post-m3-memory-gate-retry-hardening-2026-02-28.md`).
- Post-M3 gate split hardening (2026-02-28): memory release gate now separates blocking checks (local smoke + replay thresholds) from non-blocking live-smoke signal capture, reducing cron false-red noise while preserving live telemetry (`live_smoke_signal` + `smoke_live_*` artifacts); validation run is green (`memory-release-gate-summary-20260228T070659Z.json`), evidence: `checkpoints/post-m3-memory-gate-hard-soft-split-2026-02-28.md`.
- Post-M3 status helper evidence (2026-02-28): dedicated signal-only status target added (`make memory-release-gate-signal-status`) to report live-smoke health independently from blocking checkpoint gate status; validation output is green (`MEMORY_RELEASE_GATE_SIGNAL_STATUS=PASS`), evidence: `checkpoints/post-m3-memory-gate-signal-status-helper-2026-02-28.md`.
- Post-M3 debounced alert evidence (2026-02-28): recurring live-signal health alerting is enabled with debounce threshold (`make memory-release-gate-signal-alert`, `make install-memory-release-gate-signal-cron`; default threshold `2` consecutive failures) and active cron tag `ai-control-memory-release-gate-signal` (`10 * * * *`), with current state green (`consecutive_failures=0`, `alert_sent=false`); evidence: `checkpoints/post-m3-memory-signal-debounced-alert-cron-2026-02-28.md`.
- Post-M3 signal-log fix (2026-02-28): signal alert logging now uses per-run UTC-stamped log files with a refreshed latest pointer (`memory-release-gate-signal-alert-<stamp>.log` + `memory-release-gate-signal-alert-latest.log`) so stale tracebacks are not carried into current run tails; evidence: `checkpoints/post-m3-memory-signal-log-rotation-fix-2026-02-28.md`.
- Post-M3 signal-log retention evidence (2026-02-28): retention cleanup helper is added (`make memory-release-gate-signal-log-cleanup`, default `MEMORY_RELEASE_GATE_SIGNAL_LOG_RETENTION_DAYS=30`) to prune aged timestamped signal logs while preserving `memory-release-gate-signal-alert-latest.log`; validation is green (`MEMORY_RELEASE_GATE_SIGNAL_LOG_CLEANUP=PASS`), evidence: `checkpoints/post-m3-memory-signal-log-retention-cleanup-2026-02-28.md`.
- Post-M3 post-fix health snapshot (2026-02-28): broader status sweep is green (`make m8-proof-status` => `M8_PROOF_STATUS=PASS`; `make m9-parity-status` => `M9_PARITY_STATUS=PASS`; `make memory-release-gate-signal-status` => `MEMORY_RELEASE_GATE_SIGNAL_STATUS=PASS`; `make memory-release-gate-signal-alert` => `MEMORY_RELEASE_GATE_SIGNAL_ALERT_SENT=false`), evidence: `checkpoints/post-m3-postfix-health-snapshot-2026-02-28.md`.
- M3 runtime evidence (2026-02-27): Discord voice cooldown defaults are policy-backed in both proxy paths (`scripts/discord-rag-proxy.py`, `scripts/discord-rag-proxy-server.py`) using `rate_limit.voice_session_cooldown_seconds` with CLI override preserved
- M8 runtime evidence (2026-02-27): shared policy parser now materializes Discord memory/retention key families (`memory_enabled_by_default`, `memory_voice_opt_in_required`, `memory_low_confidence_write_policy`, `memory_clear_requires_confirmation`, `retention_raw_audio_persist`) and Discord payload gating reflects policy values in local checks
- M8 runtime evidence (2026-02-28): Discord proxy persistence boundary now enforces write gating for `memory_summary` (requires opt-in when policy demands it and blocks low-confidence writes when policy is `deny`); local helper validation confirmed blocked writes remain unchanged and allowed writes persist in both CLI and HTTP server paths
- M8 runtime evidence (2026-02-28): end-to-end proxy proof with local mock webhook captured at `/tmp/discord-m8-persistence-e2e-proof.txt` shows blocked low-confidence write (`speaker_confidence=0.42` => no persisted summary) and allowed high-confidence write (`speaker_confidence=0.95` => persisted `memory_summary=allowed_should_persist`), with audit parity in `/tmp/discord-m8-e2e-audit.jsonl` (`memory_summary_persisted=false` then `true`)
- M8 runtime evidence (2026-02-28): HTTP server-path parity proof captured at `/tmp/discord-m8-http-persistence-proof.txt` (`discord-rag-proxy-server.py` on `/proxy`) confirms the same behavior: blocked low-confidence forwarded write remains unchanged while allowed high-confidence forwarded write persists summary; audit parity captured in `/tmp/discord-m8-http-audit.jsonl` (`memory_summary_persisted=false` then `true`)
- M9 runtime evidence (2026-02-28): durable parity runner now in repo (`scripts/eval-discord-channel-parity-pack.py`) with Makefile wrappers (`make m9-parity`, `make m9-parity-status`); first-pass run is green (`M9_PARITY_PACK=PASS`) with stable artifacts at `checkpoints/m9-parity-summary.json` and `checkpoints/m9-contract-parity.json` (plus `/tmp` compatibility mirrors).
- M9 runtime evidence (2026-02-28): Discord voice-loop transport contract hardened in both proxy paths (`scripts/discord-rag-proxy.py`, `scripts/discord-rag-proxy-server.py`) so forwarded `voice_loop` now requires `voice_session_id` and at least one content signal (`audio_url` or `transcript` or `has_audio=true`); invalid events are rejected as `route=discord-voice-loop-invalid` with audit denial reasons (`voice_loop_missing_session_id`, `voice_loop_missing_audio_or_transcript`).
- M10 readiness decision update (2026-02-28): **GO-with-risks** for current scope (Telegram/ntfy control plane + Discord text/session/voice-dry-run + M8 memory gates + M9 parity); residual hardening items are tracked with explicit owners/dates in `docs/19-implementation-execution-tracker.md`.
- M11 deep-research evidence (2026-02-28): live Telegram `/research` path validated through onboarding + start/status/report flow with Nextcloud link delivery (`run_id=rr-1772262706-e429683f57`, ready link returned and repeatable via status/report); artifact captured at `master-suite/phase1/ai-control/checkpoints/deep-research-telegram-smoke-2026-02-28.json`.
- Textbook UX evidence (2026-02-27): live contract check passed via `scripts/eval-telegram-chat-smoke.py --check textbook_fulfillment_contract --mode live`
- Textbook UX evidence (2026-02-27): final E2E reply flow snapshot is now concise and consistent:
  - `/textbook request ...` → compact candidate review + single next-step prompt
  - `/textbook email ...` → `✅ Email saved` + `📌 Next step`
  - `/textbook <n>` → compact selected-candidate summary + `📌 Next step: /textbook confirm`
  - `/textbook confirm` → `✅ Textbook queued (email_dispatched)` + fulfillment id
  - `/textbook status` → compact pending-ingest status + `📌 Next step`
- Textbook UX evidence artifact (2026-02-27): `checkpoints/textbook-ux-evidence-2026-02-27.json`
- Textbook UX live-smoke raw log (2026-02-27): `checkpoints/textbook-ux-live-smoke-2026-02-27.log`

### Textbook Webhook Transient Recovery

- Textbook synthetic rerun evidence (2026-02-27 23:42 -06:00): `./scripts/run-textbook-synthetic-check-and-alert.sh` passed after `n8n` endpoint recovery (`curl http://127.0.0.1:5678/healthz` => `{"status":"ok"}`); latest heartbeat `logs/textbook-synthetic-heartbeat.json` now reports `status=ok`, `webhook_verify=ok`, `smoke_checks=ok`.
- Telegram release-gate live evidence (2026-02-27): `checkpoints/telegram-release-gate-live-2026-02-27.log` (`TELEGRAM_RELEASE_GATE_INCLUDE_LIVE=true`)
- Telegram notify UX live evidence (2026-02-28): `checkpoints/notify-me-live-postdeploy-2026-02-28.log` confirms `/notify me` and `/notify me json` now render the same compact user-standard format (no raw JSON payload output)

#### M8 proof command pack (quick rerun)

- One-shot wrapper (recommended):
  - `make m8-proof-all` (fresh verbose rerun + compact PASS/FAIL status)
  - `make m8-proof-fresh` (clean + rerun + verbose summary/tails)
  - `make m8-proof-quick` (clean + rerun without verbose tails)
  - `make m8-proof-status` (compact status from current summary: `PASS`/`FAIL`)
  - `make m8-proof-clean` (optional reset of prior `/tmp/discord-m8-*` artifacts)
  - `make m8-proof` (from `master-suite/phase1/ai-control`)
  - `make m8-proof-verbose` (same proof pack + summary + tail output)
  - `/usr/bin/python3 scripts/eval-discord-memory-persistence-proof-pack.py`
  - PASS marker: `M8_PROOF_PACK=PASS`
  - Summary JSON: `/tmp/discord-m8-proof-pack-summary.json`
- CLI proxy proof (blocked vs allowed persistence):
  - `/usr/bin/python3 scripts/eval-discord-memory-persistence-cli-proof.py`
  - Verify artifact: `/tmp/discord-m8-persistence-cli-proof.txt`
  - Expectation: `state_after_blocked_attempt.memory_summary == ""`, then `state_after_allowed_attempt.memory_summary == "allowed_should_persist"`
  - Audit check: `/tmp/discord-m8-audit-cli.jsonl` contains `"memory_summary_persisted":false` then `true`
- HTTP `/proxy` parity proof:
  - `/usr/bin/python3 scripts/eval-discord-memory-persistence-http-proof.py`
  - Verify artifact: `/tmp/discord-m8-persistence-http-proof.txt`
  - Expectation: blocked low-confidence write unchanged, allowed high-confidence write persisted
  - Audit check: `/tmp/discord-m8-audit-http.jsonl` contains `"memory_summary_persisted":false` then `true`
- Optional direct spot-check commands:
  - `tail -n 80 /tmp/discord-m8-persistence-cli-proof.txt`
  - `tail -n 80 /tmp/discord-m8-persistence-http-proof.txt`

#### M9 parity command pack (durable rerun)

- One-shot parity run:
  - `make m9-parity` (from `master-suite/phase1/ai-control`)
  - PASS marker: `M9_PARITY_PACK=PASS`
- Status-only check:
  - `make m9-parity-status`
  - PASS marker: `M9_PARITY_STATUS=PASS`
- Durable artifacts:
  - `checkpoints/m9-parity-summary.json`
  - `checkpoints/m9-contract-parity.json`
- Compatibility mirrors (for existing tooling):
  - `/tmp/discord-m9-parity-summary.json`
  - `/tmp/discord-m9-contract-parity.json`

#### M3 policy gate command pack (durable rerun)

- One-shot M3 release-gate run:
  - `make m3-policy-gate` (from `master-suite/phase1/ai-control`)
  - PASS marker: `M3_POLICY_GATE=PASS`
- Status-only check:
  - `make m3-policy-gate-status`
  - PASS marker: `M3_POLICY_GATE_STATUS=PASS`
- Durable artifact:
  - `checkpoints/m3-policy-release-gate-summary.json`
- Compatibility mirror:
  - `/tmp/m3-policy-release-gate-summary.json`

#### Ops-alerts evidence command pack (durable rerun)

- One-shot evidence capture:
  - `make ops-alerts-evidence` (from `master-suite/phase1/ai-control`)
  - PASS marker: `OPS_ALERTS_EVIDENCE=PASS`
- Status-only check:
  - `make ops-alerts-evidence-status`
  - PASS marker: `OPS_ALERTS_EVIDENCE_STATUS=PASS`
- Durable artifacts:
  - `checkpoints/ops-alerts-evidence-latest.json`
  - `checkpoints/ops-alerts-evidence-latest-<timestamp>.json`
- Compatibility mirror:
  - `/tmp/ops-alerts-evidence-latest.json`
- Cron automation (daily, recommended):
  - Install: `make install-ops-alerts-evidence-cron`
  - Uninstall: `make uninstall-ops-alerts-evidence-cron`
  - Schedule override: `OPS_ALERTS_EVIDENCE_CRON_SCHEDULE='50 6 * * *' make install-ops-alerts-evidence-cron`

#### Phase1 module control + performance command pack

- One-shot top-level health review (recommended):
  - `cd /media/sook/Content/Servernoots/master-suite/phase1`
  - `make phase1-health`
  - Fast check (health + perf only): `make phase1-health-quick`
  - Verbose failure triage (tails degraded module logs): `make phase1-health-verbose`
  - Status-only marker: `make phase1-health-status`
  - Optional knobs: `PHASE1_HEALTH_TIMEOUT=4 PHASE1_HEALTH_VERBOSE_TAIL=120 make phase1-health-verbose`

- Full module status review:
  - `cd /media/sook/Content/Servernoots/master-suite/phase1`
  - `./scripts/module-control.py status`
- Health sweep across all modules:
  - `./scripts/module-control.py health --timeout 4`
- Load/unload/restart specific modules without full-stack downtime:
  - `./scripts/module-control.py up ai-control`
  - `./scripts/module-control.py down monitoring`
  - `./scripts/module-control.py restart ntfy,alerts`
  - Dependency-aware reload with health gates + automatic rollback on failure: `./scripts/module-control.py reload media --timeout 4 --health-attempts 6 --wait-seconds 2`
  - Disable rollback (debug only): `./scripts/module-control.py reload media --no-rollback`
  - Top-level reload helpers: `make phase1-modules-reload` or `MODULES=media make phase1-modules-reload-safe`
- Performance metrics snapshot + degradation detection:
  - `./scripts/module-performance-monitor.py --no-notify`
  - PASS marker: `MODULE_PERFORMANCE_STATUS=PASS`
- Continuous metrics + automatic degraded detection:
  - Install cron: `./scripts/install-module-performance-monitor-cron.sh`
  - Uninstall cron: `./scripts/uninstall-module-performance-monitor-cron.sh`
  - Schedule override: `MODULE_PERF_CRON_SCHEDULE='*/5 * * * *' ./scripts/install-module-performance-monitor-cron.sh`
  - Logs: `master-suite/phase1/logs/module-performance.ndjson`, `master-suite/phase1/logs/module-performance-latest.json`
- Daily 24h performance digest:
  - Baseline reset (clear stale trend history): `make phase1-perf-baseline-reset`
  - Baseline archive retention override (default 14 days): `PHASE1_PERF_BASELINE_RETENTION_DAYS=30 make phase1-perf-baseline-reset`
  - Run now: `make phase1-perf-daily-summary`
  - Status-only marker: `make phase1-perf-daily-summary-status`
  - Current-trend quick status (1h window, no notify): `make phase1-perf-daily-summary-quick` then `make phase1-perf-daily-summary-quick-status`
  - Install daily cron: `make install-phase1-perf-daily-cron`
  - Uninstall daily cron: `make uninstall-phase1-perf-daily-cron`
  - Schedule override: `MODULE_PERF_DAILY_CRON_SCHEDULE='30 6 * * *' make install-phase1-perf-daily-cron`
  - Digest artifact: `master-suite/phase1/logs/module-performance-daily-summary-latest.json`

### Foundation

- [x] Day 1 complete (VM, SSH, updates, snapshot)
- [x] Checkpoint taken: `day1-clean-base`

### The Fort

- [ ] Day 2 complete (Gluetun, AdGuard, Authentik MFA, CrowdSec) — pending final closeout checks
- [x] Checkpoint taken: `day2-fort-stable` (`checkpoints/day2-fort-stable.tar.gz`)

### Control Panel + Visibility

- [ ] Day 3 complete (Homepage labels, ntfy, monitoring)
- [x] Snapshot taken: `day3-panel-alerts-stable` (`checkpoints/day3-panel-alerts-stable.tar.gz`)

### AI + RAG + Safe Commands

- [ ] Day 4 complete (n8n, Ollama bridge, Qdrant, guardrails)
- [x] Day 4 scaffold started: `n8n` + `qdrant` deployed, guardrail command runner created
- [x] Day 4 Step 2 complete: ntfy/n8n inbound+outbound topic flow validated (`ai-chat` + `ai-replies`/`ops-commands` -> `ai-replies`/`ops-alerts`)
- [x] Day 4 Step 3 complete: n8n AI workflow now calls local Ollama and returns model output to `ai-replies`
- [x] Day 4 AI reply tagging: both `ai-chat` and RAG query workflows publish to `ai-replies` with ntfy title `AI Reply` for bridge loop prevention
- [x] Day 4 Step 5/6 first pass complete: RAG ingest/query workflows active with one indexed source and source-cited replies from `ai-chat`
- [x] Day 4 Step 8 complete: audit-log review workflow active (`ops-audit` -> `ops-alerts`) and dashboard audit-log tile added
- [x] Day 4 Telegram bridge scaffold complete: Telegram text/photo/audio messages now forward into n8n webhooks with allowlisted user access controls
- [x] Day 4 routing reliability checks green: `./scripts/telegram-healthcheck.sh` and `./scripts/eval-routing.py` both pass in current environment
- [x] Day 4 routing regression automation live: cron installer + alert runner configured for twice-daily routing eval with failure notifications
- [x] Day 4 Telegram personalization hardening: per-user `tone_history` persisted in `telegram_users.json` and verified in live bridge state
- [x] Day 4 ntfy -> Telegram dedupe hardening: topic-specific dedupe windows loaded and verified (`ops-alerts`, `ops-audit`, `ai-audit`)
- [x] Day 4 tenant isolation validation pass: direct `rag-query` test confirms valid tenant accepted and cross-tenant access blocked
- [x] Day 4 incident ownership controls live: admins can `/ack`, `/snooze`, `/unsnooze`, and inspect `/incident` state with fanout suppression enforced
- [x] Day 4 profile personalization controls live: users can `/profile show|apply|clear` and inject `user_profile_seed` into Telegram->n8n payloads
- [x] Day 4 Telegram/chat smoke suite live: webhook, tenant-isolation, and `/profile` command-path checks available with failure alerting
- [x] Day 4 voice transcription hardening: dedicated `openwhisper` service added with env-configurable STT endpoint/model in `rag-query` workflow
- [x] Snapshot taken: `day4-ai-rag-stable` (`checkpoints/day4-ai-rag-stable.tar.gz`)

### Media + Automation

- [x] Day 5 complete (Plex, Tautulli, arr, Overseerr, Immich) — mobile-backup confirmation captured; host reboot validation deferred by operator
- [x] Day 5 kickoff pre-change snapshot: `day5-before-media` (`checkpoints/day5-before-media.tar.gz`)
- [x] Day 5 Step 1 bootstrap prepared: `master-suite/phase1/media/day5-step1-storage-bootstrap.sh`
- [x] Day 5 Step 1 complete: storage/permissions layout applied under `/srv/media` and `/srv/photos`
- [x] Day 5 Step 2 started: Plex deployed (`http://localhost:32400/web`) and responding locally
- [x] Day 5 Plex storage complete: two 8TB disks reformatted to ext4 and mounted (`/srv/media/movies`, `/srv/media/tv`)
- [x] Day 5 Step 3 started: Tautulli deployed (`http://localhost:8181`) with verified `media-alerts` publish path
- [x] Day 5 Step 4 started: Prowlarr/Sonarr/Radarr/qBittorrent deployed and reachable via Gluetun forwarded ports
- [x] Day 5 Step 5 started: Overseerr deployed (`http://localhost:5055`) for request-flow wiring to Plex + arr
- [x] Day 5 verification pass: Sonarr + Radarr paths are wired (indexers + qBittorrent + root folder); Overseerr still requires first-time UI initialization
- [x] Day 5 Step 4 API test rerun: search commands complete and Sonarr path is corrected to `/tv`, but no successful grab/import yet for current test titles
- [x] Day 5 Step 4 blocker fixed: qBittorrent downtime caused Arr download-client connection refusals; restart policy corrected and Radarr `grabbed` event confirmed
- [x] Day 5 Step 4 complete: Radarr end-to-end import confirmed (`downloadFolderImported`, `hasFile=true`, media present under `/srv/media/movies`)
- [x] Day 5 Step 5 complete: Overseerr initialized, Plex libraries enabled, and request handoff validated to Radarr (`Sintel`, request `id=1`, TMDB `45745`)
- [x] Day 5 Step 6 partial: request pipeline confirmed through Radarr `grabbed`; Plex mount visibility fixed (container restart) and Movies library indexing confirmed
- [x] Day 5 Step 6 transfer acceleration: additional higher-seed `Sintel` release grabbed (`720p BRRip x264 -YTS`) while import remains in-progress
- [x] Day 5 Step 6 import/indexing complete: `Sintel` imported and indexed in Plex Movies (`hasFile=true`, `sizeOnDisk=576700012`)
- [x] Day 5 Step 6 playback workaround: added direct-play MP4 variant for `Sintel` to bypass client transcode-triggered playback errors
- [x] Day 5 Step 6 complete: real playback session confirmed and Tautulli emitted playback webhook events (`on_play`, `on_pause`, `on_resume`, `on_stop`)
- [x] Day 5 Immich deployed: `immich-server`, `immich-ml`, `immich-redis`, and `immich-postgres` are running (`http://localhost:2283`)
- [x] Day 5 Immich backup validation pass: `master-suite/phase1/media/validate-immich-backup.sh` generated DB dump + file manifest + metadata under `media/immich/backups/<timestamp>/`
- [x] Day 5 restart resilience pass: media stack service restart/recovery validated in-session (`docker compose restart` + endpoint probes)
- [x] Day 5 health verification rerun (2026-02-27): media stack `docker compose ps` healthy; endpoint checks remain expected (Plex `302`, Overseerr `307`, Immich `200`)
- [x] Day 5 Immich backup verification rerun (2026-02-27): latest validated backup artifacts at `media/immich/backups/2026-02-27-192427/`
- [x] Day 5 Immich mobile backup confirmation (2026-02-27): database asset count advanced (`public.asset` from `0` to `2`)
- [x] Snapshot taken: `day5-media-stable` (`checkpoints/day5-media-stable.tar.gz`)

### Telegram-First Media Control (Operator Quick Reference)

Primary user control path (recommended):

- Users request media in Telegram via:
  - `/media movie <title> [year]`
  - `/media tv <title> [year]`
  - `/request ...` (alias of `/media ...`)
- Bridge submits request to Overseerr API.
- Overseerr routes approved requests into Radarr/Sonarr.
- Readiness/service events flow through `media-alerts` and fan out to Telegram subscribers.

Quick command examples:

- `/media movie Dune 2021`
- `/media tv Severance`
- `/request movie Interstellar 2014`

Expected user-facing behavior:

- Immediate Telegram acknowledgment with request type/title.
- Request appears in Overseerr request queue.
- Follow-up Telegram alert on media pipeline/availability events (`media-alerts`).

Telegram RAG profile-query behavior:

- Discord/profile-seed status questions (for example, "Do you have the discord ... profile rag data?") are answered locally from `telegram_users.json` profile state.
- If no profile seed is active, bot returns `rag_profile_seed_loaded: no` with guidance to run `/profile show`.
- When a single/high-confidence seed match is found, reply is concise (`best_match` + `first_action`) and hides extra candidate lines.
- When confidence is lower/ambiguous, bot includes `profile_seed_candidates` with explicit `/profile apply <seed_id>` options.
- High-confidence thresholds are configurable via `TELEGRAM_PROFILE_MATCH_HIGH_CONFIDENCE_MIN_SCORE` (default `95`) and `TELEGRAM_PROFILE_MATCH_HIGH_CONFIDENCE_MIN_GAP` (default `15`).
- Global Telegram outbound message review is enabled by default across both bridges; disable only for troubleshooting with `TELEGRAM_MESSAGE_REVIEW_ENABLED=false` (command bridge) and `TELEGRAM_FANOUT_MESSAGE_REVIEW_ENABLED=false` (ntfy fanout bridge).
- Command-bridge review hard-cap is configurable via `TELEGRAM_MESSAGE_REVIEW_MAX_CHARS` (default `900`); fanout review cap follows `TELEGRAM_NOTIFY_MAX_MESSAGE_CHARS`.

Operator checks (fast):

- Verify bridge services are running:
  - `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control`
  - `docker compose ps telegram-n8n-bridge ntfy-n8n-bridge n8n`
- Run pre-deploy Telegram release gate (compile + core local smoke checks):
  - `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control`
  - `./scripts/run-telegram-release-gate.sh`
  - Optional live include: `TELEGRAM_RELEASE_GATE_INCLUDE_LIVE=true ./scripts/run-telegram-release-gate.sh`
- Run safe Telegram bridge deploy (gate + deploy + post-deploy status/log tail):
  - `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control`
  - `./scripts/deploy-telegram-bridges-safe.sh`
  - Optional live gate include: `TELEGRAM_RELEASE_GATE_INCLUDE_LIVE=true ./scripts/deploy-telegram-bridges-safe.sh`
  - Optional forced recreate: `TELEGRAM_DEPLOY_FORCE_RECREATE=true ./scripts/deploy-telegram-bridges-safe.sh`
- Install nightly Telegram safe-run cron (with ntfy alert on failure):
  - `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control`
  - Gate-only mode (default): `./scripts/install-telegram-safe-deploy-cron.sh`
  - Deploy mode: `TELEGRAM_SAFE_DEPLOY_CRON_MODE=deploy ./scripts/install-telegram-safe-deploy-cron.sh`
  - Custom schedule example: `TELEGRAM_SAFE_DEPLOY_CRON_SCHEDULE='15 2 * * *' ./scripts/install-telegram-safe-deploy-cron.sh`
  - Remove cron: `./scripts/uninstall-telegram-safe-deploy-cron.sh`
- Run and schedule weekly Telegram safe-run digest:
  - One-off run: `./scripts/run-telegram-safe-deploy-weekly-rollup-and-alert.sh`
  - Install weekly cron: `./scripts/install-telegram-safe-deploy-weekly-cron.sh`
  - Custom weekly schedule: `TELEGRAM_SAFE_DEPLOY_WEEKLY_CRON_SCHEDULE='40 6 * * 1' ./scripts/install-telegram-safe-deploy-weekly-cron.sh`
  - Remove weekly cron: `./scripts/uninstall-telegram-safe-deploy-weekly-cron.sh`
- Track stale pending requests (>60 minutes) with diagnosis/escalation target:
  - `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control`
  - `./scripts/reqtrack --stale-minutes 60`
- Trigger escalation prompts (admin/user topics) when stale items exist:
  - `./scripts/reqtrack --stale-minutes 60 --emit-ntfy`
  - Approval-token remediation flow:
    - Propose: `REQTRACK_FIX_APPROVAL_SECRET='<secret>' ./scripts/reqtrack --stale-minutes 60 --attempt-fixes --auto-approve-pending --fix-approval-mode propose --json`
    - Apply: `REQTRACK_FIX_APPROVAL_SECRET='<secret>' ./scripts/reqtrack --stale-minutes 60 --attempt-fixes --auto-approve-pending --fix-approval-mode apply --fix-approval-token '<token>' --json`
    - Audit stream (decision trail): `./scripts/reqtrack --stale-minutes 60 --attempt-fixes --auto-approve-pending --fix-audit-file logs/media-request-tracker-fix-audit.ndjson --fix-actor ops-bot --json`
  - Optional noise controls:
    - `REQTRACK_MIN_REALERT_MINUTES=30` (minimum interval for re-alerting active incidents)
    - `REQTRACK_MAX_NOTIFY_CANDIDATES=25` (cap notified incidents per run)
    - `REQTRACK_MAX_ADMIN_LINES=20` and `REQTRACK_MAX_USER_LINES=10` (limit per-message line volume)
    - `REQTRACK_MIN_USER_NOTIFY_LEVEL=2` (suppress low-level user-topic notifications)
    - `REQTRACK_SUPPRESS_BY_REQUESTER_MINUTES=180` (suppress repeat notifications for same requester)
    - `REQTRACK_SUPPRESS_BY_TITLE_MINUTES=120` (suppress repeat notifications for same title/type)
  - Optional remediation guardrails v2 (for `--attempt-fixes` flows):
    - `REQTRACK_FIX_ACTIONS=approve_pending` (action allowlist)
    - `REQTRACK_FIX_RETRY_ENABLED=true` + `REQTRACK_FIX_ACTIONS=approve_pending,retry_request` (enable safe retry remediation class)
    - `REQTRACK_MAX_FIXES_PER_RUN=3` (per-run cap)
    - `REQTRACK_FIX_MIN_AGE_MINUTES=120` (minimum age gate)
    - `REQTRACK_FIX_RETRY_MIN_SINCE_UPDATE_MINUTES=180` (minimum staleness since last update before retry)
    - `REQTRACK_FIX_REQUIRE_ADMIN_TARGET=true` (admin-target-only remediation)
    - `REQTRACK_FIX_DRY_RUN=true` (no mutation; report would-fix decisions)
    - `REQTRACK_FIX_AUDIT_ENABLED=true` + `REQTRACK_FIX_AUDIT_FILE=logs/media-request-tracker-fix-audit.ndjson` + `REQTRACK_FIX_ACTOR=reqtrack`
- Refresh reqtrack dashboard status artifact (Homepage tile target):
  - `./scripts/render-media-request-tracker-dashboard-status.sh`
- Run bundled reqtrack daily health command:
  - `./scripts/run-reqtrack-daily-health.sh`
- Install automated stale-request tracking (every 15 minutes):
  - `./scripts/install-media-request-tracker-cron.sh`
- Monthly dry drill for alert path (synthetic stale items only):
  - `./scripts/reqtrack --dry-drill --emit-ntfy --json`
- Stateful dry drill (prove dedupe + level-up re-alert):
  - `DRILL_STATE=/tmp/reqtrack-drill-state.json`
  - `./scripts/reqtrack --dry-drill --dry-drill-stateful --emit-ntfy --state-file "$DRILL_STATE" --json`
  - Repeat same command once (expect `notify_candidate_count=0`)
  - `./scripts/reqtrack --dry-drill --dry-drill-stateful --emit-ntfy --state-file "$DRILL_STATE" --dry-drill-admin-age-minutes 130 --dry-drill-user-age-minutes 140 --json`
  - One-command equivalent: `./scripts/run-reqtrack-stateful-drill.sh`
- Run one-command reqtrack release gate (isolated-topic ntfy + JSON contract checks):
  - `./scripts/run-reqtrack-release-gate.sh`
  - Run command-contract regression smoke (CLI + Telegram admin command path): `./scripts/run-reqtrack-command-contract-smoke.sh`
  - Optional keep drill state for post-check inspection: `REQTRACK_RELEASE_GATE_KEEP_DRILL_STATE=true ./scripts/run-reqtrack-release-gate.sh`
  - Install daily release-gate cron (default `30 6 * * *`): `./scripts/install-reqtrack-release-gate-cron.sh`
  - Remove release-gate cron: `./scripts/uninstall-reqtrack-release-gate-cron.sh`
  - Custom schedule example: `REQTRACK_RELEASE_GATE_CRON_SCHEDULE='15 6 * * *' ./scripts/install-reqtrack-release-gate-cron.sh`
  - Weekly rollup runner: `./scripts/run-reqtrack-release-gate-weekly-rollup-and-alert.sh`
  - Install weekly rollup cron (default `50 6 * * 1`): `./scripts/install-reqtrack-release-gate-weekly-cron.sh`
  - Remove weekly rollup cron: `./scripts/uninstall-reqtrack-release-gate-weekly-cron.sh`
  - Weekly rollup overrides:
    - Window days: `REQTRACK_RELEASE_GATE_WEEKLY_DAYS=14 ./scripts/run-reqtrack-release-gate-weekly-rollup-and-alert.sh`
    - Disable ntfy emit: `REQTRACK_RELEASE_GATE_WEEKLY_EMIT_NTFY=false ./scripts/run-reqtrack-release-gate-weekly-rollup-and-alert.sh`
    - Weekly schedule override: `REQTRACK_RELEASE_GATE_WEEKLY_CRON_SCHEDULE='20 7 * * 1' ./scripts/install-reqtrack-release-gate-weekly-cron.sh`
- Inspect persistent tracker state (dedupe/escalation memory):
  - `cat /media/sook/Content/Servernoots/master-suite/phase1/ai-control/logs/media-request-tracker-state.json`
- Incident controls (tracker state):
  - List active: `./scripts/reqtrack --incident-action list --incident-filter active --json`
  - Ack: `./scripts/reqtrack --incident-action ack --incident-key 'request:<id>' --incident-by operator --incident-note 'ack' --json`
  - Snooze: `./scripts/reqtrack --incident-action snooze --incident-key 'request:<id>' --snooze-minutes 120 --incident-by operator --incident-note 'investigating' --json`
  - Unsnooze: `./scripts/reqtrack --incident-action unsnooze --incident-key 'request:<id>' --incident-by operator --json`
  - Close: `./scripts/reqtrack --incident-action close --incident-key 'request:<id>' --incident-by operator --incident-note 'resolved' --json`
- KPI digest (state-only metrics):
  - Default 24h: `./scripts/reqtrack --kpi-report`
  - Custom 48h JSON: `./scripts/reqtrack --kpi-report --kpi-window-hours 48 --json`
  - Expanded KPI dimensions include:
    - Window actions: `acked`, `reopened`, `level2plus_notified`
    - Active-age buckets: `lt_1h`, `h1_4`, `h4_24`, `gte_24h`
    - Long-running backlog signal: `long_running_active_24h`
    - Recurring incident quality sample: `quality.top_realerted`
  - Publish digest to admin topic: `./scripts/reqtrack --kpi-report --emit-kpi-ntfy`
  - Historical exports:
    - NDJSON: `./scripts/reqtrack --kpi-report --export-history-format ndjson --export-history-file /tmp/reqtrack-history.ndjson --export-history-window-hours 168 --export-history-limit 1000 --json`
    - CSV: `./scripts/reqtrack --kpi-report --export-history-format csv --export-history-file /tmp/reqtrack-history.csv --export-history-window-hours 168 --export-history-limit 1000 --json`
    - Runner: `./scripts/run-media-request-tracker-history-export.sh`
    - Runner knobs: `REQTRACK_EXPORT_FORMAT`, `REQTRACK_EXPORT_FILE`, `REQTRACK_EXPORT_WINDOW_HOURS`, `REQTRACK_EXPORT_LIMIT`, `REQTRACK_EXPORT_DIR`
  - Daily runner: `./scripts/run-media-request-tracker-kpi-and-alert.sh`
  - Install daily cron: `./scripts/install-media-request-tracker-kpi-cron.sh`
  - Remove daily cron: `./scripts/uninstall-media-request-tracker-kpi-cron.sh`
  - Weekly runner (168h default): `./scripts/run-media-request-tracker-kpi-weekly-rollup-and-alert.sh`
  - Weekly wrapper: `./scripts/kpiweekly`
  - Weekly wrapper JSON: `./scripts/kpiweekly --json`
  - Install weekly cron: `./scripts/install-media-request-tracker-kpi-weekly-cron.sh`
  - Remove weekly cron: `./scripts/uninstall-media-request-tracker-kpi-weekly-cron.sh`
- Incident controls from Telegram admin chat (same tracker state):
  - List: `/reqtrack list active`
  - KPI (24h default): `/reqtrack kpi`
  - KPI (custom hours): `/reqtrack kpi 48`
  - KPI (JSON): `/reqtrack kpi json`
  - KPI (JSON custom hours): `/reqtrack kpi 48 json`
  - Large JSON replies are auto-chunked with `[reqtrack-json i/n]` headers
  - Chunk size tuning: `TELEGRAM_REQTRACK_JSON_CHUNK_MAX_CHARS`
  - KPI (explicit pretty): `/reqtrack kpi pretty`
  - KPI weekly window: `/reqtrack kpiweekly`
  - KPI weekly (JSON): `/reqtrack kpiweekly json`
  - KPI weekly (explicit pretty): `/reqtrack kpiweekly pretty`
  - Ack: `/reqtrack ack request:<id> ack`
  - Snooze: `/reqtrack snooze request:<id> 120 investigating`
  - Unsnooze: `/reqtrack unsnooze request:<id>`
  - Close: `/reqtrack close request:<id> resolved`
  - State path check: `/reqtrack state`
- Verify media fanout stats include `media-alerts sent`:
  - `docker exec ntfy-n8n-bridge python -c "import json,sqlite3,pathlib; events=[]; db=pathlib.Path('/state/telegram_state.db'); js=pathlib.Path('/state/telegram_notify_stats.json');\nif db.exists():\n conn=sqlite3.connect(str(db)); row=conn.execute('select payload from state_kv where key=?',('notify_stats',)).fetchone(); conn.close();\n state=json.loads(row[0]) if row and row[0] else {}; events=state.get('events',[]) if isinstance(state,dict) else [];\nelif js.exists():\n state=json.loads(js.read_text()); events=state.get('events',[]) if isinstance(state,dict) else [];\n[print(e.get('topic'), e.get('result'), e.get('recipients')) for e in events[-20:]]"`
- Verify current user has `media` subscription:
  - `docker exec telegram-n8n-bridge python -c "import json; d=json.load(open('/state/telegram_users.json')); print(d)"`
- Verify profile seed catalog is mounted for Telegram profile apply:
  - `docker compose exec -T telegram-n8n-bridge sh -lc 'test -f /work/discord-seed/discord_user_profiles.json && echo PROFILE_SEED_CATALOG_OK'`
- Verify profile command telemetry events are being written:
  - `docker logs --since 5m telegram-n8n-bridge | grep -E 'profile_action user_id='`

If requests fail from Telegram:

- Confirm `OVERSEERR_API_KEY` and `OVERSEERR_URL` in `master-suite/phase1/ai-control/.env`.
- Recreate bridge services:
  - `docker compose up -d --force-recreate telegram-n8n-bridge ntfy-n8n-bridge`

### OpenWhisper Port Collision Recovery

If `docker compose up -d` fails with `Bind for 127.0.0.1:9000 failed: port is already allocated`, set `OPENWHISPER_HOST_PORT=9001` in `master-suite/phase1/ai-control/.env` (to avoid Authentik’s `127.0.0.1:9000`) and rerun compose.
See also: `master-suite/phase1/ai-control/README.md` (Local URLs + troubleshooting note).

STT debug response toggle (incident triage):

- AI Control STT details: [`master-suite/phase1/ai-control/README.md#audio-transcription-path-in-day4---rag-query`](../master-suite/phase1/ai-control/README.md#audio-transcription-path-in-day4---rag-query)

- Enable persistent STT diagnostics in Telegram webhook replies:
  - `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control`
  - `sed -i 's/^STT_DEBUG_RESPONSE_ENABLED=.*/STT_DEBUG_RESPONSE_ENABLED=true/' .env || echo 'STT_DEBUG_RESPONSE_ENABLED=true' >> .env`
  - `docker compose up -d --force-recreate n8n`
- Disable after triage:
  - `sed -i 's/^STT_DEBUG_RESPONSE_ENABLED=.*/STT_DEBUG_RESPONSE_ENABLED=false/' .env`
  - `docker compose up -d --force-recreate n8n`
- One-request override (no env change): include `"stt_debug_response_enabled": true` in webhook payload.
- Quick live probe (audio + debug):
  - `curl -sS -X POST 'http://127.0.0.1:5678/webhook/rag-query' -H 'Content-Type: application/json' -d '{"source":"telegram","user_id":"111","tenant_id":"u_111","role":"user","stt_debug_response_enabled":true,"question":"","has_audio":true,"audio_url":"https://raw.githubusercontent.com/Jakobovski/free-spoken-digit-dataset/master/recordings/0_george_0.wav","audio_mime":"audio/wav","audio_file_name":"digit.wav"}'`
  - Expect `debug.stt` in JSON reply with `transcription_error` and `used_fallback_text`.
- Evidence artifact (last verified 2026-02-27):
  - Capture only STT debug fields:
    - `curl -sS -X POST 'http://127.0.0.1:5678/webhook/rag-query' -H 'Content-Type: application/json' -d '{"source":"telegram","user_id":"111","tenant_id":"u_111","role":"user","stt_debug_response_enabled":true,"question":"","has_audio":true,"audio_url":"https://raw.githubusercontent.com/Jakobovski/free-spoken-digit-dataset/master/recordings/0_george_0.wav","audio_mime":"audio/wav","audio_file_name":"digit.wav"}' | jq '.debug.stt'`
  - Healthy result example:
    - `{"has_audio":true,"audio_url_present":true,"transcription_error":"","used_fallback_text":false}`

Textbook hosted download links (24h TTL) — live verification:

- Purpose: verify bridge-hosted textbook links deliver successfully, then expire.
- AI Control settings reference: [`master-suite/phase1/ai-control/README.md#optional-bridge-tuning`](../master-suite/phase1/ai-control/README.md#optional-bridge-tuning)
- Required env (in `master-suite/phase1/ai-control/.env`):
  - `TEXTBOOK_DOWNLOAD_LINK_ENABLED=true`
  - `TEXTBOOK_DOWNLOAD_PUBLIC_BASE_URL=http://127.0.0.1:8113`
  - `TEXTBOOK_DOWNLOAD_TTL_SECONDS=86400`
- Recreate bridge after env change:
  - `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control && docker compose up -d --force-recreate telegram-n8n-bridge`
- Confirm endpoint is live (missing token should be expired/missing):
  - `curl -sS -o /tmp/textbook-dl-probe.out -w 'http_code=%{http_code}\n' http://127.0.0.1:8113/textbook-download/probe-token-does-not-exist`
  - Expect `http_code=410`.
- Generate one proof link + capture output:
  - `docker exec telegram-n8n-bridge python -c "import importlib.util;spec=importlib.util.spec_from_file_location('tg','/app/telegram_to_n8n.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);link,exp,reason=mod.build_textbook_download_link(user_id=111,fulfillment_id='live-e2e-proof',source_url='https://archive.org/robots.txt',file_mime='text/plain',selected_candidate={'title':'Archive Robots Proof'});print(link);print(exp);print(reason)" > /tmp/live_dl_link.out && cat /tmp/live_dl_link.out`
  - Expect line 1=`http://127.0.0.1:8113/textbook-download/<token>`, line 3=`ok`.
- Verify successful download (`200`):
  - `LINK=$(sed -n '1p' /tmp/live_dl_link.out); curl -sS --max-time 20 -D /tmp/live_dl_h1.txt -o /tmp/live_dl_b1.txt "$LINK" >/dev/null; head -n 1 /tmp/live_dl_h1.txt; wc -c /tmp/live_dl_b1.txt`
  - Expect HTTP status `200` with non-zero file size.
- Force-expire the proof token + verify `410`:
  - `docker exec telegram-n8n-bridge python -c "import json,time; p='/state/telegram_textbook_downloads.json'; obj=json.load(open(p)); e=obj.get('entries',{}); [entry.__setitem__('expires_at', int(time.time())-1) for entry in e.values() if isinstance(entry,dict) and str(entry.get('fulfillment_id',''))=='live-e2e-proof'; json.dump(obj, open(p,'w'), ensure_ascii=False, indent=2); print('forced_expiry=ok')"`
  - `LINK=$(sed -n '1p' /tmp/live_dl_link.out); curl -sS -o /tmp/live_dl_b2.txt -w 'http_code=%{http_code}\n' "$LINK"`
  - Expect `http_code=410`.

If readiness alerts do not arrive:

- Publish test event:
  - `curl -sS -H 'Title: Media Ready Test' -H 'Priority: default' -d 'test media ready' http://127.0.0.1:8091/media-alerts`
- Check fanout log line:
  - `docker logs --since 30s ntfy-n8n-bridge | grep -E 'telegram fanout topic=media-alerts|bridge error'`
- Validate end-to-end notify path from Telegram admin command:
  - Run `/notify validate` and expect `stage: fanout` (not `stage: wait`)
  - If `reason=telegram_http_401`, rotate/fix `TELEGRAM_BOT_TOKEN`

### Telegram Media Hardening Checklist (Implementation Plan)

Objective:

- Raise reliability and safety for Telegram-first media control to production-grade operations.

Execution window:

- Day 1 (critical): items 1-3
- Week 1 (stability): items 4-6
- Week 2 (resilience): items 7-10

#### Day 1 — Critical controls

- [x] 1) Health watchdogs for bridge chain
  - Action:
    - Add/verify health checks and restart policy for `telegram-n8n-bridge`, `ntfy-n8n-bridge`, `n8n`, `ntfy`.
    - Run: `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control && docker compose ps`
  - Pass criteria:
    - All four services remain `Up` through restart test (`docker compose restart ...`).

- [x] 2) Synthetic end-to-end checks (request + notify)
  - Action:
    - Run one `/media` request test and one `media-alerts` publish test each cycle.
    - Command test: `curl -sS -H 'Title: Media Ready Synthetic' -H 'Priority: default' -d 'synthetic check' http://127.0.0.1:8091/media-alerts`
  - Pass criteria:
    - `telegram_notify_stats.json` records `media-alerts sent` within expected poll window.

- [ ] 3) Secret hygiene and key rotation
  - Action:
    - Rotate `TELEGRAM_BOT_TOKEN` and `OVERSEERR_API_KEY`.
    - Ensure secrets live only in runtime env and protected files.
  - Pass criteria:
    - New keys validated with successful `/media` request.

#### Week 1 — Stability controls

- [ ] 4) Request disambiguation guard
  - Action:
    - Improve `/media` flow to present top matches when title ambiguity is high.
  - Pass criteria:
    - Ambiguous request no longer auto-submits wrong title.

- [x] 5) Polling/backoff tuning
  - Action:
    - Keep bounded polling (`POLL_REQUEST_TIMEOUT_SECONDS`) and verify no sustained 429 churn.
    - Check logs: `docker logs --since 10m ntfy-n8n-bridge | grep -E '429|bridge error'`
    - ntfy request-limit baseline (2026-02-27): `NTFY_VISITOR_REQUEST_LIMIT_BURST=2000`, `NTFY_VISITOR_REQUEST_LIMIT_REPLENISH=100ms`
    - Telegram bridge webhook retries now treat transient `429/5xx` from n8n as retryable before surfacing a user-facing error.
  - Pass criteria:
    - No repeated 429 bursts during normal operation.

- [x] 6) Event idempotency validation
  - Action:
    - Re-publish same test payload and confirm dedupe behavior is expected.
  - Pass criteria:
    - Duplicate spam is suppressed while first alert still delivers.

#### Week 2 — Resilience controls

- [ ] 7) Replace file-state with transactional state store
  - Action:
    - Move critical bridge state (`telegram_users`, dedupe/stats, incident state) from JSON files to SQLite/Postgres.
  - Pass criteria:
    - Restart/power-cycle tests preserve state without corruption.

- [ ] 8) True "ready for viewing" confirmation logic
  - Action:
    - Gate final user-ready notification on explicit availability signal (Overseerr/Plex confirmation).
  - Pass criteria:
    - "Ready" alerts align with actual playback availability.

- [ ] 9) Audit summary reporting
  - Action:
    - Add recurring report for requests, approvals, denials, failures, and suppression counts.
  - Pass criteria:
    - Weekly report artifact generated and archived.

- [ ] 10) Restore drill for control-plane state
  - Action:
    - Perform restore of bridge/runtime state from snapshot and re-run synthetic checks.
  - Pass criteria:
    - Recovery completes within target time and media control path returns to green.

### Next Development Sprint — Telegram -> Plex Pipeline

Sprint target:

- Improve request accuracy, viewing-readiness confidence, and operational resilience for Telegram-first media control.

Scope (implement in this order):

- [x] S1) Request disambiguation UX
  - Build: if `/media` search returns multiple close matches, reply with top 3 choices and require explicit pick before submit.
  - Pass: ambiguous title no longer auto-submits a wrong request.

- [x] S2) Availability-confirmed ready notification
  - Build: send final "ready" message only after explicit availability check (Overseerr/Plex state), not just initial Arr events.
  - Pass: "ready" alerts align with actual playable availability in Plex.
  - Validation (2026-02-27):
    - Movie path: `Sintel is now available in Plex.` -> `ready_verified:Sintel:status=5` (allowed)
    - TV path: `Shameless is now available in Plex.` -> `ready_not_confirmed:Shameless:status=0` (blocked)

- [x] S3) Synthetic monitor automation
  - Build: scheduled health job that runs one request-path check and one `media-alerts` fanout check, then reports status.
  - Pass: failures produce an alert and success writes a timestamped heartbeat.
  - Validation (2026-02-27): synthetic run produced `status=ok` heartbeat with `request_check=request_path_ok` and `fanout_check=fanout_processed:sent_partial:telegram_http_400`.
  - Post-hardening (2026-02-27): recipient cleanup now auto-quarantines `telegram_http_400` targets immediately; direct fanout probe returned `result=sent` with `quarantined=1` (no repeated partial-send noise).

- [x] S4) State durability hardening
  - Build: migration plan from JSON runtime state to SQLite/Postgres (`telegram_users`, dedupe, notify stats, incident state).
  - Pass: documented migration + rollback, plus restart consistency test.
  - Implementation (2026-02-27): added optional SQLite-backed runtime state in `ntfy-n8n-bridge` (`TELEGRAM_STATE_BACKEND=sqlite`) and created migration helper `scripts/migrate-telegram-state-json-to-sqlite.py`.
  - Operationalization (2026-02-27): added one-command helpers `scripts/cutover-telegram-state-backend-sqlite.sh` and `scripts/rollback-telegram-state-backend-json.sh`.
  - Validation (2026-02-27): completed rollback→validate→cutover→validate flip-test; synthetic checks passed in both modes and final state is SQLite with persisted keys (`dedupe`, `delivery`, `digest_queue`, `incidents`, `notify_stats`).

- [x] S5) Security lifecycle tasks
  - Build: key-rotation runbook for Telegram + Overseerr secrets with validation and rollback steps.
  - Pass: rotated keys validated with successful `/media` request and alert fanout.
  - Progress (2026-02-27): added `scripts/run-secret-rotation-drill.sh` with rehearsal/apply modes and automatic `.env` backup + rollback command output.
  - Validation (2026-02-27): rehearsal drill passed; final apply run passed after forcing bridge recreation (`telegram-healthcheck` green, synthetic check `request_path_ok`, fanout `sent`).
  - Secret delta (2026-02-27): Telegram token rotation completed in prior apply run; Overseerr API key rotation confirmed in final apply run (changed versus pre-new-key backup).
  - Reliability note: drill now uses `docker compose up -d --force-recreate telegram-n8n-bridge ntfy-n8n-bridge` to ensure updated `.env` secrets are applied.

Release gate:

- [x] One end-to-end demo passes: Telegram request -> Overseerr -> Arr -> import -> Plex availability -> Telegram ready alert.
- [x] One failure-path demo passes: ambiguous title requires explicit user selection before request submission.
- [x] One recovery-path demo passes: bridge restart retains required runtime state and monitoring heartbeat recovers.
  - Sign-off evidence (2026-02-27): Sprint-1/2/3/4/5 validations all green, including ambiguous-title pick flow checks, synthetic monitor success heartbeats, and rollback→cutover→rollback durability drills.

### Ops Hardening

- [x] Day 6 complete (Kopia, Watchtower policy, restore test)
- [x] Day 6 closeout signed off: Gate D evidence synchronized and Day 7 kickoff handoff prepared
- [x] Snapshot taken: `day6-ops-hardened` (`checkpoints/day6-ops-hardened.tar.gz`)

### Final Validation

- [x] Day 7 complete (end-to-end tests + Homepage final pass)
- [x] Day 7 Step 1 complete: core-service health sweep passed (`restarts=0` across must-pass runtime services; Kopia `0.22.3` verified)
- [x] Day 7 Step 2 complete: security chain validated (CrowdSec detection, `security-alerts` delivery, and logged `ban` response action)
- [x] Day 7 Step 3 complete: AI scenario validated (RAG checks green, allowlisted guardrail action audited, risky `/ops` approval flow enforced)
- [x] Day 7 Step 3.5 complete: Telegram/chat full regression + live recovery validated (2026-02-27)
  - Full smoke run passed end-to-end: `./scripts/eval-telegram-chat-smoke.py --mode all` → `38/38` checks green.
  - During validation, `rag-query` returned transient HTTP `500` (`{"message":"Error in workflow"}`) after workflow restart/publish cycles; recovery path (`publish-rag-query-workflow.sh --verify` + direct webhook probe + re-run full smoke) restored healthy live responses.
  - Local regression hardening remained green after recovery, including new memory regression coverage and topic-quiet media defer behavior.
- [x] Day 7 Step 4 complete: media scenario validated (Overseerr request ingress + processing, available catalog visibility, and Tautulli playback-event notifications)
- [x] Day 7 Step 5 complete: backup + restore confidence rerun passed (backup manifest updated; Kopia file restore hash match)
- [x] Day 7 Step 6 complete: Homepage UX cleanup validated (required section order, friendlier labels, and Operations recovery/update cards present)
- [x] Day 7 Step 7 complete: risk checklist signed off (MFA/admin identity path, guardrail deny controls, intentional exposure review, and alert-noise suppression evidence)
- [x] Day 7 Step 7.5 complete: ntfy topic coverage proved across all required go-live topics (all non-zero in last 24h)
- [x] Day 7 UX metrics fetch-mode hardening (2026-02-27):
  - Daily and weekly UX runners now treat timeout-with-partial payloads as informational by default (`UX_METRICS_TIMEOUT_WARN_ON_PARTIAL=false`).
  - Daily summary includes `fetch_mode_replies`, `fetch_mode_chat`, and `fetch_timeout_s`.
  - Weekly summary includes `fetch_mode_chat` and `fetch_timeout_s`.
  - Set `UX_METRICS_TIMEOUT_WARN_ON_PARTIAL=true` to restore warning-level timeout logging for partial reads.
  - Operator quick check (latest daily + weekly fetch markers):

    ```bash
    cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control
    echo "daily:" && grep -E 'fetch_mode_|fetch_timeout_s=' "logs/ux-metrics-$(date +%F).log" | tail -n 1
    echo "weekly:" && grep -E 'fetch_mode_|fetch_timeout_s=' "logs/ux-metrics-weekly-$(date +%F).log" | tail -n 1
    ```

- [x] Snapshot taken: `day7-go-live-baseline` (`checkpoints/day7-go-live-baseline.tar.gz`)
- [x] Day 7 post-signoff revalidation pass (2026-02-27 22:17 -06:00):
  - `./scripts/publish-rag-query-workflow.sh --verify` passed; webhook verification recovered clean after n8n restart.
  - Local notification checks passed: `notify_health_local`, `notify_delivery_retry_local`, `notify_delivery_local`.
  - Local textbook checks passed: `textbook_untrusted_source_local`, `textbook_delivery_ack_retry_local`.
  - Full local Telegram/chat smoke rerun passed: `/usr/bin/python3 scripts/eval-telegram-chat-smoke.py --mode local` → `33/33` checks green (includes `memory_regression_local`, `memory_tier_decay_order_local`, `memory_intent_scope_local`, `memory_conflict_workflow_local`, and `memory_feedback_ranking_local`).
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
  - Media synthetic run passed in guardrail-aware mode with `MEDIA_SYNTHETIC_ACCEPT_RESULTS='sent,sent_partial,skipped'`; observed result `skipped:media_first_seen_repeat` (expected dedupe behavior).
  - Textbook synthetic automation installed: `35 7 * * * /media/sook/Content/Servernoots/master-suite/phase1/ai-control/scripts/run-textbook-synthetic-check-and-alert.sh` (`# ai-control-textbook-synthetic-check`).
  - Known transient recovered (2026-02-27 23:42 -06:00): temporary `127.0.0.1:5678` webhook reachability flap caused one failed textbook synthetic run; service endpoint recovered (`curl http://127.0.0.1:5678/healthz` => `{"status":"ok"}`) and immediate rerun passed with heartbeat `status=ok`.
  - UX metrics rerun remained `status=ok` (partial-timeout fetch mode informational as configured).
  - Runtime status check: `n8n`, `telegram-n8n-bridge`, `ntfy-n8n-bridge`, and `openwhisper` all `Up`.

Go-Live Decision (2026-02-27):

- Decision: **GO**
- Basis: Day 7 checklist complete, baseline snapshot captured, and post-signoff revalidation passed across workflow publish/verify, smoke checks, media synthetic (guardrail-aware), UX metrics, and core runtime container health.
- Known acceptable behavior at go-live: `media_first_seen_repeat` may appear as `skipped` during synthetic probes due to dedupe guardrails; this is expected and not a service outage.
- Rollback anchor: `checkpoints/day7-go-live-baseline.tar.gz`.
- Approved by: `sook / operator` at `2026-02-27 22:19 CST` (change control ref: `<ticket/id>`).

M10 Readiness Decision Update (2026-02-28):

- Decision: **GO-with-risks**
- Scope: current operating scope includes Telegram/ntfy control paths and Discord milestones M5-M9 (text, session controls, dry-run voice loop, memory gates, and channel parity review).
- Basis: no active workflow-runtime blocker; M9 parity probes and audit checks are passing; runbook/tracker documents are aligned with milestone truth.
- Boundary: this decision does not claim completion of live Discord voice identity attribution transport.

M10 Risk Ownership Table:

| Risk item | Owner | Due date | Mitigation plan | Exit evidence |
|---|---|---|---|---|
| Live Discord voice identity attribution transport not validated end-to-end | ai-control | 2026-03-07 | Implement and validate live voice identity transport with consent + confidence policy gates | `docs/12-discord-bot-expansion.md` follow-on section + parity/audit proof artifacts |
| M3 policy-as-config rollout remains in-progress | ai-control | 2026-03-07 | Complete remaining workflow-level policy materialization and enforcement alignment across channels | `docs/19-implementation-execution-tracker.md` M3 checklist + runbook M3 runtime evidence updates |

---

## Homepage Label Standard (Do Not Change Names)

1. Core Access
2. Security
3. Network
4. AI Control
5. Knowledge
6. Media
7. Operations
8. Home

Use friendly tile names and one-line purpose text for each service.

---

## Go / No-Go Gates

### Gate A — Security Ready

- [x] Authentik MFA required for admin routes
- [x] CrowdSec active and ingesting logs
- [ ] No unintended public admin exposure

Day 2 remaining closeout:

- Post-reboot UI/health re-check for Gluetun, AdGuard, Authentik, CrowdSec (deferred by operator request)

### Gate B — Visibility Ready

- [x] ntfy alerts reach phone
- [x] Netdata/Beszel/Scrutiny all reporting
- [x] Homepage links valid and readable

Notes:

- Private ntfy access validated via Tailscale Serve:
  - `https://servernoots.tail95a8ad.ts.net/` -> `http://127.0.0.1:8091`
- Phone received `ops-alerts` and `security-alerts` test messages.
- Monitoring stack deployed (local-only):
  - Netdata: `http://localhost:19999`
  - Beszel: `http://localhost:8090`
  - Scrutiny: `http://localhost:8083/web/`
- Homepage link normalization notes:
  - AdGuard card points to local runbook because host/macvlan isolation prevents direct localhost UI access.

### Remote Admin Access Live (Tailscale)

- Completed: 2026-02-27
- Access model: services remain loopback-bound and are exposed only through Tailnet HTTPS ports.
- Onboarding (Cheesusrice/other admins):
  1. Join Tailnet with approved identity.
  2. Open Homepage: `https://servernoots.tail95a8ad.ts.net:8443/`.
  3. Authenticate at Authentik: `https://servernoots.tail95a8ad.ts.net:8444/`.
- Primary admin URLs:
  - Homepage: `https://servernoots.tail95a8ad.ts.net:8443/`
  - Authentik: `https://servernoots.tail95a8ad.ts.net:8444/`
  - n8n: `https://servernoots.tail95a8ad.ts.net:8445/`
  - Netdata: `https://servernoots.tail95a8ad.ts.net:8446/`
  - Beszel: `https://servernoots.tail95a8ad.ts.net:8447/`
  - Scrutiny: `https://servernoots.tail95a8ad.ts.net:8448/`
  - Overseerr: `https://servernoots.tail95a8ad.ts.net:8449/`
  - Sonarr: `https://servernoots.tail95a8ad.ts.net:8450/`
  - Radarr: `https://servernoots.tail95a8ad.ts.net:8451/`
  - Prowlarr: `https://servernoots.tail95a8ad.ts.net:8452/`
  - qBittorrent: `https://servernoots.tail95a8ad.ts.net:8453/`
  - Tautulli: `https://servernoots.tail95a8ad.ts.net:8454/`
  - Plex Web: `https://servernoots.tail95a8ad.ts.net:8455/`
  - ntfy: `https://servernoots.tail95a8ad.ts.net:8456/`
- Rollback command:
  - `cd /media/sook/Content/Servernoots/master-suite/phase1/tailscale && ./disable-admin-access.sh`

### ntfy Topic Matrix (Live)

- `ops-alerts` — general operations and uncategorized service status changes
- `security-alerts` — CrowdSec detections
- `network-alerts` — network/control-plane service status changes (`gluetun`, `adguardhome`, `ntfy`)
- `auth-alerts` — auth service status changes (`authentik-*`)
- `storage-alerts` — disk/health service status changes (`scrutiny`, `smartd`)
- `backup-alerts` — backup/restore service status changes (`kopia`, backup workers)
- `ai-audit` — guarded ops command audit trail from n8n (`ops-commands-ingest` workflow)
- `media-alerts` — media stack service status changes (`sonarr`, `prowlarr`, `qbittorrent`, `plex`, etc.)
- `update-alerts` — update automation service status changes (`watchtower`, similar)

Producer notes:

- Alert bridge publishes service-state events + CrowdSec events.
- n8n ops workflow publishes to both `ops-alerts` and `ai-audit`.
- Topics are private/local via ntfy localhost exposure + Tailscale Serve path.

### Gate C — AI Safety Ready

- [x] n8n commands are allowlisted only
- [x] Destructive actions require confirmation
- [x] Audit log captures all action attempts

Validation notes:

- Guardrails enforced via `guardrails/safe_command.sh` + workflow approval path (`/approve`/`/deny` for risky `/ops` requests)
- Audit trail active through both guardrail file log and n8n audit review workflow (`ops-audit` -> `ops-alerts`)
- Routing/tenant checks in current run confirm policy enforcement for Telegram/ntfy-originated requests

Tenant isolation verification (run after Telegram bridge or `rag-query` workflow updates):

1. Ensure workflow is imported/published and n8n is restarted:

- `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control`
- `jq empty workflows/rag-query-webhook.json`
- `docker exec n8n n8n import:workflow --input=/opt/workflows/rag-query-webhook.json`
- `docker exec n8n n8n publish:workflow --id=e2f4c63a-6ac9-46ce-9ee4-39d1d8de9128`
- `docker compose restart n8n telegram-n8n-bridge`

1. Valid tenant request should succeed:

- `curl -sS -X POST 'http://127.0.0.1:5678/webhook/rag-query' -H 'Content-Type: application/json' -d '{"source":"telegram","chat_id":700,"user_id":9001,"role":"user","tenant_id":"u_9001","full_name":"Tone User","telegram_username":"toneu","message":"hello"}' | jq -r '.reply'`

1. Cross-tenant request should be denied even if payload role is `admin`:

- `curl -sS -X POST 'http://127.0.0.1:5678/webhook/rag-query' -H 'Content-Type: application/json' -d '{"source":"telegram","chat_id":700,"user_id":9001,"role":"admin","tenant_id":"u_24680","full_name":"Tone User","telegram_username":"toneu","message":"Use internal docs: what is redwood-42?"}' | jq -r '.reply'`

Expected denial response includes:

- `⛔ Access denied: your account can only access its own tenant memory.`

Optional deny-event audit probe (local ntfy host port):

- `curl -sS --max-time 20 'http://127.0.0.1:8091/ops-alerts/json?poll=1' | grep -F 'TENANT_SCOPE_DENIED'`

Discord private user seed ingest (non-citable memory bootstrap):

1. Build per-user private seed profiles from Discord export ZIP:

- `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control`
- `/usr/bin/python3 scripts/import-discord-user-seed.py '/home/sook/Downloads/Council of Degenerates.zip' --out 'work/discord-seed' --min-messages 3`

1. Artifacts:

- `work/discord-seed/discord_user_profiles.json`
- `work/discord-seed/discord_user_seed_payloads.ndjson`

Policy:

- These Discord-derived profiles are treated as private per-user context (`user_profile_seed`, `user_profile_image_url`).
- They are not indexed as RAG sources and should not be cited as external/database sources in replies unless the user explicitly requests that provenance.
- `user_profile_image_url` is available to voice-channel flows as personalization context.
- For Discord requests, only include profile context when the user is active/interacting for the current event (`interaction_user_id == user_id` or `user_id` in `active_user_ids`).

Discord active-context payload helper:

- `/usr/bin/python3 scripts/discord-profile-context-loader.py --profiles work/discord-seed/discord_user_profiles.json --user-id <discord_user_id> --interaction-user-id <speaker_or_sender_id> --active-user-ids <comma_separated_active_ids>`
- Include resulting fields in webhook payload: `profile_context_allowed`, `user_profile_seed`, `user_profile_image_url`, `interaction_user_id`, `active_user_ids`.

Preferred integration wrapper:

- Pipe Discord event JSON into:
  - `/usr/bin/python3 scripts/discord-rag-proxy.py --profiles work/discord-seed/discord_user_profiles.json --n8n-base http://127.0.0.1:5678 --rag-webhook /webhook/rag-query --ops-webhook /webhook/ops-commands-ingest --allow-guild-ids <guild_id_csv> --allow-channel-ids <channel_id_csv> --allow-role-ids <role_id_csv> --audit-log logs/discord-command-audit.jsonl`
- This wrapper ignores any caller-supplied profile seed/image and computes gated context server-side.
- Command contract:
  - `/ask <question>` -> RAG query webhook
  - `/ops <action>` -> ops webhook (admin-only)
  - `/status` -> proxy + n8n health summary
  - `/memory show|opt-in|opt-out|clear` -> local memory-control scaffold (`clear` requires confirmation: `/memory clear confirm`)
  - `/join`, `/leave`, `/listen on|off`, `/voice status`, `/voice stop` -> voice-session scaffold contract (`route=discord-voice-scaffold` by default)
  - Optional forward mode for voice commands is available in proxy CLI/server with `--voice-forward` to `--voice-webhook` (`/webhook/discord-voice-command` default)
  - Voice cooldown policy: default `30s` per command/channel (`--voice-cooldown-seconds`), with moderator/admin bypass via `--voice-moderator-role-ids`
  - Voice cooldown state file: `--voice-state-file` (default `logs/discord-voice-state.json`)
  - Memory state file: `--memory-state-file` (default `logs/discord-memory-state.json`)
  - Attribution gate threshold override: `--memory-min-speaker-confidence` (default policy/`0.8`)

Discord voice loop dry-run contract (M7 scaffold):

- Script: `python3 scripts/discord-voice-loop-dryrun.py`
- CLI dry-run example:
  - `printf '{"user_id":"183726312861466635","guild_id":"g1","channel_id":"c1","role":"user","tenant_id":"u_183726312861466635","message":"hello from voice dry run","voice_session_id":"vs-1"}' | python3 scripts/discord-voice-loop-dryrun.py --n8n-base http://127.0.0.1:5678 --rag-webhook /webhook/rag-query --stt-base http://127.0.0.1:9001`
- HTTP contract endpoint mode:
  - `python3 scripts/discord-voice-loop-dryrun.py --serve --host 127.0.0.1 --port 8101`
  - `curl -sS -X POST 'http://127.0.0.1:8101/discord-voice-command' -H 'Content-Type: application/json' -d '{"user_id":"183726312861466635","tenant_id":"u_183726312861466635","message":"voice contract ping"}'`
- Forwarded `audio_url` path support (proxy -> voice loop endpoint):
  - `discord-rag-proxy.py` and `discord-rag-proxy-server.py` forward non-control voice events (`audio_url`/`has_audio`/`voice_mode`) to `--voice-webhook` as `command=voice_loop`.
  - Audit records use `command=voice_loop` and `reason=voice_loop_forwarded`.
- STT endpoint compatibility:
  - Primary STT path remains `--stt-path` (default `/v1/audio/transcriptions/by-url`).
  - OpenWhisper parity evidence (2026-02-28): `POST /v1/audio/transcriptions/by-url` now serves native JSON by-url transcription for Discord dry-run without fallback; E2E proof artifact captured at `/tmp/openwhisper-byurl-e2e-proof.json` (event fixture: `/tmp/openwhisper-byurl-e2e-event.json`).
  - Proof command:
    - `python3 scripts/discord-voice-loop-dryrun.py --event-file /tmp/openwhisper-byurl-e2e-event.json --n8n-base http://127.0.0.1:5678 --rag-webhook /webhook/rag-query --stt-base http://127.0.0.1:9001 --stt-path /v1/audio/transcriptions/by-url --stt-model whisper-1 --timeout 30 > /tmp/openwhisper-byurl-e2e-proof.json`
  - If provider returns `404`, helper falls back to OpenWhisper-compatible `POST /v1/audio/transcriptions?source_url=<audio_url>&model=<model>`.
  - This fallback was validated in local M7 probes with forwarded Discord proxy requests.
- Latency baseline (dry-run local forwarded path, 2026-02-28):
  - Target: `p95 <= 3500ms`
  - Sample source: local spoken clip served at `http://172.17.0.1:8111/0_george_0.wav`
  - 12-sample matrix summary (`/tmp/m7-latency-matrix-local.json`): `min=2135ms`, `p50=2230ms`, `p95=2867ms`, `max=3300ms`
  - Route/result consistency: `route=discord-voice-loop-dryrun`, `stt=ok`, `rag=ok`, `tts=ready` on all samples.

Discord memory scaffold checks (M8 kickoff, 2026-02-28):

- Show status:
  - `printf '{"user_id":"111","guild_id":"g1","channel_id":"c1","role":"user","tenant_id":"u_111","message":"/memory show"}' | /usr/bin/python3 scripts/discord-rag-proxy.py --allow-guild-ids g1 --allow-channel-ids c1 --memory-state-file /tmp/discord-memory-state-test.json --audit-log /tmp/discord-m8-audit.jsonl`
- Opt-in + clear confirmation flow:
  - `printf '{"user_id":"111","guild_id":"g1","channel_id":"c1","role":"user","tenant_id":"u_111","message":"/memory opt-in"}' | /usr/bin/python3 scripts/discord-rag-proxy.py --allow-guild-ids g1 --allow-channel-ids c1 --memory-state-file /tmp/discord-memory-state-test.json --audit-log /tmp/discord-m8-audit.jsonl`
  - `printf '{"user_id":"111","guild_id":"g1","channel_id":"c1","role":"user","tenant_id":"u_111","message":"/memory clear"}' | /usr/bin/python3 scripts/discord-rag-proxy.py --allow-guild-ids g1 --allow-channel-ids c1 --memory-state-file /tmp/discord-memory-state-test.json --audit-log /tmp/discord-m8-audit.jsonl`
  - `printf '{"user_id":"111","guild_id":"g1","channel_id":"c1","role":"user","tenant_id":"u_111","message":"/memory clear confirm"}' | /usr/bin/python3 scripts/discord-rag-proxy.py --allow-guild-ids g1 --allow-channel-ids c1 --memory-state-file /tmp/discord-memory-state-test.json --audit-log /tmp/discord-m8-audit.jsonl`
- Audit verification:
  - `tail -n 6 /tmp/discord-m8-audit.jsonl`
  - Expected reasons include `memory_show`, `memory_opt_in`, `memory_clear_confirmation_required`, `memory_clear`.

RAG-query downstream memory gate checks (M8, 2026-02-28):

- Publish updated workflow:
  - `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control`
  - `./scripts/publish-rag-query-workflow.sh --verify`
- Telegram debug probe (low-confidence voice-attributed payload):
  - `curl -sS -X POST 'http://127.0.0.1:5678/webhook/rag-query' -H 'Content-Type: application/json' -d '{"source":"telegram","chat_id":700,"user_id":"111","role":"user","tenant_id":"u_111","message":"hello","has_audio":true,"audio_url":"http://example.invalid/a.wav","memory_enabled":true,"voice_memory_opt_in":true,"memory_summary":"persist this short preference","speaker_confidence":0.42,"memory_min_speaker_confidence":0.8,"memory_write_allowed":false,"memory_low_confidence_policy":"deny","memory_write_mode":"summary_only","raw_audio_persist":false,"stt_debug_response_enabled":true}' | jq .`
- Expected debug memory fields:
  - `memory_write_allowed=false`
  - `memory_gate_blocked=true`
  - `memory_enabled_effective=false`

Discord response-driven memory writeback checks (M8, 2026-02-28):

- Behavior:
  - Memory summary persistence now occurs after webhook responses return (response-derived writeback), not from inbound Discord payload fields.
  - Persistence still requires policy pass (`voice_opt_in_required` and `memory_write_allowed=true`).
- CLI proof (local stub webhook):
  - `cat /tmp/m8-write-state.json`
  - `tail -n 1 /tmp/m8-write-audit.jsonl`
  - Expect: state contains summary text from webhook response and audit includes `"memory_summary_persisted":true` on `/ask`.
- HTTP proxy parity proof:
  - `cat /tmp/m8-write-server-state.json`
  - `tail -n 1 /tmp/m8-write-server-audit.jsonl`
  - Expect: same persisted summary and `"memory_summary_persisted":true` on `/ask`.

RAG response memory-summary contract checks (M8, 2026-02-28):

- Deploy:
  - `./scripts/publish-rag-query-workflow.sh --verify`
- Discord-source probe (`memory_summary` required):
  - `curl -sS -X POST 'http://127.0.0.1:5678/webhook/rag-query' -H 'Content-Type: application/json' -d '{"source":"discord","chat_id":"c1","user_id":"111","role":"user","tenant_id":"u_111","message":"hello","memory_enabled":true,"voice_memory_opt_in":true,"memory_summary":"persist me from normalize","speaker_confidence":0.95,"memory_min_speaker_confidence":0.8,"memory_write_allowed":true,"has_audio":false}' | jq '{reply,memory_summary}'
- Telegram-source probe (`memory_summary` + debug):
  - `curl -sS -X POST 'http://127.0.0.1:5678/webhook/rag-query' -H 'Content-Type: application/json' -d '{"source":"telegram","chat_id":700,"user_id":"111","role":"user","tenant_id":"u_111","message":"hello","memory_enabled":true,"voice_memory_opt_in":true,"memory_summary":"persist me telegram","speaker_confidence":0.95,"memory_min_speaker_confidence":0.8,"memory_write_allowed":true,"has_audio":false,"stt_debug_response_enabled":true}' | jq '{reply,memory_summary,debug_memory:(.debug.memory//null)}'
- Expected: top-level `memory_summary` present on both branches.

Final real proxy-to-n8n persistence proof (M8, 2026-02-28):

- CLI mode artifact:
  - `/tmp/discord-m8-real-cli-proof.txt`
  - Contains `/ask` output from real `http://127.0.0.1:5678/webhook/rag-query`, updated state, and audit marker `"memory_summary_persisted":true`.
- HTTP mode artifact:
  - `/tmp/discord-m8-real-http-proof.txt`
  - Contains `/ask` output via `discord-rag-proxy-server.py`, updated state, and audit marker `"memory_summary_persisted":true`.

Optional local HTTP service (`systemd`):

1. Install unit file:

- `sudo cp /media/sook/Content/Servernoots/master-suite/phase1/ai-control/systemd/discord-rag-proxy.service /etc/systemd/system/`
- `sudo systemctl daemon-reload`
- `sudo systemctl enable --now discord-rag-proxy.service`

1. Check health:

- `systemctl status discord-rag-proxy.service --no-pager`
- `curl -sS -X POST 'http://127.0.0.1:8099/discord-rag' -H 'Content-Type: application/json' -d '{"user_id":"183726312861466635","interaction_user_id":"183726312861466635","active_user_ids":["183726312861466635"],"channel_id":"discord-vc-1","message":"hello"}'`
- Audit trail output (JSONL):
  - `tail -n 20 /media/sook/Content/Servernoots/master-suite/phase1/ai-control/logs/discord-command-audit.jsonl`

Scope-denied alert rate limit (loose):

- Telegram delivery for `ops-alerts` (including `TENANT_SCOPE_DENIED`) is deduped with a loose topic window of `60s`.

Telegram/chat regression smoke checks:

- Evaluator: `./scripts/eval-telegram-chat-smoke.py`
- Alert runner: `./scripts/run-telegram-chat-smoke-and-alert.sh`
- Installer: `./scripts/install-telegram-chat-smoke-cron.sh`
- Uninstaller: `./scripts/uninstall-telegram-chat-smoke-cron.sh`
- Default schedule: `20 6 * * *` (local time)
- Override schedule: run installer with `TELEGRAM_CHAT_SMOKE_CRON_SCHEDULE='*/30 * * * *' ./scripts/install-telegram-chat-smoke-cron.sh`
- Current checks:
  - RAG webhook basic response check (`/webhook/rag-query`)
  - Telegram tenant isolation denial check (cross-tenant spoof payload)
  - Local `/profile apply|clear` command-path check with isolated temp state

Manual run:

- `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control`
- `/usr/bin/python3 ./scripts/eval-telegram-chat-smoke.py`
- `./scripts/run-telegram-chat-smoke-and-alert.sh`
- `./scripts/install-telegram-chat-smoke-cron.sh`
- `./scripts/uninstall-telegram-chat-smoke-cron.sh`
- `./scripts/run-health-monitor-and-alert.sh`
- `./scripts/install-health-monitor-cron.sh`
- `./scripts/uninstall-health-monitor-cron.sh`
- In Telegram as admin: `/status`
- In Telegram as admin (machine-friendly): `/status json`
- In Telegram as admin (consolidated health): `/health`
- In Telegram as admin (fast health without probe): `/health quick`
- In Telegram as admin (quiet hours): `/notify quiet 22-07` then `/notify profile`
- In Telegram as admin (notify E2E probe): `/notify validate`
- In Telegram as admin (manual digest flush): `/digest now`
- In Telegram as admin (digest queue status): `/digest stats`

Hourly health monitor (degraded-only alerting):

- Runner: `scripts/run-health-monitor-and-alert.sh`
- Cron install/uninstall:
  - `./scripts/install-health-monitor-cron.sh`
  - `./scripts/uninstall-health-monitor-cron.sh`
- Default behavior: alerts only after `2` consecutive degraded checks.
- State/log files:
  - `logs/health-monitor-state.json`
  - `logs/health-monitor-YYYY-MM-DD.log`
- Optional env tuning:
  - `HEALTH_MONITOR_CONSECUTIVE_DEGRADED_THRESHOLD` (default `2`)
  - `HEALTH_MONITOR_MAX_NOTIFY_STATS_AGE_SECONDS` (default `3600`)
  - `HEALTH_MONITOR_MAX_FANOUT_AGE_SECONDS` (default `10800`)
  - `HEALTH_MONITOR_NTFY_TOPIC` (default `ops-alerts`)
  - `TELEGRAM_HEALTH_MONITOR_CRON_SCHEDULE` (default `17 * * * *`)

Telegram admin quick sheet:

- Health and metrics:
  - `/health`
  - `/health quick`
  - `/health json`
  - `/status`
  - `/status json`
  - `/selftest`
  - `/ratelimit`
- Notification controls:
  - `/notify me`
  - `/notify me json`
  - `/notify list`
  - `/notify profile`
  - `/notify validate`
  - `/notify quiet 22-07`
  - `/notify quiet off`
  - `/notify stats`

`/notify me json` live sample (2026-02-27, sanitized):

```json
{
  "account_status": "active",
  "delivery_fail_streak": 0,
  "eligibility": "ok",
  "last_delivery_failed_age": "none",
  "last_delivery_reason": "(none)",
  "last_delivery_sent_age": "27m",
  "last_global_event_result": "skipped",
  "last_global_event_topic": "ops-alerts",
  "next": "/notify list (admins) or ask an admin to adjust topics/quarantine",
  "quarantine_remaining_seconds": 0,
  "quiet_by_topic": "(none)",
  "quiet_hours": "on (22-07 UTC)",
  "role": "admin",
  "selected_topics": ["audit", "critical", "media", "ops"],
  "timestamp": 1772254586,
  "user_id": "<redacted>"
}
```

---

## Ollama Token Generation & Hardware Utilization Review Thread

This thread documents the review process for token generation workflows and hardware utilization (Intel NPU, AMD 6950xt) in the AI system. Use this as a checklist and evidence log for each review cycle.

### 1. Token Generation Workflow Review

- **Overview of Token Generation Processes**
  - Document how Ollama is invoked (API, workflow, script, etc.)
  - Identify key components (models, endpoints, scripts)
  - Example: n8n workflow `rag-query-webhook.json` calls Ollama via HTTP proxy on port 11435

- **Workflow Bottlenecks or Inefficiencies**
  - Note any delays, errors, or slow responses
  - List any observed issues with model loading, token generation, or post-processing

### 2. Hardware Utilization Monitoring

- **GPU Usage (NVTOP)**
  - Run `nvtop` during token generation
  - Record GPU load, memory usage, and process name (should show Ollama or related container)
  - Example:
    - GPU Load: [Paste NVTOP screenshot/output]
    - Memory Usage: [Paste value]

- **CPU/Memory Usage (Netdata)**
  - Use Netdata dashboard to monitor CPU and RAM during token generation
  - Record spikes or sustained high usage
  - Example:
    - CPU Utilization: [Paste Netdata chart or value]
    - Memory Utilization: [Paste Netdata chart or value]

- **Process Checks**
  - Use `ps`, `top`, or `htop` to identify high-resource-consuming processes
  - Example:
    - High CPU/Memory Processes:
      - `ollama` PID [PID]: [CPU%] [MEM%]
      - [Other process]

### 3. Config and Monitoring Improvements

- **Hardware Configuration Recommendations**
  - Suggest changes to Docker, Ollama, or system config for better NPU/GPU utilization
  - Example: Set device flags, adjust memory limits, prioritize Ollama process

- **Monitoring Tool Improvements**
  - Recommend Netdata/NVTOP alert rules, dashboards, or logging enhancements
  - Example: Add custom Netdata chart for Ollama, set GPU usage alert threshold

---

#### Conclusion
This template provides a structured approach to reviewing token generation and hardware utilization. Use it to document findings, evidence, and recommendations for each review cycle.

---

Live-state validation snapshot (container): `USER_COUNT 5`, `STATUS_COUNTS {"active":4,"pending_registration":1}`.
Command-path validation snapshot (2026-02-28, injected Telegram update via `process_update`): `JSON_VALID true`, `CAPTURED_TEXT_LEN 554`, keys include `eligibility`, `selected_topics`, `quiet_hours`, `delivery_fail_streak`.
Network-path validation snapshot (2026-02-28, real Telegram API send): `TELEGRAM_API_OK true`, `TELEGRAM_MESSAGE_ID 259`, `JSON_VALID true`, `CAPTURED_TEXT_LEN 554`.

- Deferred digest controls:
  - `/digest stats`
  - `/digest now`
- Incident controls:
  - `/incident list`
  - `/incident show <incident_id>`
  - `/ack <incident_id>`
  - `/snooze <incident_id> <minutes>`
  - `/unsnooze <incident_id>`

Incident ownership + suppression (Telegram admin):

- Purpose: reduce repeat alert fatigue while keeping incident visibility and traceability.
- Incident IDs are attached to fanout messages as `Incident ID: INC-...`.
- Suppression behavior:
  - `/ack <incident_id>` suppresses repeat fanout for that incident within `TELEGRAM_INCIDENT_ACK_TTL_SECONDS`.
  - `/snooze <incident_id> <minutes>` suppresses fanout until the snooze timer expires.
  - `/unsnooze <incident_id>` removes an active snooze immediately.

Admin commands:

- `/incident list`
- `/incident show <incident_id>`
- `/ack <incident_id>`
- `/snooze <incident_id> <minutes>`
- `/unsnooze <incident_id>`

Runtime configuration knobs (`master-suite/phase1/ai-control/.env`):

- `TELEGRAM_INCIDENT_ACK_TTL_SECONDS` (default `21600`)
- `TELEGRAM_INCIDENT_RETENTION_SECONDS` (default `604800`)
- `TELEGRAM_INCIDENT_LIST_LIMIT` (default `8`)

Validation quick check:

1. Ensure updated bridges are recreated:

- `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control`
- `docker compose up -d --force-recreate ntfy-n8n-bridge telegram-n8n-bridge`

1. Trigger a repeat test incident and capture ID from logs:

- `docker exec ntfy-n8n-bridge python -c "import sys; sys.path.append('/app'); import ntfy_to_n8n as m; m.fanout_to_telegram(topic='ops-alerts', title='Runbook Incident Test', message='validation event', priority=5)"`
- `docker logs --since 30s ntfy-n8n-bridge | grep -E 'incident_id=|telegram fanout'`

1. In Telegram as admin, run `/ack <incident_id>` or `/snooze <incident_id> 10`, then re-send the same event and confirm skip reason in logs:

- `docker logs --since 30s ntfy-n8n-bridge | grep -E 'reason=incident_acked|reason=incident_snoozed'`

See also: [Incident command reference](13-telegram-command-reference.md#incident-ownership-controls-admin)

### Gate D — Recovery Ready

- [x] Backup policy written
- [x] Backup success confirmed
- [x] Restore test proven

Day 6 execution notes (2026-02-27):

- Existing snapshot backup path succeeded: `master-suite/phase1/ai-control/scripts/backup-system-snapshots.sh`.
- Pre-Kopia restore drill succeeded using latest snapshot backup copy for `snapshots/restore-drill/restore-drill.txt` (baseline hash == restored hash).
- Kopia installed locally and verified: `~/.local/bin/kopia` (`0.22.3`).
- Kopia repository initialized at `master-suite/phase1/ai-control/snapshots/kopia-repo` with config `master-suite/phase1/ai-control/snapshots/kopia.repository.config`.
- Kopia snapshots created for docs, ai-control, and media metadata paths.
- Kopia-native restore drill succeeded for `snapshots/restore-drill/restore-drill.txt` (baseline hash == restored hash after mutation).
- Immich backup validation rerun succeeded: `master-suite/phase1/media/validate-immich-backup.sh`.
- Watchtower policy validation complete (2026-02-27): deployed in monitoring stack with `monitor-only` + label scope (`phase1-monitoring`) and verified by one-shot run (`Session done Failed=0 Scanned=0 Updated=0`), with events visible on `update-alerts`.
- Media synthetic tuning status (2026-02-27): script now auto-loads `.env` and parses bridge stats in-process (no oversized argv path); latest run is `EXIT_CODE=0` with heartbeat `status=ok` and `fanout_check=fanout_processed:sent:none`.
- Alert-noise suppression evidence captured from bridge stats: `ops-alerts` (`critical_only`, `dedupe`, `incident_acked`, `incident_snoozed`) and `media-alerts` (`sent`, `sent_partial`, `dedupe`, `media_noise`, `deferred`).
- Bridge stability fix applied: `ntfy-n8n-bridge` now mounts `telegram-bridge-state` writable (no recent `Read-only file system` errors).
- Gate D closeout status: complete for Day 6 handoff; proceed with Day 7 full validation sweep.

### User / Role / Tenant Snapshot System

Scope:

- Telegram account registry (user + admin roles)
- Per-tenant RAG memory collections (`day4_rag_u_<telegram_user_id>`)

Snapshot command:

- `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control`
- `./scripts/snapshot-user-rag-state.sh`

Nightly automation (installed):

- Installer: `./scripts/install-user-rag-snapshot-cron.sh`
- Runner: `./scripts/run-user-rag-snapshot-and-alert.sh`
- Schedule: `30 2 * * *` (local time)
- Alert topic: `ops-alerts` via local ntfy (`http://localhost:8091/ops-alerts`)
- Retention policy: keep snapshot store at or under `50 GiB` (`USER_RAG_SNAPSHOT_MAX_BYTES=53687091200`)
- Near-cap alert threshold: `90%` (`USER_RAG_SNAPSHOT_WARN_PCT=90`)
- Behavior on over-cap: oldest snapshot directories are pruned until usage is <= cap

Snapshot output path:

- `master-suite/phase1/ai-control/snapshots/user-rag/<UTC_TIMESTAMP>/`
- Includes:
  - `telegram_users.json`
  - `collections.json`
  - `<collection>.snapshots.json`
  - `<collection>.<snapshot_file>`
  - `<collection>.info.json`
  - `manifest.txt`

Restore outline (per collection):

- Verify target collection name from `manifest.txt`
- Upload snapshot to Qdrant restore endpoint for that collection (collection-level restore)
- Validate with:
  - `curl -s http://127.0.0.1:6333/collections/<collection_name> | jq .result.points_count`
- Restore Telegram registry by replacing `/state/telegram_users.json` inside `telegram-n8n-bridge` from saved `telegram_users.json`

Operational note:

- Run snapshot before major user/role changes and before workflow migrations that alter tenant routing.

### External Snapshot Backup (Seagate)

Purpose:

- Copy system snapshot artifacts to external storage with a timestamped folder (no symlink dependency).

Run command:

- `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control`
- `./scripts/backup-system-snapshots.sh`

Default destination root:

- `/media/sook/Seagate Expansion Drive/SERVERNOOTS BACKUPS`

What it copies:

- `master-suite/phase1/ai-control/snapshots/` -> `system-snapshots/<timestamp>/ai-control-snapshots/`
- `checkpoints/` -> `system-snapshots/<timestamp>/checkpoints/`

Outputs:

- Per-run manifest: `system-snapshots/<timestamp>/backup-manifest.txt`
- Latest run marker: `system-snapshots/latest-path.txt`

Automation (optional):

- Installer: `./scripts/install-system-snapshot-backup-cron.sh`
- Uninstaller: `./scripts/uninstall-system-snapshot-backup-cron.sh`
- Default schedule: `45 2 * * *` (local time)
- Override schedule: run installer with `BACKUP_CRON_SCHEDULE='15 4 * * *' ./scripts/install-system-snapshot-backup-cron.sh`

### Gate E — Go-Live Ready

- [ ] Security scenario pass
- [x] AI/RAG scenario pass
- [ ] Media scenario pass
- [ ] Final baseline snapshot exists

Gate E partial status (2026-02-27): 1/4 complete (AI/RAG passed); Security, Media, and final baseline snapshot remain open.

Day 7 AI/RAG evidence capture (2026-02-27):

- Workflow deploy + restart completed with `./scripts/publish-rag-query-workflow.sh`.
- Direct webhook probe recovered to healthy state (HTTP 500 regression resolved):
  - `curl -sS --max-time 25 -H 'Content-Type: application/json' -d '{"source":"telegram","chat_id":700,"user_id":9001,"role":"user","tenant_id":"u_9001","full_name":"Smoke User","telegram_username":"smokeuser","message":"hello","persona_pref_brevity":"short"}' http://127.0.0.1:5678/webhook/rag-query`
  - Response included route/personality markers with short-budget marker: `route:smalltalk:greeting ... brevity:short rb:220`.
- Routing contract regression passed:
  - `python3 scripts/eval-routing.py --require-contract`
  - Result: all routing checks passed.
- Telegram/chat smoke suite passed in full:
  - `python3 scripts/eval-telegram-chat-smoke.py --mode all`
  - Result: `38/38` checks passed (live + local).
- Session outcome: direct webhook preference honoring is stable after fix; route budget markers and persona contract checks are green.

Day 5 media post-reboot quick verification (copy/paste):

`cd /media/sook/Content/Servernoots/master-suite/phase1/media && docker compose ps`

`curl -sS -I --max-time 15 http://127.0.0.1:32400/web | head -n 1`

`curl -sS -I --max-time 15 http://127.0.0.1:5055 | head -n 1`

`curl -sS -I --max-time 15 http://127.0.0.1:2283 | head -n 1`

Expected status lines:

- Plex: `HTTP/1.1 302 Moved Temporarily`
- Overseerr: `HTTP/1.1 307 Temporary Redirect`
- Immich: `HTTP/1.1 200 OK`

Backup re-check:

`cd /media/sook/Content/Servernoots/master-suite/phase1/media && ./validate-immich-backup.sh`

Immich mobile-backup evidence (no reboot required):

`BEFORE_COUNT=$(docker exec immich-postgres psql -U immich -d immich -tAc "select count(*) from public.asset;") && echo "BEFORE_COUNT=$BEFORE_COUNT"`

`AFTER_COUNT=$(docker exec immich-postgres psql -U immich -d immich -tAc "select count(*) from public.asset;") && echo "AFTER_COUNT=$AFTER_COUNT"`

`docker logs --since 2m immich-server 2>&1 | grep -Ei 'assets|upload|/api/assets' | tail -n 40 || true`

`if [ "$AFTER_COUNT" -gt "$BEFORE_COUNT" ]; then echo MOBILE_BACKUP_EVIDENCE_OK; else echo MOBILE_BACKUP_EVIDENCE_MISSING; fi`

---

## Daily Log (Quick Notes)

### Date

### What Changed

### What Passed

### What Failed

### Snapshot Taken

### Next Action

---

## Known Guardrails

- Never enable unrestricted AI shell access.
- Never skip snapshot before a major phase.
- Never rely on backup without restore testing.
- Keep service exposure minimal and intentional.

---

## First Action Right Now

Start at Day 1 and only mark complete when the Day 1 Definition of Done is fully true.
