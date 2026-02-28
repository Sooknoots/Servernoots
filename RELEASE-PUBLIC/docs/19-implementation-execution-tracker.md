# Implementation Execution Tracker (v1)

## Purpose

Track execution progress for `18-implementation-sequence-v1.md` with clear ownership, status, and evidence.

Status key:

- `not-started`
- `in-progress`
- `blocked`
- `done`

Update rule:

- When status changes, update `Last Updated`, owner, and evidence link(s).

---

## Global fields

- Last Updated: `2026-02-28`
- Program Owner: `ai-control`
- Current Focus Milestone: `Post-M3 hardening`
- Overall Health: `green`

---

## Milestone tracker

- M1 — Day 5 closeout baseline
  - Status: completed
  - Owner: TBD
  - Start Date: 2026-02-27
  - Target Date: 2026-02-27
  - Exit Criteria Met: yes
  - Evidence Link(s): docs/07-day5-checklist.md; docs/00-master-runbook.md
  - Notes: Closed; reboot deferred by operator
- M2 — Day 6 reliability hardening
  - Status: completed
  - Owner: TBD
  - Start Date: 2026-02-27
  - Target Date: 2026-02-27
  - Exit Criteria Met: yes
  - Evidence Link(s): docs/08-day6-checklist.md; docs/00-master-runbook.md
  - Notes: Closed with `day6-ops-hardened` snapshot captured
- M3 — Policy-as-config foundation
  - Status: completed
  - Owner: ai-control
  - Start Date: 2026-02-27
  - Target Date: 2026-03-07
  - Exit Criteria Met: yes
  - Evidence Link(s): docs/18-implementation-sequence-v1.md; docs/17-channel-contract-v1.md; docs/14-software-capabilities-matrix.md; docs/00-master-runbook.md; master-suite/phase1/ai-control/policy/policy.v1.yaml; master-suite/phase1/ai-control/policy/policy_extract.sh; master-suite/phase1/ai-control/guardrails/safe_command.sh; master-suite/phase1/ai-control/bridge/ntfy_to_n8n.py; master-suite/phase1/ai-control/bridge/telegram_to_n8n.py; master-suite/phase1/ai-control/scripts/discord-rag-proxy.py; master-suite/phase1/ai-control/scripts/discord-rag-proxy-server.py; checkpoints/m3-closure-evidence-2026-02-28.md; master-suite/phase1/ai-control/checkpoints/m3-policy-release-gate-summary.json
  - Notes: M3 is closed for current scope with release-gate evidence green. Post-M3 hardening baseline is active: checkpoint and policy-gate automation enabled (`scripts/install-memory-release-gate-cron.sh`, tag `ai-control-memory-release-gate`, evidence: `checkpoints/post-m3-memory-gate-cron-enable-2026-02-28.md`), rollback safety proofed (`checkpoints/post-m3-memory-gate-cron-rollback-proof-2026-02-28.md`, verified `1 -> 0 -> 1`), retry/backoff added (`checkpoints/post-m3-memory-gate-retry-hardening-2026-02-28.md`), hard/soft gate split (`checkpoints/post-m3-memory-gate-hard-soft-split-2026-02-28.md`), signal status helper (`make memory-release-gate-signal-status`, evidence: `checkpoints/post-m3-memory-gate-signal-status-helper-2026-02-28.md`), debounced alert cron (`make install-memory-release-gate-signal-cron`, evidence: `checkpoints/post-m3-memory-signal-debounced-alert-cron-2026-02-28.md`), signal-log retention cleanup (`make memory-release-gate-signal-log-cleanup`, evidence: `checkpoints/post-m3-memory-signal-log-retention-cleanup-2026-02-28.md`), and broader post-fix health snapshot (`make m8-proof-status`, `make m9-parity-status`, `make memory-release-gate-signal-status`, `make memory-release-gate-signal-alert`; evidence: `checkpoints/post-m3-postfix-health-snapshot-2026-02-28.md`).
- M4 — Acceptance test matrix
  - Status: completed
  - Owner:
  - Start Date: 2026-02-27
  - Target Date: 2026-02-27
  - Exit Criteria Met: yes
  - Evidence Link(s): docs/09-day7-checklist.md; docs/00-master-runbook.md; docs/20-ai-personality-next-sprint.md; checkpoints/day7-go-live-baseline.tar.gz
  - Notes: Day 7 final-validation matrix completed and baseline snapshot frozen; AI personality sprint closeout recorded with GO decision
