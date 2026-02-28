# Discord Bot Expansion (AI + Voice DJ)

## Current Status (Execution Kickoff)

- Milestone `M5 — Discord text v1` is now active.
- This document now includes an execution checklist with evidence targets.
- Voice features remain phased behind text-first completion gates.

## M5 — Discord Text v1 (Execution Checklist)

Status: `completed`  
Start Date: `2026-02-27`

Exit criteria (must all pass):

- [x] `/ask`, `/ops`, `/status` defined and implemented
- [x] Guild/channel/role allowlists enforced
- [x] Audit + tenant parity with Telegram/ntfy validated

Implementation checklist:

- [x] Define Discord command contract payload for `/ask`, `/ops`, `/status`
- [x] Add webhook route mapping for Discord text commands (`discord-command`)
- [x] Enforce guild/channel/role allowlists before webhook dispatch
- [x] Reuse existing guardrail path for ops commands and confirmation handling
- [x] Emit Discord command audit events with actor, scope, action, decision, result
- [x] Add smoke checks for allow/deny and tenant/scope isolation behavior
- [x] Add runbook/operator notes for deploy, verify, and rollback

Initial validation evidence (2026-02-27):

- `python3 -m py_compile scripts/discord-rag-proxy.py scripts/discord-rag-proxy-server.py` -> `PY_SYNTAX_OK`
- `/status` contract check:
  - `printf '{"user_id":"183726312861466635","guild_id":"g1","channel_id":"c1","role":"user","message":"/status"}' | python3 scripts/discord-rag-proxy.py --allow-guild-ids g1 --allow-channel-ids c1 --audit-log /tmp/discord-audit-test.jsonl`
- Allowlist deny-path check:
  - `printf '{"user_id":"183726312861466635","guild_id":"g2","channel_id":"c1","role":"user","message":"/ask hello"}' | python3 scripts/discord-rag-proxy.py --allow-guild-ids g1 --allow-channel-ids c1 --audit-log /tmp/discord-audit-test.jsonl`
- Tenant parity + audit validation (post-fix):
  - `printf '{"user_id":"9001","guild_id":"g1","channel_id":"c1","role":"admin","tenant_id":"u_24680","message":"/ask Use internal docs: what is redwood-42?"}' | python3 scripts/discord-rag-proxy.py --allow-guild-ids g1 --allow-channel-ids c1 --audit-log /tmp/discord-m5-audit.jsonl`
  - Expected result: `route=discord-tenant-scope-denied` and denial reply.
  - Audit evidence tail shows `tenant_scope_denied`, `ops_admin_only`, and forwarded admin ops decision records.

Evidence to capture:

- `docs/19-implementation-execution-tracker.md` (M5 status + evidence links)
- `docs/00-master-runbook.md` (Discord text validation note)
- `master-suite/phase1/ai-control/README.md` (Discord command usage + safety notes)
- command outputs for webhook health, allowlist deny-path, and audit log confirmation

## M6 — Voice Session Controls v1 (Scaffold Progress)

Status: `completed`

Current implemented scaffold commands:

- `/join`
- `/leave`
- `/listen on`
- `/listen off`
- `/voice status`
- `/voice stop`

Behavior:

- Default mode returns `route=discord-voice-scaffold` and records audit events.
- Optional forward mode is supported with `--voice-forward` to `--voice-webhook` (default `/webhook/discord-voice-command`).

Initial M6 evidence (2026-02-27):

- `python3 -m py_compile scripts/discord-rag-proxy.py scripts/discord-rag-proxy-server.py`
- `printf '{"user_id":"183726312861466635","guild_id":"g1","channel_id":"c1","role":"user","tenant_id":"u_183726312861466635","message":"/join"}' | python3 scripts/discord-rag-proxy.py --allow-guild-ids g1 --allow-channel-ids c1 --audit-log /tmp/discord-m6-audit.jsonl`
- `printf '{"user_id":"183726312861466635","guild_id":"g1","channel_id":"c1","role":"user","tenant_id":"u_183726312861466635","message":"/listen on"}' | python3 scripts/discord-rag-proxy.py --allow-guild-ids g1 --allow-channel-ids c1 --audit-log /tmp/discord-m6-audit.jsonl`
- `printf '{"user_id":"183726312861466635","guild_id":"g1","channel_id":"c1","role":"user","tenant_id":"u_183726312861466635","message":"/voice status"}' | python3 scripts/discord-rag-proxy.py --allow-guild-ids g1 --allow-channel-ids c1 --audit-log /tmp/discord-m6-audit.jsonl`
- `tail -n 6 /tmp/discord-m6-audit.jsonl` shows `voice_scaffold` audit decisions.
- Cooldown + moderator override validation:
  - Run `join` twice in same channel with `--voice-cooldown-seconds 30` -> second response returns `route=discord-voice-cooldown`.
  - Run `join` with role id in `--voice-moderator-role-ids` while cooldown active -> response returns `route=discord-voice-scaffold`.
  - Audit tail confirms `voice_cooldown` denial and moderator-allowed execution records.
