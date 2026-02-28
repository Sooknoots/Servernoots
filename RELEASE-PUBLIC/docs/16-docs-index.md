# Documentation Index (Master Suite)

## Purpose

This is the primary navigation page for the full documentation set.
Use it to quickly find the right document by role, task, and project phase.

---

## Recommended Starting Points by Audience

### New Operator (Day-to-Day Operations)

1. [Master Runbook](00-master-runbook.md)
2. [Operations Command Reference](15-operations-command-reference.md)
3. [Software Capabilities Matrix](14-software-capabilities-matrix.md)

### Security/Admin Maintainer

1. [Master Runbook](00-master-runbook.md)
2. [Master Suite Architecture](02-master-suite-architecture.md)
3. [Tailnet Admin Expansion](11-tailnet-admin-expansion.md)
4. [Telegram Command Reference](13-telegram-command-reference.md)

### Planning/Design Thread

1. [Master Suite Rollout Plan](01-master-suite-rollout-plan.md)
2. [Master Suite Architecture](02-master-suite-architecture.md)
3. [Discord Bot Expansion](12-discord-bot-expansion.md)
4. [Channel Contract v1](17-channel-contract-v1.md)
5. [Implementation Sequence v1](18-implementation-sequence-v1.md)
6. [Implementation Execution Tracker](19-implementation-execution-tracker.md)
7. [AI Personality 2-Week Plan](20-ai-personality-next-sprint.md)
8. [Software Capabilities Matrix](14-software-capabilities-matrix.md)

---

## Core Control Documents

- [00-master-runbook.md](00-master-runbook.md)
  - Single-page control center for progress, gates, and key links.
- [01-master-suite-rollout-plan.md](01-master-suite-rollout-plan.md)
  - Phase-based deployment sequence and scope.
- [02-master-suite-architecture.md](02-master-suite-architecture.md)
  - System interaction model, contracts, and boundaries.

---

## Phase Execution Checklists

- [03-day1-checklist.md](03-day1-checklist.md)
- [04-day2-checklist.md](04-day2-checklist.md)
- [05-day3-checklist.md](05-day3-checklist.md)
- [06-day4-checklist.md](06-day4-checklist.md)
- [07-day5-checklist.md](07-day5-checklist.md)
- [08-day6-checklist.md](08-day6-checklist.md)
- [09-day7-checklist.md](09-day7-checklist.md)

Use these for step-by-step rollout and closeout verification by day.

---

## Expansion and Migration Documents

- [10-proxmox-migration.md](10-proxmox-migration.md)
  - Host/VM migration planning and notes.
- [11-tailnet-admin-expansion.md](11-tailnet-admin-expansion.md)
  - Private multi-admin remote access model.
- [12-discord-bot-expansion.md](12-discord-bot-expansion.md)
  - Design-only Discord interface extension.

---

## Command and Capability References

- [13-telegram-command-reference.md](13-telegram-command-reference.md)
  - Full Telegram command surface, permissions, and policy behavior.
  - Policy key for runtime role gating: `channels.telegram.role_command_allowlist` in [../master-suite/phase1/ai-control/policy/policy.v1.yaml](../master-suite/phase1/ai-control/policy/policy.v1.yaml).
- [14-software-capabilities-matrix.md](14-software-capabilities-matrix.md)
  - Capability inventory across services with maturity and controls.
- [15-operations-command-reference.md](15-operations-command-reference.md)
  - Operator command handbook and troubleshooting commands.
  - Includes textbook synthetic transient recovery step for `127.0.0.1:5678` webhook reachability (`/healthz` check + rerun sequence).
- [17-channel-contract-v1.md](17-channel-contract-v1.md)
  - Unified channel policy contract for Telegram, ntfy, and future Discord.
- [18-implementation-sequence-v1.md](18-implementation-sequence-v1.md)
  - Ordered milestone roadmap with exit criteria.
- [19-implementation-execution-tracker.md](19-implementation-execution-tracker.md)
  - Live progress tracker for milestones, owners, and evidence.
  - Latest M11 deep-research evidence artifact: [../master-suite/phase1/ai-control/checkpoints/deep-research-telegram-smoke-2026-02-28.json](../master-suite/phase1/ai-control/checkpoints/deep-research-telegram-smoke-2026-02-28.json).
- [20-ai-personality-next-sprint.md](20-ai-personality-next-sprint.md)
  - Two-week execution plan for persona contract, style gate, and correction learning.

