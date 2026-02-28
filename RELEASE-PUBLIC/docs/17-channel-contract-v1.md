# Channel Contract v1 (Telegram, ntfy, Discord)

## Purpose

Define one shared behavior contract for all AI interaction channels so policy, security, and UX stay consistent as new frontends are added.

Status: design-only specification.

Canonical policy source: `18-implementation-sequence-v1.md` -> `Milestone 3 — Policy-as-config foundation` -> `Canonical policy key set (M3 draft)`.

---

## Scope

Applies to:

- Telegram bridge (live)
- ntfy conversational paths (live)
- Discord bot (planned)
- Voice conversation mode for Discord sessions (planned)

Does not cover:

- unrestricted autonomous shell execution (explicitly out of scope)
- public unauthenticated admin endpoints

---

## Design goals

- Same policy outcome regardless of channel.
- Same tenant boundary guarantees across channels.
- Same approval requirements for risky actions.
- Same audit fields for all request/response events.
- Channel-specific UX differences only where necessary.
- Voice features require explicit consent, clear retention policy, and reversible user controls.

---

## Contract model

Each request is normalized into a common envelope before workflow routing.

Policy key mapping note:

- Contract behavior in this document maps to canonical key families defined in the M3 policy registry (`identity.*`, `tenant.*`, `commands.*`, `approval.*`, `rate_limit.*`, `retention.*`, `dedupe.*`, `alerts.*`, `channels.*`, `memory.*`).
- Channel-specific behavior must be represented as `channels.<channel>.*` overrides rather than contract drift.

## Canonical request envelope (concept)

- `channel`: `telegram | ntfy | discord`
- `source`: concrete source identifier
- `chat_id` / `channel_id`
- `user_id`
- `role`: `user | admin`
- `tenant_id`: canonical tenant (`u_<user_id>` pattern for user-bound channels)
- `message`
- `attachments` (optional image/audio metadata)
- `interaction_modality`: `text | voice`
- `speaker_id` (channel-native user identity when voice)
- `speaker_confidence` (optional confidence from speaker attribution path)
- `memory_enabled` and `memory_summary` (if supported by channel)
- `timestamp`
- `request_id` (trace correlation id)

## Canonical decision envelope (concept)

- `decision`: `allow | deny | requires_approval`
- `mode`: `rag | ops`
- `reason_code`: policy or validation reason
- `target_action` (if any)
- `audit_required`: boolean

---

## Identity and authorization rules

- Channel identity must map to a known account record before command execution.
- Role-based action policy is channel-agnostic:
  - user role: no privileged ops execution
  - admin role: can request ops actions under guardrails
- Disabled account state blocks action regardless of channel.
- Unknown/invalid identity yields deny + safe user-facing message.
- Voice identity attribution must bind to a known account before long-term memory updates.

---

## Tenant isolation rules

- Tenant id is authoritative for retrieval and memory scope.
- Cross-tenant data access is denied by default.
- Administrative role does not implicitly bypass tenant boundary unless explicit policy allows a scoped admin operation.
- Tenant-scope denials are auditable security events.
- Voice-derived memory must inherit the same tenant boundary as text-derived memory.

---

## Command and safety rules

- Allowed actions must be from explicit allowlist.
- Telegram role command enforcement is policy-backed at `channels.telegram.role_command_allowlist` in `master-suite/phase1/ai-control/policy/policy.v1.yaml` (see also `docs/13-telegram-command-reference.md`).
- Risky actions require confirmation/approval flow.
- Unknown commands are denied with help guidance.
- Rate limiting is applied per user and channel to prevent abuse.
- Very short or malformed requests receive clarification prompts rather than silent failure.
- Voice session controls (`join/leave/listen`) must be allowlisted and rate-limited.

---

## Audit contract (required fields)

Every channel-originated action attempt should emit audit records including:

- `timestamp`
- `request_id`
- `channel`
- `user_id`
- `role`
- `tenant_id`
- `mode`
- `action` or `intent`
- `decision`
- `reason_code`
- `outcome`
- `interaction_modality`
- `speaker_id` (when voice)

Recommended sinks:

- topic-based audit feed (`ai-audit`)
- file/structured audit log for forensic review

---

## Response contract

- All responses should be concise and policy-safe.
- If denied, include clear reason class (permission, tenant, approval required, rate limit, malformed input).
- If approval required, include explicit next step and expiry window.
- Source citations are included when retrieval path returns trusted sources (channel formatting may vary).
- Voice responses should include optional text mirror when channel policy enables transcript visibility.

---

## Voice identity and memory policy

- Default policy: do not retain raw voice audio long-term.
- Use transcript + compact preference summaries as primary memory substrate.
- If speaker recognition is used, treat it as sensitive biometric processing.
- Require explicit disclosure/consent before enabling voice-based identity memory.
- Provide user controls to:
  - view stored memory summary,
  - opt out of voice memory,
  - clear voice-derived memory profile.

---

## Voice Conversation v1 Spec (design target)

### Session lifecycle

