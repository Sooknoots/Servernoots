# Day 2 Checklist (Phase 1: The Fort)

## Day 2 Goal

Deploy your first security foundation services in a controlled way:

- Gluetun (Windscribe tunnel)
- AdGuard Home (DNS filtering)
- Authentik (identity + MFA)
- CrowdSec (automated blocking)

## Progress Status

- [x] Step 3 complete: Gluetun deployed and stable
- [x] Step 4 complete: AdGuard Home deployed and DNS tested
- [x] Step 5 complete: Authentik deployed and MFA enabled
- [x] Step 6 complete: CrowdSec deployed, metrics active, and controlled test event detected with active decision
- [x] Step 7 complete: Internal service map defined
- [x] Step 8 complete: integration verification checks passed
- [ ] Step 9 pending reboot re-check (checkpoint created)

## Time Budget

- Total: 3 to 5 hours
- Stop point: all four services reachable internally, no public exposure yet

## Before You Start

- Confirm Day 1 done and checkpoint exists: `day1-clean-base`
- Take a new pre-change checkpoint: `day2-before-fort`
- Keep one terminal open for logs and one for commands

## Step 1 — Prepare container runtime

Install and verify Docker/Compose on your Ubuntu VM.

Verification:

- `docker --version` works
- `docker compose version` works
- `sudo systemctl status docker` is active/running

## Step 2 — Create clear folder structure

Use one top folder (example):

- `~/master-suite/`
  - `gluetun/`
  - `adguard/`
  - `authentik/`
  - `crowdsec/`
  - `proxy/` (for later Nginx Proxy Manager)

Verification:

- Folders exist and are writable by your admin user

## Step 3 — Deploy Gluetun first

Configure Windscribe credentials and bring up only Gluetun.

Verification:

- Container starts without restart loop
- Logs show successful VPN connection
- Public IP from inside Gluetun matches Windscribe egress

If this fails:

- Stop and fix before deploying anything else

## Step 4 — Deploy AdGuard Home

Bring up AdGuard and bind it only to internal network initially.

Initial setup goals:

- Set admin username/password
- Set upstream DNS providers
- Import basic blocklists

Verification:

- AdGuard UI opens locally
- DNS query logs appear
- A test client can resolve domains through AdGuard

## Step 5 — Deploy Authentik (with DB + Redis)

Bring up Authentik stack components and complete initial admin setup.

Minimum Day 2 setup:

- Admin account created
- MFA enabled for admin account (TOTP minimum)
- Default policies in place for admin routes

Verification:

- Authentik UI is reachable internally
- Login works
- MFA challenge is required and successful

## Step 6 — Deploy CrowdSec

Deploy CrowdSec to monitor auth/service logs.

Minimum Day 2 setup:

- Parsers/scenarios loaded
- At least one bouncer path planned (host firewall or reverse proxy bouncer)

Verification:

- `cscli` shows healthy state
- Decisions list can be queried
- A controlled test event is detected by CrowdSec

## Step 7 — Internal service map and labels (Homepage prep)

Even before Homepage is live, define your display labels now:

### Core Access

- Authentik

### Security

- CrowdSec
- AdGuard Home

### Network

- Gluetun (Windscribe)

Use these exact names consistently in docs, hostnames, and dashboards.

Verification:

- You have a one-page note with each service name, URL, and purpose

Current internal service map (this environment):

- Gluetun status/logs only (no user UI)
- AdGuard Home setup: `http://localhost:3001`
- AdGuard Home admin UI: `http://localhost:8081`
- Authentik: `http://localhost:9000` (or `https://localhost:9443`)
- CrowdSec Local API: `127.0.0.1:8082` (internal/admin use)

## Step 8 — Validate integration basics

Run these practical checks:

1. Gluetun connected and stable for 15+ minutes
2. AdGuard resolving DNS and blocking test ad domain
3. Authentik login + MFA works twice in a row
4. CrowdSec reports active and ingesting logs

If any check fails:

- Roll back to `day2-before-fort` and retry one service at a time

Step 8 quick closeout checklist:

- [x] Gluetun connected and stable (VPN egress verified)
- [x] Authentik login + MFA verified
- [x] CrowdSec active, ingesting logs, and issuing decisions
- [x] AdGuard blocks at least one test ad domain from one client device

## Step 9 — Snapshot and freeze

When checks pass:

- Stop nothing unless required
- Create checkpoint archive: `day2-fort-stable`
- Document exact versions/images used

Verification:

- Snapshot exists
- Reboot VM once and re-check all service UIs

Host-system closeout (no Proxmox):

- Create archive checkpoint of phase1 folders and docs as `day2-fort-stable.tar.gz`
- Reboot host once and re-run service/UI checks

Current status (this run):

- [x] `checkpoints/day2-fort-stable.tar.gz` created
- [ ] Reboot re-check deferred by operator request (no reboot/log out during this session)

Step 9 command sequence (on VM) before/after reboot:

1. Before reboot, run `cd /media/sook/Content/Servernoots/master-suite/phase1/gluetun && docker compose ps`, `cd /media/sook/Content/Servernoots/master-suite/phase1/adguard && docker compose ps`, `cd /media/sook/Content/Servernoots/master-suite/phase1/authentik && docker compose ps`, and `cd /media/sook/Content/Servernoots/master-suite/phase1/crowdsec && docker compose ps`.
1. Create checkpoint archive `day2-fort-stable.tar.gz`.
1. Reboot VM.
1. After reboot, re-run the four `docker compose ps` commands above and verify UIs at `http://localhost:8081` (AdGuard) and `http://localhost:9000` (Authentik).

## Do Not Do on Day 2

- Do not expose Authentik/AdGuard directly to public internet yet
- Do not add autonomous command execution yet
- Do not connect production media stack yet
- Do not skip MFA setup

## Day 2 Definition of Done

You are done when all are true:

1. Gluetun connected to Windscribe and stable
2. AdGuard filtering DNS for at least one test client
3. Authentik reachable with MFA enforced for admin
4. CrowdSec active and reading logs
5. Checkpoint `day2-fort-stable` created and boot-tested

## Day 3 Preview

Next step is usability + observability:

- Homepage (clear labeled control panel)
- ntfy notifications
- Netdata/Beszel/Scrutiny visibility
