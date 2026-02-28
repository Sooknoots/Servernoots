# Master Suite Rollout Plan (Beginner-Friendly)

## Goal

Build your Linux "Master Suite" in safe phases so you can learn as you go, avoid breakage, and keep your system secure from day one.

## Final Scope (from your chat log)

- Foundation: Proxmox, Ubuntu VM, Gluetun (Windscribe), AdGuard Home, Nginx Proxy Manager
- Security: CrowdSec, Suricata, Authentik (MFA), Livepatch, Kasm Workspaces
- Brain: n8n, ntfy (+ SMStfy), Ollama, Qdrant, OpenClaw/Agent Zero
- Frontends: Telegram bridge, ntfy/SMS, Discord bot (text now, voice/DJ later)
- Knowledge: Wallabag, Paperless-ngx, SearXNG
- Media: Plex, Tautulli, Immich, Sonarr/Radarr/Prowlarr/Overseerr
- Operations: MeshCentral, Gitea, Netdata, NVTOP, Beszel, Scrutiny, Watchtower, Kopia
- Home: Home Assistant, Homepage

## How this should work (simple view)

1. You send a message (ntfy or SMS).
2. n8n receives it and decides what to do.
3. For questions, it asks Ollama (+ Qdrant if docs are needed).
4. For actions, it calls controlled tools/scripts (restart/check/status).
5. Results/alerts come back to your phone through ntfy.
6. Homepage shows all service status in one clear panel.

## Deployment Phases

### Phase 0 — Prep & Safety (do first)

- Install Proxmox and create one Ubuntu 24.04 LTS VM for this suite.
- Turn on snapshots and take a snapshot after each successful phase.
- Set naming convention now (example: `svc-<name>` for containers).
- Set one password manager and MFA device before exposing anything.

Success criteria:

- You can restore VM from snapshot.
- You can SSH into VM.

### Phase 1 — The Fort (security + access)

- Deploy Gluetun (Windscribe static IP routing for privacy services).
- Deploy AdGuard Home (network DNS filtering).
- Deploy CrowdSec + basic bouncer integration.
- Deploy Authentik with MFA (TOTP or hardware key).
- Deploy Nginx Proxy Manager for clean HTTPS entrypoints.

Success criteria:

- Authentik login works with MFA.
- CrowdSec detects and blocks test bad behavior.
- Homepage can reach each Phase 1 service tile.

### Phase 2 — Command & Visibility

- Deploy Homepage (clear labels, grouped cards).
- Deploy ntfy + SMStfy (message in/out).
- Deploy Netdata + Beszel + NVTOP + Scrutiny.
- Connect key alerts (Scrutiny/CrowdSec/Tautulli later) to ntfy.

Success criteria:

- Phone receives a test alert.
- Homepage shows live health + link to each service.
- [x] Checkpoint: Tailnet multi-admin access enabled for approved admins via private HTTPS service mappings (servernoots.tail95a8ad.ts.net:8443-8456). (Completed: 2026-02-27)

### Phase 3 — AI Brain + RAG

- Connect existing Ollama/OpenWebUI.
- Deploy n8n and Qdrant.
- Add controlled command tools (restart/check/status only at first).
- Add RAG ingestion from Wallabag + Paperless-ngx.

Success criteria:

- You can ask a question via ntfy and get model reply.
- You can issue one safe action (example: restart one service) with confirmation.

### Phase 4 — Media + Automation

- Deploy Plex + Tautulli.
- Deploy arr stack + Overseerr.
- Deploy Immich.
- Keep Plex pathing and permissions stable before adding automation rules.

Success criteria:

- Plex stream works local + remote.
- Tautulli sends playback alerts to ntfy.

### Phase 5 — Ops + Quality of Life

- Deploy Gitea + MeshCentral + Kopia + Watchtower.
- Add SearXNG and Kasm Workspaces.
- Add Home Assistant (optional isolation VM recommended).

Success criteria:

- Backups run and restore test passes.
- Auto-update policy is controlled (not blind updates for critical services).

### Phase 6 — Discord Interface (AI + Voice Control)

Status: planning target only (design complete in this thread; implementation deferred).

- Add Discord bot service with slash commands that call n8n webhooks.
- Reuse existing tenant/role guardrails and audit logs for Discord-originated actions.
- Add controlled voice actions: join/leave channel, queue management, basic DJ mode prompts.
- Keep media provider abstraction so queue control can support legal sources cleanly.

Success criteria:

- Text command flow works end-to-end (`/ask`, `/ops`, `/join`, `/leave`).
- Discord actions are allowlisted, rate-limited, and audited in existing ops/audit paths.
- Voice session control is stable in one test guild/channel.

Spotify feasibility note:

- Spotify Premium can support account-level playback control and recommendations, but Spotify audio should not be restreamed by a custom Discord bot.
- For Discord voice DJ playback, use a provider path that permits bot voice delivery.

## Beginner Rules (important)

- Change one thing at a time.
- Snapshot before each phase.
- Do not expose new ports directly unless required.
- Require MFA for all admin routes.
- For AI command execution, require confirmation on destructive actions.

## First Week Checklist

- Day 1: Proxmox + Ubuntu VM + snapshot flow
- Day 2: Gluetun + AdGuard + Authentik + CrowdSec (Fort baseline)
- Day 3: Homepage + ntfy + monitoring baseline + first alert bridge path
- Day 4: n8n + Ollama bridge + Qdrant + guardrails + Telegram bridge + RAG routing hardening
- Day 5: Media stack (Plex, Tautulli, arr, Overseerr) with end-to-end request/playback validation
- Day 6: Ops hardening (Kopia, Watchtower policy, restore drill, alert tuning)
- Day 7: Final validation, UX closeout, and go-live baseline snapshot

## What to build first (today)

- Start with Phase 0 and Phase 1 only.
- Do not deploy AI command execution until identity, MFA, and alerting are confirmed working.