1. User invokes voice assistant in an allowlisted channel.
2. Bot posts a consent/disclosure notice before active listening begins.
3. Bot captures speech turns while session is active.
4. Bot exits on explicit leave command, idle timeout, or moderation stop.

### Latency targets

- Turn-to-turn target (user speech end -> bot speech start): 1.5 to 3.5 seconds typical.
- Degraded-mode maximum target: 6 seconds with fallback message if exceeded.
- If latency budget is exceeded repeatedly, bot should switch to short-text fallback mode and notify users.

### Consent UX requirements

- First join in a channel must include clear notice:
  - speech is transcribed for AI response,
  - memory updates may occur if enabled,
  - how to opt out and clear memory.
- Require server-level enablement plus per-user opt-in for voice-derived memory.
- Users without opt-in can still converse, but no long-term voice-derived profile updates are written.

### Retention defaults

- Raw audio clips: default disabled for persistence (ephemeral processing only).
- Transcript snippets: short retention window (default design target: 7 days) for incident/debug review.
- Summarized user memory facts: longer retention window (default design target: 30 days) with rolling refresh.
- Audit events: align with operations audit retention policy (separate from raw transcript retention).

### Memory update policy

- Only store durable, useful preference facts (interests, recurring goals, communication style cues).
- Do not store highly sensitive personal content unless explicitly required and consented.
- Apply confidence threshold before committing voice-derived facts.
- Store provenance metadata for each memory fact:
  - channel,
  - timestamp,
  - confidence,
  - source modality (`voice`).

### Speaker attribution policy

- Primary identity source: Discord user/session metadata.
- Speaker recognition confidence is secondary support, not sole authority.
- If attribution confidence is low, do not write long-term memory; ask a clarifying question instead.

### Safety controls

- Push-to-talk style activation or explicit wake trigger is preferred over always-on listening.
- Enforce voice session cooldown to prevent join/leave abuse.
- Provide moderator override command to immediately disable active voice session.

### Voice commands v1 (design table)

| Command | Role | Expected behavior | Audit outcome |
| --- | --- | --- | --- |
| `/join` | user/admin (allowlisted) | Bot joins caller voice channel if policy allows | `allow/deny` with reason |
| `/leave` | user/admin (allowlisted) | Bot disconnects and ends active voice session state | `allow` session_end |
| `/listen on` | user/admin (allowlisted) | Enables active voice turn capture for current session | `allow` listening_enabled |
| `/listen off` | user/admin (allowlisted) | Pauses voice turn capture while remaining connected | `allow` listening_disabled |
| `/voice status` | user/admin | Returns current session state, consent mode, memory mode | `allow` status_read |
| `/voice memory on` | user/admin (self) | Enables voice-derived memory for requesting user | `allow` memory_opt_in |
| `/voice memory off` | user/admin (self) | Disables future voice-derived memory writes | `allow` memory_opt_out |
| `/voice memory show` | user/admin (self) | Shows compact summary of stored voice-derived preferences | `allow` memory_read |
| `/voice memory clear` | user/admin (self) | Clears user voice-derived memory profile and confirms completion | `allow` memory_clear |
| `/voice stop` | admin/moderator | Emergency stop for active voice assistant session | `allow` forced_stop |

Command policy notes:

- Commands are subject to guild/channel/role allowlist checks.
- Unknown voice commands return guidance and do not change session state.
- Memory commands operate on caller identity unless explicit admin override policy is later defined.

---

## Channel-specific UX overlays

## Telegram (live)

- Supports text, photo, and audio inputs.
- Supports command families (`/rag`, `/ops`, `/notify`, `/memory`, `/user`, `/tone`, approvals).
- Supports memory + tone context fields.

## ntfy (live)

- Topic-based request/response and operational alerting.
- Best for lightweight command/notification interactions.

## Discord (planned)

- Slash command UX for discoverability.
- Voice session controls (`join/leave`) should reuse same allowlist + audit contract.
- Music/DJ behavior must follow provider policy constraints.
- Conversational voice loop should use STT -> policy/routing -> TTS pipeline with bounded latency targets.
- Memory updates from voice interactions should be summary-based and policy-scoped.

---

## Failure-mode design

- Workflow/backend unavailable -> return clear temporary failure message.
- Timeout -> return safe fallback + retry guidance.
- Policy evaluation error -> default deny (fail-safe).
- Audit sink failure -> action policy may proceed only if risk tier allows and failure is reported.

---

## Versioning and change control

- This document is `v1` baseline.
- Any channel behavior change should update this contract first, then channel-specific docs.
- Channel-specific docs must not conflict with this contract.

---

## Related docs

- [02-master-suite-architecture.md](02-master-suite-architecture.md)
- [12-discord-bot-expansion.md](12-discord-bot-expansion.md)
- [13-telegram-command-reference.md](13-telegram-command-reference.md)
- [14-software-capabilities-matrix.md](14-software-capabilities-matrix.md)
- [15-operations-command-reference.md](15-operations-command-reference.md)