- M5 — Discord text v1
  - Status: completed
  - Owner:
  - Start Date: 2026-02-27
  - Target Date: 2026-02-27
  - Exit Criteria Met: yes
  - Evidence Link(s): docs/12-discord-bot-expansion.md; docs/00-master-runbook.md; master-suite/phase1/ai-control/README.md
  - Notes: Command contract (`/ask` `/ops` `/status`), scope allowlists, JSONL audit logging, and strict tenant-scope parity validated.
- M6 — Discord voice session controls v1
  - Status: completed
  - Owner:
  - Start Date: 2026-02-27
  - Target Date: 2026-02-27
  - Exit Criteria Met: yes
  - Evidence Link(s): docs/12-discord-bot-expansion.md; docs/00-master-runbook.md; master-suite/phase1/ai-control/README.md; master-suite/phase1/ai-control/scripts/discord-rag-proxy.py; master-suite/phase1/ai-control/scripts/discord-rag-proxy-server.py; master-suite/phase1/ai-control/systemd/discord-rag-proxy.service
  - Notes: Voice session command scaffold handlers, cooldown policy, moderator override, and audit verification completed.
- M7 — Conversational voice loop v1
  - Status: completed
  - Owner:
  - Start Date: 2026-02-27
  - Target Date: 2026-02-28
  - Exit Criteria Met: yes
  - Evidence Link(s): docs/12-discord-bot-expansion.md; docs/00-master-runbook.md; master-suite/phase1/ai-control/README.md; master-suite/phase1/ai-control/scripts/discord-voice-loop-dryrun.py
  - Notes: Dry-run STT->routing->TTS contract scaffold completed with forwarded `audio_url` path and latency baseline (`p95=2867ms` across 12 local samples, target `<=3500ms`); live Discord voice transport integration remains future scope.
- M8 — Voice memory and identity v1
  - Status: completed
  - Owner: ai-control
  - Start Date: 2026-02-28
  - Target Date: 2026-02-28
  - Exit Criteria Met: yes
  - Evidence Link(s): docs/12-discord-bot-expansion.md; docs/00-master-runbook.md; master-suite/phase1/ai-control/README.md; master-suite/phase1/ai-control/Makefile; master-suite/phase1/ai-control/scripts/discord-rag-proxy.py; master-suite/phase1/ai-control/scripts/discord-rag-proxy-server.py; master-suite/phase1/ai-control/scripts/eval-discord-memory-persistence-proof-pack.py; master-suite/phase1/ai-control/scripts/eval-discord-memory-persistence-cli-proof.py; master-suite/phase1/ai-control/scripts/eval-discord-memory-persistence-http-proof.py
  - Notes: M8 closed with policy-backed payload gating plus persistence-boundary write enforcement in both Discord proxy paths, verified by durable proof scripts and one-command Makefile flows (`m8-proof-all|fresh|quick|status|clean`) that reproduce blocked low-confidence writes and allowed high-confidence writes with audit parity.
- M9 — Channel parity review
  - Status: completed
  - Owner: ai-control
  - Start Date: 2026-02-28
  - Target Date: 2026-02-28
  - Exit Criteria Met: yes
  - Evidence Link(s): docs/12-discord-bot-expansion.md; docs/00-master-runbook.md; master-suite/phase1/ai-control/Makefile; master-suite/phase1/ai-control/scripts/eval-discord-channel-parity-pack.py; master-suite/phase1/ai-control/scripts/discord-rag-proxy.py; master-suite/phase1/ai-control/scripts/discord-rag-proxy-server.py; checkpoints/m9-parity-summary.json; checkpoints/m9-contract-parity.json; /tmp/discord-m9-parity-summary.json; /tmp/discord-m9-contract-parity.json; /tmp/discord-m9-voice-contract-audit.jsonl
  - Notes: Channel parity review is closed with durable in-repo automation (`make m9-parity`, `make m9-parity-status`) and green parity output; workflow runtime blocker (`Build General Prompt` + `Augment RAG Prompt Memory` syntax) is fixed; voice-loop transport contract hardening is active in both proxy paths with explicit invalid-event denial/audit reasons.