- Policy-default cooldown validation (2026-02-27):
  - `discord-rag-proxy.py` and `discord-rag-proxy-server.py` now load default cooldown from `policy/policy.v1.yaml` key `rate_limit.voice_session_cooldown_seconds` (CLI `--voice-cooldown-seconds` still overrides).
  - Validation used two immediate `/join` commands without explicit cooldown arg; second response returned `route=discord-voice-cooldown` with `cooldown_seconds=30` in both CLI and `/proxy` server paths.

## M7 — Conversational Voice Loop v1 (Dry-Run Scaffold)

Status: `completed`

Implemented scaffold:

- New helper script: `scripts/discord-voice-loop-dryrun.py`
- Contract path: `STT -> rag-query routing -> TTS text output` (dry-run)
- Supports:
  - CLI one-shot event mode
  - HTTP webhook contract mode (`/discord-voice-command`)
  - `audio_url` STT by-url path (`/v1/audio/transcriptions/by-url`) or transcript/message fast path

Initial M7 evidence (2026-02-27):

- `python3 -m py_compile scripts/discord-voice-loop-dryrun.py`
- `printf '{"user_id":"183726312861466635","guild_id":"g1","channel_id":"c1","role":"user","tenant_id":"u_183726312861466635","message":"hello from voice dry run","voice_session_id":"vs-1"}' | python3 scripts/discord-voice-loop-dryrun.py --n8n-base http://127.0.0.1:5678 --rag-webhook /webhook/rag-query --stt-base http://127.0.0.1:9001`
- Output summary captured: `route=discord-voice-loop-dryrun`, `rag=ok`, `tts_status=ready`.
- Forwarded command-path validation (proxy -> voice loop endpoint):
  - Start helper server: `python3 scripts/discord-voice-loop-dryrun.py --serve --host 127.0.0.1 --port 8101 --quiet`
  - Forwarded `/join`: `printf '{"user_id":"111","guild_id":"g1","channel_id":"c1","role":"user","tenant_id":"u_111","message":"/join","voice_session_id":"vs-forward-1"}' | python3 scripts/discord-rag-proxy.py --n8n-base http://127.0.0.1:8101 --voice-webhook /discord-voice-command --voice-forward --voice-cooldown-seconds 0 --allow-guild-ids g1 --allow-channel-ids c1 --audit-log /tmp/discord-m7-forward-audit.jsonl`
  - Forwarded `/listen on`: same invocation with `message:"/listen on"`
  - Expected/observed output: `route=discord-voice-loop-dryrun`, `control.status=accepted`, and proxy audit records with `reason=voice_forwarded`.

Audio-url forward path evidence (2026-02-28):

- Added proxy routing parity for non-control voice events so `audio_url`/`has_audio`/`voice_mode` payloads are forwarded to `--voice-webhook` with `command=voice_loop`.
- Added OpenWhisper compatibility fallback in `discord-voice-loop-dryrun.py`:
  - primary: `POST {stt_base}/v1/audio/transcriptions/by-url`
  - fallback on `404`: `POST {stt_base}/v1/audio/transcriptions?source_url=<audio_url>&model=<model>`
- Validation commands:
  - Direct helper probe with silence sample URL returns `route=discord-voice-loop-dryrun`, `stt=empty`, `rag=ok`, `tts=ready`.
  - Forwarded proxy probe with spoken sample URL (`0_george_0.wav`) returns `route=discord-voice-loop-dryrun`, `stt=ok`, `rag=ok`, `tts=ready`.
  - Audit tail shows `command=voice_loop` with `reason=voice_loop_forwarded` and expected webhook URL.

Latency baseline evidence (2026-02-28):

- Target (dry-run local forwarded path): `p95 <= 3500ms`
- Matrix command (12 samples):
  - `AUDIO_URL='http://172.17.0.1:8111/0_george_0.wav'` payload forwarded via `python3 scripts/discord-rag-proxy.py --voice-forward --n8n-base http://127.0.0.1:8101 --voice-webhook /discord-voice-command ...`
