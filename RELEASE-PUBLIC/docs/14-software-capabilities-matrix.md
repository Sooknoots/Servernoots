# Software Capabilities Matrix (Master Suite)

## Purpose

This document provides a single, high-level map of what the software stack can do today, what is planned, how it is accessed, and what controls are in place.

Scope: current Phase 1 workspace with forward-looking design notes where explicitly marked.

---

## Capability maturity legend

- `Live` = deployed and validated in current environment
- `Partial` = scaffolded or partially validated
- `Planned` = design documented, not yet implemented

---

## Foundation and access capabilities

| Domain | Service(s) | Core capability | Access model | Safety controls | Maturity |
| --- | --- | --- | --- | --- | --- |
| Core panel | Homepage | Unified service dashboard and navigation | Local + Tailscale mapped HTTPS | Minimal exposure via loopback/Tailnet | Live |
| Identity | Authentik (`authentik-server`, `authentik-worker`, DB, Redis) | Admin auth and MFA gateway | Local + Tailscale mapped HTTPS | MFA requirement, dedicated auth plane | Live |
| Tailnet admin | Tailscale serve scripts | Secure remote admin access without public port exposure | Tailnet HTTPS ports `8443-8456` | ACL/tag-based access control | Live |

---

## Security and network capabilities

| Domain | Service(s) | Core capability | Inputs/Signals | Outputs/Actions | Maturity |
| --- | --- | --- | --- | --- | --- |
| VPN routing | Gluetun + media clients on shared netns | Privacy egress and kill-switch path for downloader stack | VPN provider config, peer config | Stable tunnel egress for dependent containers | Live |
| DNS filtering | AdGuard Home (`adguardhome`) | LAN DNS filtering and policy control | Client DNS queries | Filtered DNS responses + query logs | Live |
| Threat detection | CrowdSec (`crowdsec`) | Detection and decision generation from log patterns | Service/auth/network logs | Decisions + metrics + alerts via bridge | Live |
| Health eventing | Alert bridge (`alert-bridge`) | CrowdSec + service state changes -> topicized alerts | Docker status, CrowdSec alerts | ntfy topics (`security/network/auth/storage/...`) | Live |

---

## Messaging and orchestration capabilities

| Domain | Service(s) | Core capability | Inputs | Outputs | Maturity |
| --- | --- | --- | --- | --- | --- |
| Notification hub | ntfy (`ntfy`) | Topic-based event and response channel | HTTP publish events | Multi-topic notifications to devices/admins | Live |
| Workflow orchestration | n8n (`n8n`) | Webhook-driven workflow execution and policy routing | Telegram/ntfy webhook payloads | AI responses, ops alerts, audit publishes | Live |
| Bridge fan-in/fan-out | `ntfy-n8n-bridge` | Feeds ntfy topics into n8n and relays policy outputs | ntfy events, Telegram policy settings | n8n webhook calls + targeted Telegram notifications | Live |
| Audit visibility | `audit-log-viewer` + n8n ops workflow | Readable operational audit feedback loop | Guardrail logs + workflow events | `ops-alerts`, `ai-audit` topic posts | Live |

---

## AI, RAG, and policy capabilities

| Domain | Service(s) | Core capability | Inputs | Outputs | Maturity |
| --- | --- | --- | --- | --- | --- |
| LLM integration | Ollama loopback proxy + n8n AI workflows | Local model prompt/response path | Chat/query prompts + retrieved context | AI responses on Telegram/ntfy | Live |
| Voice transcription | OpenWhisper (`openwhisper`) + RAG query workflow | OpenAI-compatible speech-to-text for Telegram voice/audio | `audio_url`, `audio_mime`, optional `STT_*` env overrides | Text query for downstream routing/reply | Live |
| Vector knowledge | Qdrant (`qdrant`) | Tenant-scoped + shared vector retrieval store | Ingested chunks + metadata | Ranked retrieval context for answers | Live |
| Routing policy | RAG query workflow + eval scripts | Dynamic route decision (smalltalk/web-first/RAG/weather etc.) | Query text + metadata | Route-tagged and policy-aware responses | Live |
| Tenant isolation | Workflow policy + tenant IDs | Prevent cross-tenant retrieval access | `tenant_id`, `user_id`, role | Denial events (`TENANT_SCOPE_DENIED`) + blocked responses | Live |
| Guarded ops | `safe_command.sh` + n8n ops webhook | Allowlist-only command path with confirmation controls | `/ops` requests + admin approvals | Status/restart/health actions + audit lines | Live |
| Autonomous shell access | Agent-style unrestricted execution | N/A | N/A | Explicitly disallowed by guardrails | Not supported |