- M10 — Go-live readiness update
  - Status: completed
  - Owner: ai-control
  - Start Date: 2026-02-28
  - Target Date: 2026-02-28
  - Exit Criteria Met: yes
  - Evidence Link(s): docs/00-master-runbook.md; docs/19-implementation-execution-tracker.md; docs/12-discord-bot-expansion.md; docs/17-channel-contract-v1.md
  - Notes: M10 closed with explicit readiness decision `GO-with-risks`: M1/M2/M4/M5/M6/M7/M8/M9 evidence is green for current operating scope, while residual production hardening items remain tracked with named owners and due dates.
- M11 — Deep research report delivery
  - Status: completed
  - Owner: ai-control
  - Start Date: 2026-02-28
  - Target Date: 2026-02-28
  - Exit Criteria Met: yes
  - Evidence Link(s): docs/00-master-runbook.md; master-suite/phase1/ai-control/workflows/deep-research-webhook.json; master-suite/phase1/ai-control/bridge/telegram_to_n8n.py; master-suite/phase1/ai-control/scripts/publish-deep-research-workflow.sh; master-suite/phase1/ai-control/checkpoints/deep-research-telegram-smoke-2026-02-28.json
  - Notes: Telegram `/research` start/status/report path is wired to n8n deep-research workflow with Nextcloud link delivery contract; live smoke evidence confirms onboarding + queued/ready lifecycle and stable report-link retrieval.

---

## Milestone detail cards

## M1 — Day 5 closeout baseline

- Status: completed
- Owner: TBD
- Exit criteria checklist:
  - [x] Immich first successful backup validation
  - [x] `day5-media-stable` snapshot created
  - [x] Reboot validation completed (deferred by operator for current phase acceptance)
  - [x] Runbook updated
- Evidence:
  - `docs/07-day5-checklist.md`
  - `docs/00-master-runbook.md`
- Risks/blockers:
  - None for current phase acceptance.

## M2 — Day 6 reliability hardening

- Status: completed
- Owner: TBD
- Exit criteria checklist:
  - [x] Kopia policy documented
  - [x] Backup success verified
  - [x] Restore drill completed
  - [x] Watchtower policy controlled and documented
- Evidence:
  - `docs/08-day6-checklist.md`
  - `docs/00-master-runbook.md`
- Risks/blockers:
  - Final acceptance depends on Day 6 own gate evidence and go-live review.

## M3 — Policy-as-config foundation

- Status: completed
- Owner: ai-control
- Exit criteria checklist:
  - [x] Canonical policy key set documented
  - [x] Ownership and change process documented
  - [x] Channel contract references policy source
  - [x] Workflow-level policy materialization completed for remaining channel paths
  - [x] Policy parity regression checks documented and passing for release gate usage
  - [x] M3 closure evidence bundle captured in tracker + runbook
- Remaining execution plan (2026-02-28):
  - [x] `2026-03-02` — Inventory remaining workflow-level policy reads/writes and map each to canonical keys (`ai-control`) (completed early on `2026-02-28`; artifact: `checkpoints/m3-policy-inventory-2026-02-28.md`)
  - [x] `2026-03-05` — Implement remaining policy materialization/enforcement updates and capture validation outputs (`ai-control`) (completed early on `2026-02-28`; workflow ntfy topic endpoints now env-indirected across `rag-query`, `rag-ingest`, `ops-commands`, `ops-audit-review`, `ai-chat`, and `textbook-fulfillment`; `rag-query` normalize path also cleaned to remove embedded memory fallback constants in favor of upstream policy-backed fields; validation: `./scripts/publish-rag-query-workflow.sh --verify`, `make m9-parity-status`, `make m9-parity` all PASS)
  - [x] `2026-03-07` — Publish M3 closure evidence and update milestone status/exit criteria (`ai-control`) (completed early on `2026-02-28`; artifact: `checkpoints/m3-closure-evidence-2026-02-28.md`)