- Captured summary (`/tmp/m7-latency-matrix-local.json`):
  - `sample_count=12`, `min=2135ms`, `p50=2230ms`, `p95=2867ms`, `max=3300ms`
  - Status set: `stt=ok`, `rag=ok`, `tts=ready` across all samples.

## M8 — Voice Memory + Identity v1 (Completed Scope)

Status: `completed`

Implemented scaffold (2026-02-28):

- New Discord memory command contract in proxy CLI/server:
  - `/memory show`
  - `/memory opt-in`
  - `/memory opt-out`
  - `/memory clear` (confirmation required: `/memory clear confirm`)
- Per-user memory state file support: `--memory-state-file` (default `logs/discord-memory-state.json`)
- Policy-backed memory defaults from `policy/policy.v1.yaml`:
  - `memory_enabled_by_default`
  - `memory_voice_opt_in_required`
  - `memory_low_confidence_write_policy`
  - `memory_clear_requires_confirmation`
  - `retention_raw_audio_persist`
- Payload metadata now includes scaffolded attribution gate fields:
  - `speaker_confidence`
  - `memory_min_speaker_confidence`
  - `memory_write_allowed`
  - `memory_write_mode=summary_only`
  - `raw_audio_persist=false` (policy default)

Initial M8 validation evidence (2026-02-28):

- `python3 -m py_compile scripts/discord-rag-proxy.py scripts/discord-rag-proxy-server.py`
- `printf '{"user_id":"111","guild_id":"g1","channel_id":"c1","role":"user","tenant_id":"u_111","message":"/memory show"}' | python3 scripts/discord-rag-proxy.py --allow-guild-ids g1 --allow-channel-ids c1 --memory-state-file /tmp/discord-memory-state-test.json --audit-log /tmp/discord-m8-audit.jsonl`
- `printf '{"user_id":"111","guild_id":"g1","channel_id":"c1","role":"user","tenant_id":"u_111","message":"/memory opt-in"}' | python3 scripts/discord-rag-proxy.py --allow-guild-ids g1 --allow-channel-ids c1 --memory-state-file /tmp/discord-memory-state-test.json --audit-log /tmp/discord-m8-audit.jsonl`
- `printf '{"user_id":"111","guild_id":"g1","channel_id":"c1","role":"user","tenant_id":"u_111","message":"/memory clear"}' | python3 scripts/discord-rag-proxy.py --allow-guild-ids g1 --allow-channel-ids c1 --memory-state-file /tmp/discord-memory-state-test.json --audit-log /tmp/discord-m8-audit.jsonl`
- `printf '{"user_id":"111","guild_id":"g1","channel_id":"c1","role":"user","tenant_id":"u_111","message":"/memory clear confirm"}' | python3 scripts/discord-rag-proxy.py --allow-guild-ids g1 --allow-channel-ids c1 --memory-state-file /tmp/discord-memory-state-test.json --audit-log /tmp/discord-m8-audit.jsonl`
- Audit evidence: `tail -n 6 /tmp/discord-m8-audit.jsonl` shows `memory_show`, `memory_opt_in`, `memory_clear_confirmation_required`, `memory_clear`.
- Attribution confidence policy evidence (payload dry-run): low-confidence probe (`speaker_confidence=0.42`) returns `memory_write_allowed=false` with default threshold `0.8`.
- Shared parser materialization evidence:
  - `python3 - <<'PY'\nfrom bridge.policy_loader import load_policy_telegram_settings\ns=load_policy_telegram_settings('policy/policy.v1.yaml')\nprint(s.get('memory_enabled_by_default'), s.get('memory_voice_opt_in_required'), s.get('memory_low_confidence_write_policy'), s.get('memory_clear_requires_confirmation'), s.get('retention_raw_audio_persist'))\nPY`
  - Expected/observed values: `False True deny True False`.

Downstream workflow gate evidence (2026-02-28):

- `workflows/rag-query-webhook.json` now computes and applies `memory_gate_blocked` in `Normalize Query` when `has_audio && memory_write_allowed=false`.
- Effective memory context is suppressed when blocked (`memory_enabled_effective=false`; effective summary cleared).
- Prompt builder nodes (`Build General Prompt`, `Augment RAG Prompt Memory`) now consume effective memory fields.
- Live webhook validation (telegram path with debug enabled) confirms:
  - `memory_write_allowed=false`
  - `memory_gate_blocked=true`
  - `memory_enabled_effective=false`
- Deploy command used: `./scripts/publish-rag-query-workflow.sh --verify`

Response contract hardening (2026-02-28):