---

## Telegram frontend capabilities

| Domain | Service(s) | Core capability | Notes | Maturity |
| --- | --- | --- | --- | --- |
| Chat frontend | `telegram-n8n-bridge` | Text, photo, and audio ingress to AI workflows | `/rag`, `/ops`, default-mode chat | Live |
| Account model | Telegram registry in bridge state | Role/status/registration state tracking | Admin/user role controls + disable/enable | Live |
| Approval queue | Bridge approval state | Risky `/ops` requests require explicit admin approve/deny | TTL-based queue with `/pending` management | Live |
| Personalization | Memory + tone history | User memory notes and tone smoothing across turns | User-level controls + admin tone inspection/reset | Live |
| Notification targeting | `/notify` policy controls | Topic selection + emergency contact behavior | Dedupe and drop-pattern policy controls | Live |

Reference: see Telegram command details in `13-telegram-command-reference.md`.

---

## Observability and operations capabilities

| Domain | Service(s) | Core capability | Access | Maturity |
| --- | --- | --- | --- | --- |
| Real-time metrics | Netdata (`netdata`) | Live host/container metrics | Local + Tailnet mapped | Live |
| Historical dashboard | Beszel (`beszel`) | Historical trends and uptime views | Local + Tailnet mapped | Live |
| Disk health | Scrutiny (`scrutiny`) | Disk/SMART visibility and health API | Local + Tailnet mapped | Live |
| Routing regression | `eval-routing.py` + cron wrappers | Repeatable AI routing checks with alert-on-fail | Script + cron jobs | Live |
| Snapshot automation | User/RAG snapshot scripts + cron wrappers | Tenant collection + registry snapshots with retention policy | Script + cron jobs + ntfy alerts | Live |
| Backup platform policy (Kopia) | Day 6 plan | Full backup/restore standardization | Planned in docs | Planned |

---

## Media automation capabilities

| Domain | Service(s) | Core capability | Current state |
| --- | --- | --- | --- |
| Media server | Plex (`plex`) | Library indexing and playback | Live and validated |
| Session telemetry | Tautulli (`tautulli`) | Playback events + alert path to `media-alerts` | Live and validated |
| Request workflow | Overseerr (`overseerr`) | User request interface into arr pipeline | Live and validated |
| Acquisition stack | qBittorrent + Prowlarr + Sonarr + Radarr | Automated search/download/import pipeline | Live and validated |
| Photo stack | Immich | Private photo backup/gallery | Pending closeout validation |

---

## Interface channels (current + planned)

| Channel | Purpose | State |
| --- | --- | --- |
| ntfy topics | Alerts + conversational endpoints | Live |
| Telegram bot | Primary remote AI and ops frontend | Live |
| Homepage UI | Operator navigation/control surface | Live |
| Discord bot | Additional AI/voice frontend | Planned (design documented) |

Reference: `12-discord-bot-expansion.md`.

---

## Global safety boundaries

- No unrestricted AI shell access.
- Allowlist-first command execution only.
- Risky operations require explicit approval.
- Tenant scope boundaries must be enforced.
- Admin services remain private and intentionally exposed only through trusted paths.
- Snapshots/backup verification are required before high-impact changes.

## Policy-as-config source of truth (M3)

- Canonical policy key registry lives in `18-implementation-sequence-v1.md` under Milestone 3 (`Canonical policy key set (M3 draft)`).
- Channel behavior contract maps to that registry via `17-channel-contract-v1.md`.
- Policy changes should update registry first, then channel contract and runbook evidence.

---

## Current known gaps (high-level)

- Day 5 closeout still pending Immich backup validation and `day5-media-stable` snapshot/reboot pass.
- Day 6 hardening (Kopia policy/restore drill/watchtower policy verification) not started.
- Discord interface is design-complete but not implemented.

---

## Related docs

- `00-master-runbook.md`
- `02-master-suite-architecture.md`
- `06-day4-checklist.md`
- `07-day5-checklist.md`
- `08-day6-checklist.md`
- `12-discord-bot-expansion.md`
- `13-telegram-command-reference.md`