- Evidence:
  - `docs/18-implementation-sequence-v1.md` (Milestone 3 canonical policy key set + ownership/change process)
  - `docs/17-channel-contract-v1.md` (canonical policy source reference + key-family mapping note)
  - `docs/14-software-capabilities-matrix.md` (policy-as-config source of truth section)
  - `master-suite/phase1/ai-control/policy/policy.v1.yaml` (runtime policy artifact)
  - `master-suite/phase1/ai-control/bridge/policy_loader.py` (shared policy parser used by both bridge directions)
  - `master-suite/phase1/ai-control/policy/policy_extract.sh` (shared shell policy extractor for guardrails consumers)
  - `master-suite/phase1/ai-control/guardrails/safe_command.sh` (allowlist reads policy file via shared extractor with fallback)
  - `master-suite/phase1/ai-control/bridge/ntfy_to_n8n.py` (notification topic controls filtered by policy `alerts.required_topics` and category mapping from `alerts.topic_categories`)
  - `master-suite/phase1/ai-control/bridge/telegram_to_n8n.py` (admin notify defaults + labels + dedupe + approval TTL/max-pending + request rate-limit settings derived from policy)
  - `master-suite/phase1/ai-control/bridge/telegram_to_n8n.py` (`build_payload` now forwards policy-backed `voice_memory_opt_in`, `memory_low_confidence_policy`, `memory_min_speaker_confidence`, `raw_audio_persist` to `rag-query`)
  - `master-suite/phase1/ai-control/workflows/rag-query-webhook.json` (ntfy endpoints now env-indirected via `NTFY_BASE`/`NTFY_*_TOPIC` expressions)
  - `master-suite/phase1/ai-control/workflows/rag-query-webhook.json` (`Normalize Query` now avoids embedded memory fallback constants and consumes upstream policy-backed `memory_*`/`retention_*` fields)
  - `master-suite/phase1/ai-control/workflows/rag-ingest-webhook.json` (ntfy endpoint env-indirected)
  - `master-suite/phase1/ai-control/workflows/ops-commands-webhook.json` (ntfy ops/audit endpoints env-indirected)
  - `master-suite/phase1/ai-control/workflows/ops-commands-webhook.json` (`Format Ops Result` now enforces payload-backed `channels.telegram.role_command_allowlist` decisions and workflow-level per-user rate limiting using policy-derived payload fields)
  - `master-suite/phase1/ai-control/bridge/telegram_to_n8n.py` (`build_payload` now forwards policy-derived ops enforcement fields: `policy_role_command_allowlist`, `policy_rate_limit_window_seconds`, `policy_rate_limit_max_requests`, `policy_rate_limit_requests_per_minute`, `policy_rate_limit_burst`)
  - `master-suite/phase1/ai-control/workflows/ops-audit-review-webhook.json` (ntfy endpoint env-indirected)
  - `master-suite/phase1/ai-control/workflows/ai-chat-webhook.json` (ntfy reply endpoint env-indirected)
  - `master-suite/phase1/ai-control/workflows/textbook-fulfillment-webhook.json` (ntfy ops/audit endpoints env-indirected)
  - `master-suite/phase1/ai-control/docker-compose.yml` (`n8n` env now wires `NTFY_BASE`, `NTFY_ALERT_TOPIC`, `NTFY_REPLIES_TOPIC`, `NTFY_AUDIT_TOPIC`)
  - `master-suite/phase1/ai-control/.env.example` (default workflow ntfy routing knobs)
  - `master-suite/phase1/ai-control/scripts/eval-m3-policy-release-gate.py` (M3 release gate for topic contract + memory contract + channel parity)
  - `master-suite/phase1/ai-control/Makefile` (`m3-policy-gate`, `m3-policy-gate-status` wrappers)
  - `make m9-parity-status` (`M9_PARITY_STATUS=PASS` after topic indirection)
  - `make m9-parity` (`M9_PARITY_PACK=PASS` after topic indirection)
  - `make m3-policy-gate` (`M3_POLICY_GATE=PASS`)
  - `make m3-policy-gate` (`M3_POLICY_GATE=PASS` after ops role/rate workflow hardening)
  - `make m3-policy-gate-status` (`M3_POLICY_GATE_STATUS=PASS`)
  - `master-suite/phase1/ai-control/scripts/capture-ops-alerts-evidence.py` (retry-safe ntfy topic evidence capture with endpoint fallback and durable checkpoint artifacts)
  - `make ops-alerts-evidence` (`OPS_ALERTS_EVIDENCE=PASS`)
  - `make ops-alerts-evidence-status` (`OPS_ALERTS_EVIDENCE_STATUS=PASS`)
  - `checkpoints/ops-alerts-evidence-latest.json` (latest pointer) + timestamped archive artifacts
  - `checkpoints/m3-policy-release-gate-summary.json` (durable M3 release-gate summary)
  - `make telegram-role-allowlist-smoke` + `make telegram-role-allowlist-smoke-status` (`TELEGRAM_ROLE_ALLOWLIST_SMOKE_STATUS=PASS`)
  - `make memory-scope-guard` + `make memory-scope-guard-status` (`MEMORY_SCOPE_GUARD_STATUS=PASS`)
  - `checkpoints/m3-closure-evidence-2026-02-28.md` (M3 closure decision + final release-gate evidence bundle)
  - `./scripts/eval-telegram-chat-smoke.py --mode local --check memory_regression_local` (post-change targeted local smoke passed)
  - `checkpoints/m3-policy-inventory-2026-02-28.md` (workflow-level policy read/write inventory + remaining gap map)