- `workflows/rag-query-webhook.json` now emits top-level `memory_summary` on both response branches:
  - Telegram path (`Return Telegram Reply`) includes `memory_summary` in normal and debug-enabled responses.
  - Non-Telegram path now returns via `Return Routed Reply` (after `Post RAG Reply`) with `reply` + `memory_summary`.
- Live webhook probes confirm both paths return `memory_summary`:
  - Discord probe output: `memory_summary="persist me from normalize"`
  - Telegram probe output: `memory_summary="persist me telegram"`
- Real proxy -> n8n writeback proof artifacts (no stub):
  - CLI: `/tmp/discord-m8-real-cli-proof.txt` (`/ask` output includes `memory_summary`, state updated, audit has `memory_summary_persisted=true`)
  - HTTP: `/tmp/discord-m8-real-http-proof.txt` (same parity markers for server mode)

Persistence gate rollout evidence (2026-02-28):

- `discord-rag-proxy.py` and `discord-rag-proxy-server.py` now enforce memory write policy at the persistence boundary via `persist_memory_summary_if_allowed(...)` after receiving downstream webhook responses.
- Memory writes are now response-driven (extracted from webhook result `memory_summary`/`memory.summary` variants), not accepted directly from inbound Discord event payloads.
- Write is blocked unless policy permits it at write time:
  - respects `memory_voice_opt_in_required` and per-user opt-in state
  - respects confidence gate (`memory_low_confidence_write_policy=deny` + `memory_min_speaker_confidence`)
- Fresh CLI proof with local stub webhook (`memory_summary` returned by webhook):
  - state file: `/tmp/m8-write-state.json` shows persisted summary after `/memory opt-in` + `/ask`
  - audit marker: `/tmp/m8-write-audit.jsonl` includes `"memory_summary_persisted":true` for `/ask`
- Fresh HTTP parity proof with local proxy server + same stub webhook:
  - state file: `/tmp/m8-write-server-state.json` shows same persisted summary behavior
  - audit marker: `/tmp/m8-write-server-audit.jsonl` includes `"memory_summary_persisted":true` for `/ask`
- Finalized HTTP `/proxy` parity transcript artifacts (2026-02-28):
  - proof transcript: `/tmp/discord-m8-http-persistence-proof.txt`
  - state artifact: `/tmp/discord-m8-http-state.json`
  - audit artifact: `/tmp/discord-m8-http-audit.jsonl` (`memory_summary_persisted=false` for low-confidence then `true` for high-confidence)

Current M8 scope note:

- Command/payload scaffold and persistence write gating are now implemented in proxy paths; live Discord voice identity transport wiring remains pending for production end-to-end behavior.

## M9 — Channel Parity Review (Kickoff)

Status: `completed`

Goal:

- Confirm policy and contract parity across Telegram, ntfy, and Discord after M8 closeout.

Validation steps (completed):

- Policy parity spot-check:
  - Compare `memory_write_allowed`, `memory_gate_blocked`, and effective memory fields across channel-source probes against the same low/high confidence inputs.
- Audit parity check:
  - Confirm equivalent decision markers for command forwarding/denials and memory persistence markers (`memory_summary_persisted`) in channel-specific audit logs.
- Contract drift check:
  - Verify response payload includes stable `reply` + `memory_summary` where expected, and that no branch regressed to empty/omitted summary unexpectedly.

Expected artifacts:

- `/tmp/discord-m9-parity-summary.json`
- `/tmp/discord-m9-audit-parity.json`
- `/tmp/discord-m9-contract-parity.json`

Artifact run + closure (2026-02-28):

- Artifacts generated:
  - `/tmp/discord-m9-parity-summary.json`
  - `/tmp/discord-m9-audit-parity.json`
  - `/tmp/discord-m9-contract-parity.json`
- Result snapshot:
  - Audit parity (Discord proxy CLI + HTTP) passed with `memory_summary_persisted=true` in both paths.
  - Workflow error path was resolved by fixing JS syntax in `Build General Prompt` and `Augment RAG Prompt Memory` (`??` + `||` precedence issue), then republishing `rag-query`.
  - Contract/policy probes now run without workflow errors across `source=discord|ntfy|telegram`.
  - Current parity snapshot: high-confidence probes include `memory_summary`; low-confidence probes suppress effective memory (`memory_summary` omitted) while still returning valid replies.

Success gate (met):

- No parity regressions across mapped fields and no unresolved contract drift for M8 memory paths.
- Follow-on note: live Discord voice transport identity wiring remains a separate production hardening scope outside M9 parity review closure.

## Objective

Add Discord as an additional control frontend for the Master Suite so users can:

