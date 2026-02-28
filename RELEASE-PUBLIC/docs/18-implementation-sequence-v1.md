# Implementation Sequence v1 (Design Roadmap)

## Purpose

Translate current design documents into an implementation order that reduces risk and avoids policy drift.

Status: planning artifact (design thread).

---

## Sequence principles

- Reliability before feature expansion.
- Policy parity across channels before adding new channels.
- Consent/privacy controls before persistent voice memory.
- Each milestone requires explicit exit criteria.

---

## Milestone 1 — Day 5 closeout baseline

Objective:

- Complete remaining media validation and snapshot closeout.

Scope:

- Immich first successful backup validation.
- `day5-media-stable` snapshot and reboot verification.

Exit criteria:

- Day 5 checklist closeout items are complete.
- Runbook reflects Day 5 as fully closed.

Primary docs:

- `07-day5-checklist.md`
- `00-master-runbook.md`

---

## Milestone 2 — Day 6 reliability hardening

Objective:

- Establish recoverability baseline.

Scope:

- Written Kopia backup policy.
- One successful backup + one verified restore drill.
- Controlled Watchtower policy with exclusions and alerting.

Exit criteria:

- Day 6 checklist pass conditions marked complete.
- Recovery gate in runbook is meaningfully advanced.

Primary docs:

- `08-day6-checklist.md`
- `15-operations-command-reference.md`

---

## Milestone 3 — Policy-as-config foundation

Objective:

- Prevent channel behavior drift.

Scope:

- Define one policy surface for:
  - allowlists,
  - rate limits,
  - approval risk tiers,
  - retention windows,
  - dedupe windows,
  - tenant boundary settings.

Exit criteria:

- Policy keys and ownership documented.
- Channel contract references canonical policy source.

Primary docs:

- `17-channel-contract-v1.md`
- `14-software-capabilities-matrix.md`

### Canonical policy key set (M3 draft)

Canonical source of truth (v1 draft): this section.

Key naming convention:

- Dot-delimited lowercase keys grouped by policy domain.
- Channel-specific overrides are optional and must use `channels.<channel>.*`.
- Emergency override keys must be explicit, time-scoped, and auditable.

Key groups:

- `identity.*`
  - `identity.require_registered_account`
  - `identity.admin_roles`
  - `identity.disabled_account_action`
- `tenant.*`
  - `tenant.enforce_strict_boundary`
  - `tenant.admin_cross_tenant_mode`
  - `tenant.denial_audit_topic`
- `commands.*`
  - `commands.allowlist.enabled`
  - `commands.allowlist.services`
  - `commands.unknown_action_policy`
- `approval.*`
  - `approval.required_risk_tiers`
  - `approval.default_ttl_seconds`
  - `approval.max_pending_per_user`
- `rate_limit.*`
  - `rate_limit.default.requests_per_minute`
  - `rate_limit.burst`
  - `rate_limit.voice_session_cooldown_seconds`
- `retention.*`
  - `retention.audit_days`
  - `retention.transcript_days`
  - `retention.voice_summary_days`
  - `retention.raw_audio_persist`
- `dedupe.*`
  - `dedupe.default_window_seconds`
  - `dedupe.topics.ops_alerts.window_seconds`
  - `dedupe.topics.media_alerts.window_seconds`
- `alerts.*`
  - `alerts.required_topics`
  - `alerts.noise_control.enabled`
  - `alerts.critical_only_topics`
- `channels.*`
  - `channels.telegram.enabled`
  - `channels.ntfy.enabled`
  - `channels.discord.enabled`
  - `channels.discord.voice.enabled`
- `memory.*`
  - `memory.enabled_by_default`
  - `memory.voice_opt_in_required`
  - `memory.low_confidence_write_policy`
  - `memory.clear_requires_confirmation`

### Ownership and change process (M3 draft)

Ownership model:

- Policy owner: platform operator (`Program Owner` in tracker).
- Security reviewer: owner/delegate for `tenant.*`, `approval.*`, `commands.*`, and `retention.*`.
- Runtime maintainer: service operator for channel-specific keys under `channels.*` and alert/dedupe tuning keys.

Change process:

1. Propose key/value change with rationale, risk level, and rollback plan.
2. Link impacted channels/components (`telegram`, `ntfy`, `discord`, workflows, bridge scripts).
3. Update this key registry first, then update channel contract behavior notes.
4. Record validation evidence in runbook/tracker before marking change complete.
5. For high-risk keys (`approval.*`, `tenant.*`, `commands.*`, `retention.*`), require explicit operator sign-off.

Acceptance criteria checkpoint for M3:

- Canonical key groups documented and stable enough for M4/M5 reuse.
- Channel contract references this section as canonical policy source.
- Tracker marks M3 `in-progress` with first evidence links.

---

## Milestone 4 — Acceptance test matrix

Objective:

- Make validations repeatable and visible.

Scope:

- Define scenario tests for:
  - auth and role restrictions,
  - tenant isolation,
  - approval flow,
  - alert routing,
  - backup restore,
  - channel parity.

Exit criteria:

- Matrix includes pass/fail status and last validation date.
- Go/no-go gates map to matrix rows.

Primary docs:

- `14-software-capabilities-matrix.md`
- `00-master-runbook.md`

---

## Milestone 5 — Discord text v1

Objective:

- Add Discord as a safe text frontend before voice features.

Scope:

- `/ask`, `/ops`, `/status` command set.
- Guild/channel/role allowlists.
- Audit + tenant policy parity with Telegram/ntfy.

Exit criteria:

- Text command path is stable in one test guild.
- Audit and policy behavior matches Channel Contract v1.

Primary docs:

- `12-discord-bot-expansion.md`
- `17-channel-contract-v1.md`

---

## Milestone 6 — Discord voice session controls v1

Objective:

- Enable safe voice session control without persistent voice memory yet.

Scope:

- `/join`, `/leave`, `/listen on`, `/listen off`, `/voice status`, `/voice stop`.
- Session cooldowns and moderator override.

Exit criteria:

- Voice session control is stable and auditable.
- Safety controls verified in test guild.

Primary docs:

- `17-channel-contract-v1.md`
- `12-discord-bot-expansion.md`

---

## Milestone 7 — Conversational voice loop v1

Objective:

- Deliver natural voice conversation behavior.

Scope:

- STT -> policy/routing -> TTS pipeline.
- Latency budget and degraded-mode fallback.
- Optional transcript mirror policy.

Exit criteria:

- Turn latency remains within target budget for normal load.
- Failure behavior is clear and safe.

Primary docs:

- `17-channel-contract-v1.md`
- `12-discord-bot-expansion.md`

---

## Milestone 8 — Voice memory and identity v1

Objective:

- Add user memory enrichment from voice interactions under strict controls.

Scope:

- Per-user opt-in/opt-out.
- `voice memory show/clear` controls.
- Summary-based memory writes (no long-term raw audio by default).
- Attribution confidence rules.

Exit criteria:

- Consent and memory controls are demonstrably functional.
- Retention policy is documented and enforced by design.

Primary docs:

- `17-channel-contract-v1.md`
- `12-discord-bot-expansion.md`

---

## Milestone 9 — Channel parity review

Objective:

- Ensure Telegram, ntfy, and Discord follow one contract.

Scope:

- Compare policy behavior and audit fields across channels.
- Close any contract drift gaps.

Exit criteria:

- Parity checklist complete.
- Capability matrix updated with implementation state.

Primary docs:

- `17-channel-contract-v1.md`
- `14-software-capabilities-matrix.md`

---

## Milestone 10 — Go-live readiness update

Objective:

- Prepare final confidence pass before broader use.

Scope:

- Refresh runbook gates and evidence links.
- Confirm backup/restore, policy, and channel readiness signals.

Exit criteria:

- Runbook reflects current truth.
- Outstanding risk items are explicit and owned.

Primary docs:

- `00-master-runbook.md`
- `09-day7-checklist.md`

---

## Milestone 11 — Deep research reports (Telegram + Nextcloud)

Objective:

- Provide Gemini-style deep research report generation with reliable artifact delivery.

Scope:

- Add `/research` command family (`start`, `status`, `report`) for Telegram users.
- Run research workflow asynchronously with auditable run ids.
- Generate report artifact (Markdown/PDF) and upload to Nextcloud.
- Deliver report via Telegram message containing Nextcloud download link.
- Enforce policy limits for report size and link TTL.

Exit criteria:

- User can request a report and retrieve it via Nextcloud link from Telegram.
- Failed/expired links return safe retry guidance.
- Audit records include requester, run id, artifact path, and link expiry metadata.

Primary docs:

- `13-telegram-command-reference.md`
- `17-channel-contract-v1.md`
- `15-operations-command-reference.md`

---

## Suggested sequencing cadence

- Milestones 1-2: reliability closeout
- Milestones 3-4: governance + validation foundation
- Milestones 5-8: Discord/voice rollout in increasing risk order
- Milestones 9-10: parity and go-live framing
- Milestone 11: deep research artifact delivery rollout

---

## Related docs

- `00-master-runbook.md`
- `12-discord-bot-expansion.md`
- `14-software-capabilities-matrix.md`
- `17-channel-contract-v1.md`