- Risks/blockers:
  - No blocking risks for M3 closure in current scope; remaining channel hardening items are tracked as post-M3 execution work.

## M4 — Acceptance test matrix

- Status: completed
- Owner: TBD
- Exit criteria checklist:
  - [x] Matrix includes scenario coverage for auth/tenant/approval/alerts/backup/channel parity
  - [x] Last validation date recorded per scenario
  - [x] Go/no-go gates mapped to scenarios
- Evidence:
  - `docs/09-day7-checklist.md` (Step 1 health sweep execution evidence)
  - `docs/00-master-runbook.md` (Day 7 Step 1 completion marker)
  - `docs/09-day7-checklist.md` (Step 2 security scenario evidence)
  - `docs/09-day7-checklist.md` (Step 3 AI scenario evidence: routing pass + allowlisted audit + approval flow)
  - `docs/00-master-runbook.md` (Day 7 Step 3 completion marker)
  - `docs/09-day7-checklist.md` (Step 4 media scenario evidence: request ingress + processing + playback telemetry)
  - `docs/00-master-runbook.md` (Day 7 Step 4 completion marker)
  - `docs/09-day7-checklist.md` (Step 5 backup/restore confidence evidence)
  - `docs/00-master-runbook.md` (Day 7 Step 5 completion marker)
  - `docs/09-day7-checklist.md` (Step 6 Homepage UX cleanup evidence)
  - `docs/00-master-runbook.md` (Day 7 Step 6 completion marker)
  - `docs/09-day7-checklist.md` (Step 7 risk checklist evidence)
  - `docs/09-day7-checklist.md` (Step 7.5 topic coverage evidence)
  - `docs/00-master-runbook.md` (Day 7 Step 7/7.5 completion markers)
  - `docs/09-day7-checklist.md` (Step 8 baseline freeze evidence)
  - `docs/00-master-runbook.md` (Day 7 baseline snapshot marker)
  - `docs/20-ai-personality-next-sprint.md` (Operator checklist closeout + go/no-go evidence)
  - `checkpoints/day7-go-live-baseline.tar.gz`
- Risks/blockers:
  - No open blockers for M4 closeout.

## M5 — Discord text v1

- Status: completed
- Owner:
- Exit criteria checklist:
  - [x] `/ask`, `/ops`, `/status` defined and implemented
  - [x] Guild/channel/role allowlists enforced
  - [x] Audit + tenant parity with Telegram/ntfy validated
- Evidence:
  - `docs/12-discord-bot-expansion.md` (M5 execution checklist + initial smoke evidence)
  - `docs/00-master-runbook.md` (Discord proxy command contract + audit path)
  - `master-suite/phase1/ai-control/README.md` (Discord proxy usage and allowlist options)
  - `master-suite/phase1/ai-control/scripts/discord-rag-proxy.py` (CLI contract/allowlist/audit implementation)
  - `master-suite/phase1/ai-control/scripts/discord-rag-proxy-server.py` (HTTP proxy contract/allowlist/audit implementation)
  - `master-suite/phase1/ai-control/systemd/discord-rag-proxy.service` (runtime env wiring for webhook, allowlists, and audit log)