- send AI text prompts in Discord,
- trigger approved ops commands,
- ask the bot to join voice channels,
- run a controlled DJ mode,
- and hold real-time voice conversations with users using AI-generated speech.

## Voice Conversation Vision (theory)

Target user experience:

- Bot can listen in a voice channel when explicitly activated.
- Bot can respond with synthesized AI speech in near real time.
- Bot can maintain per-user conversation memory (interests/preferences) for better follow-up responses.
- Bot can optionally use speaker identity signals so memory maps to the correct Discord user.

Important boundary:

- Voice identity features should be opt-in and policy-driven. Treat voiceprints as sensitive biometric data.
- Voice latency, consent UX, and retention defaults follow Channel Contract v1 voice spec.

## Basic System Model (theory)

- **Input layer:** Discord messages and slash commands.
- **Decision layer:** existing workflow logic determines answer vs action.
- **Action layer:** only allowlisted operations are executed.
- **Feedback layer:** responses and audit events are posted back to chat/alerts.

This keeps Discord as a frontend, while safety policy remains centralized.

## Scope (phased)

### Phase A — Text-first integration

- Bot receives slash commands and mention commands.
- Bot forwards normalized payloads to n8n webhooks.
- Existing routing/guardrails decide answer vs action.
- Replies are posted back to Discord channel/DM.

Initial commands:

- `/ask <question>` -> AI/RAG response
- `/ops <action>` -> guarded ops flow
- `/status` -> bot + backend health summary

### Phase B — Voice control primitives

- `/join` -> bot joins caller voice channel (allowlisted guild/channel/role)
- `/leave` -> bot disconnects cleanly
- `/dj start` -> start queue mode
- `/dj stop` -> stop queue mode
- `/skip` -> skip current track

### Phase C — Conversational voice assistant

- Capture user speech from active voice session.
- Run speech-to-text (STT) with speaker attribution.
- Send normalized transcript to n8n/AI workflow with user + tenant metadata.
- Return short assistant response and synthesize speech (TTS) back into voice channel.
- Mirror condensed text summary to channel thread/log for traceability when enabled.
- Use bounded latency targets with graceful fallback when speech pipeline exceeds budget.
- Command behavior should follow the Voice Commands v1 table in `17-channel-contract-v1.md`.

### Phase D — DJ orchestration

- Queue manager handles tracks, priorities, and idle timeout.
- AI assistant can suggest tracks or mood-based transitions.
- Playback actions and moderation events are audited.

### Phase E — Voice identity + memory enrichment

- Maintain stable mapping between Discord user and memory profile.
- Optionally support speaker recognition confidence scoring for noisy multi-user channels.
- Persist preference memory (topics, interests, style cues) in user profile.
- Do not store raw voice audio long-term by default; store compact metadata/transcript summaries unless explicit retention policy allows otherwise.
- Only write long-term memory when attribution confidence and consent requirements are satisfied.

## Architecture Contract

1. Discord Bot receives command/event.
2. Bot validates guild, channel, and role allowlists.
3. Bot sends signed payload to n8n webhook (`discord-command` / `discord-voice-command`).
4. n8n returns action decision (`allow`, `deny`, `requires_confirmation`).
5. Bot executes allowed action and sends result to Discord + `ops-alerts`/`ai-audit`.

## Security and Guardrails

- Token handling:
  - store Discord bot token in env/secret only,
  - never in git-tracked workflow JSON.
- Command safety:
  - reuse allowlist-only command model,
  - require confirmation for destructive ops.
- Abuse controls:
  - per-user and per-channel rate limiting,
  - cooldown on voice join/leave actions.
- Auditability:
  - every Discord command logs timestamp, actor, guild/channel, action, result.
- Consent + privacy:
  - require explicit server-level and user-level disclosure for voice capture,
  - provide opt-out and memory-clear controls,
  - document retention windows for transcript and voice-derived metadata.

## Spotify Feasibility Note

- Spotify Premium is useful for account playback control and recommendations.
- A custom Discord bot should not rebroadcast Spotify audio into voice channels.
- Design recommendation:
  - keep `music_provider` abstraction (`spotify_control`, `voice_stream_provider`),
  - use Spotify for metadata/recommendations/control,
  - use a provider path that permits Discord voice streaming for bot playback.

## Data Model Additions (planned)

- `discord_guild_id`
- `discord_channel_id`
- `discord_user_id`
- `discord_role_ids`
- `voice_session_id`
- `music_provider`
- `queue_state`
- `speaker_profile_id`
- `speaker_confidence`
- `voice_memory_opt_in`
- `interest_summary`
- `conversation_style_summary`
- `last_voice_interaction_at`

## Done Criteria