---

## Fast-Path Reading Routes

### Bring Up a New Admin Quickly

- [00-master-runbook.md](00-master-runbook.md)
- [11-tailnet-admin-expansion.md](11-tailnet-admin-expansion.md)
- [13-telegram-command-reference.md](13-telegram-command-reference.md)

### Validate Current Platform Status

- [00-master-runbook.md](00-master-runbook.md)
- [14-software-capabilities-matrix.md](14-software-capabilities-matrix.md)
- [07-day5-checklist.md](07-day5-checklist.md)
- [08-day6-checklist.md](08-day6-checklist.md)

### Work on AI/Control-Plane Behavior

- [06-day4-checklist.md](06-day4-checklist.md)
- [13-telegram-command-reference.md](13-telegram-command-reference.md)
- [17-channel-contract-v1.md](17-channel-contract-v1.md)
- [15-operations-command-reference.md](15-operations-command-reference.md)

### Plan Future Channel Integrations

- [12-discord-bot-expansion.md](12-discord-bot-expansion.md)
- [17-channel-contract-v1.md](17-channel-contract-v1.md)
- [18-implementation-sequence-v1.md](18-implementation-sequence-v1.md)
- [19-implementation-execution-tracker.md](19-implementation-execution-tracker.md)
- [20-ai-personality-next-sprint.md](20-ai-personality-next-sprint.md)
- [02-master-suite-architecture.md](02-master-suite-architecture.md)
- [01-master-suite-rollout-plan.md](01-master-suite-rollout-plan.md)

---

## Recent Incident Notes

### Core

- Service unhealthy recovery commands:
  - [15-operations-command-reference.md#service-unhealthy-recovery](15-operations-command-reference.md#service-unhealthy-recovery)
- Workflow import/runtime recovery commands:
  - [15-operations-command-reference.md#workflow-importruntime-recovery](15-operations-command-reference.md#workflow-importruntime-recovery)

### Textbook Webhook Transient (`127.0.0.1:5678`)

- Recovery evidence and timeline:
  - [00-master-runbook.md#textbook-webhook-transient-recovery](00-master-runbook.md#textbook-webhook-transient-recovery)
- On-call recovery commands (`/healthz` check + textbook synthetic rerun):
  - [15-operations-command-reference.md#textbook-webhook-transient-recovery](15-operations-command-reference.md#textbook-webhook-transient-recovery)
- AI-control local troubleshooting note:
  - [../master-suite/phase1/ai-control/README.md#textbook-webhook-transient-recovery](../master-suite/phase1/ai-control/README.md#textbook-webhook-transient-recovery)

### OpenWhisper Port Collision (`127.0.0.1:9000`)

- Recovery evidence and context:
  - [00-master-runbook.md#openwhisper-port-collision-recovery](00-master-runbook.md#openwhisper-port-collision-recovery)
- On-call recovery commands (`OPENWHISPER_HOST_PORT=9001` sequence):
  - [15-operations-command-reference.md#openwhisper-port-collision-recovery](15-operations-command-reference.md#openwhisper-port-collision-recovery)
- AI-control local troubleshooting note:
  - [../master-suite/phase1/ai-control/README.md#openwhisper-port-collision-recovery](../master-suite/phase1/ai-control/README.md#openwhisper-port-collision-recovery)

---

## Recent Evidence

- M11 deep-research Telegram smoke (Nextcloud link delivery): [../master-suite/phase1/ai-control/checkpoints/deep-research-telegram-smoke-2026-02-28.json](../master-suite/phase1/ai-control/checkpoints/deep-research-telegram-smoke-2026-02-28.json)
- M3 closure evidence bundle: [../checkpoints/m3-closure-evidence-2026-02-28.md](../checkpoints/m3-closure-evidence-2026-02-28.md)
- Latest policy gate summary: [../master-suite/phase1/ai-control/checkpoints/m3-policy-release-gate-summary.json](../master-suite/phase1/ai-control/checkpoints/m3-policy-release-gate-summary.json)
- Latest ops-alerts evidence: [../master-suite/phase1/ai-control/checkpoints/ops-alerts-evidence-latest.json](../master-suite/phase1/ai-control/checkpoints/ops-alerts-evidence-latest.json)

---

## Maintenance Note

When adding a new document to docs, update this index and the runbook document map in the same change.