- Risks/blockers:
  - No open blockers for M5 closeout.

## M6 — Discord voice session controls v1

- Status: completed
- Owner:
- Exit criteria checklist:
  - [x] `/join`, `/leave`, `/listen on/off`, `/voice status`, `/voice stop` implemented
  - [x] Cooldown + moderator override validated
  - [x] Session control audit events verified
- Evidence:
  - `docs/12-discord-bot-expansion.md` (M6 scaffold progress + command evidence)
  - `docs/00-master-runbook.md` (M6 command contract notes)
  - `master-suite/phase1/ai-control/README.md` (M6 scaffold and voice-forward usage)
  - `master-suite/phase1/ai-control/scripts/discord-rag-proxy.py` (CLI voice command scaffold)
  - `master-suite/phase1/ai-control/scripts/discord-rag-proxy-server.py` (HTTP voice command scaffold)
  - `master-suite/phase1/ai-control/systemd/discord-rag-proxy.service` (VOICE_WEBHOOK runtime wiring)
- Risks/blockers:
  - No open blockers for M6 closeout.

## M7 — Conversational voice loop v1

- Status: completed (dry-run + forwarded `audio_url` path + latency baseline validated)
- Owner: ai-control
- Exit criteria checklist:
  - [x] STT -> routing -> TTS path stable (dry-run contract including forwarded `audio_url` path)
  - [x] Latency target achieved (`p95 <= 3500ms`; observed `2867ms` over 12-sample local forwarded matrix)
  - [x] Fallback behavior validated under degraded conditions (OpenWhisper by-url `404` fallback path)
- Evidence:
  - `master-suite/phase1/ai-control/scripts/discord-rag-proxy.py` (`voice_loop` forwarding for `audio_url`/`has_audio`/`voice_mode`)
  - `master-suite/phase1/ai-control/scripts/discord-rag-proxy-server.py` (HTTP parity for `voice_loop` forwarding)
  - `master-suite/phase1/ai-control/scripts/discord-voice-loop-dryrun.py` (OpenWhisper endpoint fallback)
  - `/tmp/discord-m7-audio-forward-audit.jsonl` (`reason=voice_loop_forwarded` records)
  - `/tmp/discord-m7-latency-audit.jsonl` (forwarded matrix audit records)
  - `/tmp/m7-latency-matrix-local.json` (latency percentile summary)
  - `docs/12-discord-bot-expansion.md` (M7 audio-url forward evidence)
- Risks/blockers:
  - Dry-run scope closed; live Discord voice transport integration is still pending and should be measured separately before production go-live.

## M8 — Voice memory and identity v1

- Status: completed (memory controls + policy gates + response-driven writeback)
- Owner: ai-control
- Exit criteria checklist:
  - [x] Opt-in/opt-out controls available
  - Evidence Link(s): docs/12-discord-bot-expansion.md; docs/00-master-runbook.md; master-suite/phase1/ai-control/README.md; master-suite/phase1/ai-control/scripts/discord-rag-proxy.py; master-suite/phase1/ai-control/scripts/discord-rag-proxy-server.py; master-suite/phase1/ai-control/workflows/rag-query-webhook.json
  - Notes: M8 scaffold kickoff completed: `/memory show|opt-in|opt-out|clear` command path added with confirmation-required clear, policy-backed defaults, and attribution-confidence payload gating fields; downstream `rag-query` now enforces effective memory suppression when `memory_write_allowed=false` for voice-attributed payloads; proxy persistence now writes summaries from downstream webhook responses (not inbound Discord payload fields); `rag-query` now explicitly returns top-level `memory_summary` on both Telegram and non-Telegram response branches.
  - [x] Attribution confidence policy applied (payload gate fields + thresholded `memory_write_allowed`)
