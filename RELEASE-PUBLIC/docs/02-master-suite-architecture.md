# Master Suite Architecture and Service Interaction Guide

## Architecture Intent

You are building a secure, modular private cloud where:

- Identity controls access (Authentik + MFA)
- Messaging controls interaction (ntfy/SMS)
- Automation executes actions (n8n + guarded tools)
- AI answers and reasons (Ollama + Qdrant + OpenWhisper for voice transcription)
- Security watches everything (CrowdSec + Suricata + Scrutiny)
- Homepage gives one clear control surface

## Core Planes

### 1) Access Plane

- Authentik is the SSO gate for all web UIs.
- Nginx Proxy Manager routes external/internal URLs to services.
- MFA is mandatory for admin and command-capable apps.

### 2) Network Plane

- Gluetun handles Windscribe route for privacy services.
- Headscale provides private mesh access for trusted devices.
- AdGuard Home provides DNS filtering for your network.

### 3) Control Plane

- ntfy is the event/messaging hub.
- n8n is the orchestrator for workflows and commands.
- Discord Bot (future frontend) can route text and voice intents into the same n8n guardrail workflows.
- OpenClaw/Agent Zero is optional autonomous operator with strict limits.

### 4) Knowledge Plane

- Qdrant stores embeddings and retrieval index.
- Wallabag + Paperless provide ingest sources.
- SearXNG provides private web lookup when local docs are insufficient.

### 5) Observability Plane

- Netdata (real-time), Beszel (historical), NVTOP (GPU), Scrutiny (disk health).
- CrowdSec/Suricata security events feed alerting.
- Tautulli adds Plex event telemetry.

## Key Interaction Contracts

### Contract A — Natural language control

1. User sends message in ntfy/SMS.
2. n8n parses intent.
3. If question: call Ollama (+ Qdrant lookup).
4. If command: run approved action only.
5. Send result back to ntfy.

Guardrails:

- Destructive command requires confirmation.
- High-risk actions require MFA re-auth or allowlist.

### Contract B — RAG ingestion loop

1. New article/doc appears in Wallabag/Paperless.
2. n8n ingest workflow chunks + embeds.
3. Vectors stored in Qdrant with source metadata.
4. Future answers cite source title/date.

### Contract C — Security response loop

1. CrowdSec/Suricata/Scrutiny detect event.
2. Event pushed to ntfy.
3. n8n can suggest or execute predefined remediation.
4. User gets status confirmation.

### Contract D — Media operations

1. Overseerr request enters arr pipeline.
2. Sonarr/Radarr/Prowlarr process and deliver to Plex libraries.
3. Tautulli reports playback/issues to ntfy.

### Contract E — Discord command + voice control (future)

1. User sends Discord slash command or mention command (for example: `join`, `leave`, `dj start`, `dj stop`).
2. Discord bot validates role/channel allowlist and writes command event to n8n webhook.
3. n8n applies existing guardrails/approval rules and returns action payload.
4. Bot executes allowed Discord action (join voice, start queue, skip track) and posts status back to Discord + `ops-alerts`.

Guardrails:

- Restrict command execution to approved Discord guild(s), channel(s), and role(s).
- Keep bot token in secrets only; never in workflow JSON or repo docs.
- Apply per-user and per-channel rate limits.
- Reuse existing audit path so Discord-triggered actions appear in `ai-audit`.

Spotify note:

- Spotify Premium enables user playback control via Spotify APIs, but does not grant permission for a custom Discord bot to rebroadcast Spotify audio into voice channels.
- Treat Spotify as a control source (queue metadata, recommendations, transfer to your own authorized device), not as raw audio stream source for Discord voice output.

## Homepage Design (clear labels)

Use these exact top-level sections so the panel is beginner-friendly:

1. **Core Access**

- Authentik
- Nginx Proxy Manager
- Headscale

1. **Security**

- CrowdSec
- Suricata
- AdGuard Home
- Scrutiny

1. **AI Control**

- n8n
- ntfy
- Ollama / OpenWebUI
- Qdrant
- Discord Bot (future)
- OpenClaw/Agent Zero

1. **Knowledge**

- Wallabag
- Paperless-ngx
- SearXNG

1. **Media**

- Plex
- Tautulli
- Sonarr / Radarr / Prowlarr / Overseerr
- Immich

1. **Operations**

- Netdata
- Beszel
- NVTOP (doc/help tile)
- Kopia
- Watchtower
- Gitea
- MeshCentral

1. **Home**

- Home Assistant

## Risk Boundaries (must enforce)

- Do not grant unrestricted shell to AI workflows.
- Use allowlisted scripts/commands only.
- Keep Plex/media exposure separate from admin exposure.
- Never deploy all services at once; phase with snapshots.

## Recommended Runtime Topology

- Proxmox host
  - VM-1: Core services (Access/Security/Control)
  - VM-2: Media services (Plex/arr/Immich)
  - VM-3: AI and RAG services (Ollama/Qdrant/n8n)

This separation limits blast radius and makes troubleshooting easier for beginners.

## Definition of Done

- You can log in through Authentik MFA.
- You can receive and send ntfy messages.
- You can ask AI a RAG-backed question and get a sourced answer.
- You can run one approved service action from phone with confirmation.
- Homepage has all sections above, clearly labeled and reachable.