- Evidence:
  - `master-suite/phase1/ai-control/scripts/discord-rag-proxy.py` (`/memory` command scaffold + policy-backed memory payload fields)
  - `master-suite/phase1/ai-control/scripts/discord-rag-proxy-server.py` (HTTP parity for `/memory` scaffold)
  - `persist_memory_summary_if_allowed(...)` in both Discord proxy paths (persistence boundary write gate)
  - `master-suite/phase1/ai-control/workflows/rag-query-webhook.json` (downstream `memory_gate_blocked` + effective memory suppression)
  - `/tmp/discord-m8-audit.jsonl` (memory command decision records)
  - `/tmp/discord-memory-state-test.json` (per-user memory state scaffold)
  - `/tmp/discord-m8-persistence-e2e-proof.txt` (blocked vs allowed persistence transcript)
  - `/tmp/discord-m8-e2e-audit.jsonl` (`memory_summary_persisted=false` then `true`)
  - `/tmp/discord-m8-http-persistence-proof.txt` (HTTP `/proxy` parity proof transcript)
  - `/tmp/discord-m8-http-audit.jsonl` (HTTP parity audit with `memory_summary_persisted=false` then `true`)
  - `/tmp/m8-write-state.json` + `/tmp/m8-write-audit.jsonl` (fresh CLI response-writeback parity: `/ask` -> `memory_summary_persisted=true`)
  - `/tmp/m8-write-server-state.json` + `/tmp/m8-write-server-audit.jsonl` (fresh HTTP response-writeback parity: `/ask` -> `memory_summary_persisted=true`)
  - `/tmp/discord-m8-real-cli-proof.txt` (real proxy->n8n CLI proof with state update + `memory_summary_persisted=true`)
  - `/tmp/discord-m8-real-http-proof.txt` (real proxy->n8n HTTP proof with state update + `memory_summary_persisted=true`)
  - Discord and Telegram webhook probe outputs (post-deploy) each containing top-level `memory_summary`
  - `./scripts/publish-rag-query-workflow.sh --verify` (workflow deploy/registration)
  - Telegram debug probe output with `memory_gate_blocked=true` and `memory_enabled_effective=false`
  - Local gate validation probe (`mcp_pylance` snippet): `cli_blocked=False`, `cli_allowed=True`, `server_blocked=False`, `server_allowed=True`, `M8_PERSISTENCE_GATE_VALIDATION_OK`
  - `docs/12-discord-bot-expansion.md` (M8 kickoff evidence)
- Risks/blockers:
  - Follow-on hardening item: live Discord voice identity attribution transport wiring remains pending for full production end-to-end behavior.

## M9 — Channel parity review

- Status: completed
- Owner: ai-control
- Exit criteria checklist:
  - [x] Policy behavior matched across Telegram/ntfy/Discord
  - Evidence Link(s): docs/12-discord-bot-expansion.md; docs/00-master-runbook.md; master-suite/phase1/ai-control/Makefile; master-suite/phase1/ai-control/scripts/eval-discord-channel-parity-pack.py; master-suite/phase1/ai-control/scripts/discord-rag-proxy.py; master-suite/phase1/ai-control/scripts/discord-rag-proxy-server.py; checkpoints/m9-parity-summary.json; checkpoints/m9-contract-parity.json; /tmp/discord-m9-parity-summary.json; /tmp/discord-m9-contract-parity.json; /tmp/discord-m9-voice-contract-audit.jsonl
  - Notes: Durable parity automation is now in-repo (`make m9-parity`, `make m9-parity-status`) with green output (`M9_PARITY_PACK=PASS`); voice-loop transport contract has been hardened in both proxy paths with explicit invalid-event rejection/audit reasons, reducing malformed live voice-forward risk.
  - [x] Workflow runtime regressions cleared for parity probes
- Evidence:
  - `docs/12-discord-bot-expansion.md` (M8 closeout note + follow-on scope)
  - `docs/00-master-runbook.md` (M8 response-writeback contract and proofs)
  - `master-suite/phase1/ai-control/scripts/eval-discord-channel-parity-pack.py` (durable parity runner)
  - `master-suite/phase1/ai-control/Makefile` (`m9-parity`, `m9-parity-status` wrappers)
  - `checkpoints/m9-parity-summary.json` (durable parity summary)
  - `checkpoints/m9-contract-parity.json` (durable per-source contract probe detail)
  - `/tmp/discord-m9-parity-summary.json` + `/tmp/discord-m9-contract-parity.json` (compatibility mirrors)
- First-pass findings (2026-02-27):
  - Audit parity check passed for Discord proxy modes: CLI and HTTP both show `/ask` forwarded with `memory_summary_persisted=true`.
  - Workflow regression resolved: `Error in workflow` was traced to JS syntax errors in `Build General Prompt` (`format_no_match`) and `Augment RAG Prompt Memory` (`augment_rag_prompt_memory`) from invalid `??` + `||` mixing; syntax fixed and workflow republished.
  - Contract/policy probes now execute cleanly across `source=discord|ntfy|telegram` with no workflow errors.
  - Current parity snapshot:
    - high- and low-gate probes (`memory_write_allowed=true|false`) return `reply_present=true` and `memory_summary_present=true` consistently across Discord/Telegram/ntfy in this webhook contract path.
    - gate-memory presence consistency checks are green for both gates in `checkpoints/m9-parity-summary.json`.
- Risks/blockers:
  - Live Discord voice transport implementation details still to be finalized before production rollout.
  - No active workflow-runtime blockers after syntax fix; M9 parity review scope is closed.

## M10 — Go-live readiness update

- Status: completed
- Owner: ai-control
- Exit criteria checklist:
  - [x] Runbook gates updated with current truth
  - [x] Outstanding risks explicitly owned
  - [x] Final readiness decision documented
- Readiness decision:
  - Decision: `GO-with-risks`
  - Decision date: `2026-02-28`
  - Scope approved: existing Telegram/ntfy control plane + Discord text/session/voice-dry-run + M8 memory gates + M9 channel parity behavior.
  - Conditions: residual hardening items are tracked with explicit owners and target dates; no unresolved workflow runtime blocker remains in current scope.
- Evidence:
  - `docs/00-master-runbook.md` (progress tracker + next action alignment)
  - `docs/19-implementation-execution-tracker.md` (M10 status/owner/scope)
  - `docs/12-discord-bot-expansion.md` (M9 closure evidence carried into readiness context)
  - `docs/17-channel-contract-v1.md` (channel behavior baseline for readiness checks)
- Risk ownership:

| Risk item | Owner | Due date | Mitigation plan | Exit evidence |
|---|---|---|---|---|
| Live Discord voice identity attribution transport not validated end-to-end | ai-control | 2026-03-07 | Implement and validate live voice identity transport path with consent and confidence policy enforcement in production-like flow | Updated `docs/12-discord-bot-expansion.md` M8/M9 follow-on section + probe/audit artifacts |
| M3 policy-as-config rollout remains in-progress | ai-control | 2026-03-07 | Complete remaining workflow-level policy materialization and enforcement alignment across channels | M3 tracker checklist and runbook M3 runtime evidence updated with closure notes |

- Risks/blockers:
  - No blocker for approved current go-live scope; listed items remain post-go-live hardening commitments.

## M11 — Deep research report delivery

- Status: completed
- Owner: ai-control
- Exit criteria checklist:
  - [x] `/research` command path implemented for start/status/report in Telegram bridge
  - [x] n8n deep-research workflow deployed and verified
  - [x] Nextcloud report-link response contract validated end-to-end
- Evidence:
  - `master-suite/phase1/ai-control/workflows/deep-research-webhook.json` (deep-research webhook contract and Nextcloud share-link response shape)
  - `master-suite/phase1/ai-control/bridge/telegram_to_n8n.py` (Telegram `/research` command handling + role-safe job ownership checks)
  - `master-suite/phase1/ai-control/scripts/publish-deep-research-workflow.sh` (`--verify` deployment and contract verification)
  - `master-suite/phase1/ai-control/checkpoints/deep-research-telegram-smoke-2026-02-28.json` (live onboarding + `/research` start/status/report evidence with run id and delivered link)
  - `docs/00-master-runbook.md` (M11 progress/evidence bullet)
- Risks/blockers:
  - No blocker for current scope; full deep synthesis quality tuning and richer report composition remain follow-on product work.

---

## Evidence conventions

Use workspace-relative links where possible:

- docs updates (runbook/checklists)
- command output logs
- screenshot exports (if used)
- checkpoint/snapshot artifact paths

Example evidence entries:

- `checkpoints/day5-media-stable.tar.gz`
- `master-suite/phase1/ai-control/logs/routing-eval-YYYY-MM-DD.log`
- `docs/00-master-runbook.md`

---

## Related docs

- `18-implementation-sequence-v1.md`
- `17-channel-contract-v1.md`
- `14-software-capabilities-matrix.md`
- `00-master-runbook.md`
