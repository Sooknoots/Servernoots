# Day 3 Checklist (Control Panel + Alerts + Monitoring)

## Day 3 Goal

Make your suite understandable at a glance by deploying:

- Homepage (clear, labeled control panel)
- ntfy (notification hub)
- Monitoring baseline (Netdata, Beszel, Scrutiny)

## Progress Status

- [x] Step 1 complete: Homepage deployed and reachable
- [x] Step 2 complete: Plain-language card descriptions added
- [x] Step 3 complete: ntfy deployed, terminal publish test passed, and phone app receives `ops-alerts` + `security-alerts`
- [x] Step 5 baseline complete: first alert path wired (`alert-bridge` -> `ops-alerts` / `security-alerts`)
- [x] Step 4 deployed: Netdata, Beszel, and Scrutiny containers are running and reachable locally
- [x] Step 4 closeout: short burn-in verified (`Netdata` API responds, `Beszel` UI responds, `Scrutiny` health endpoint responds)
- [x] Follow-up: Homepage URLs normalized for current networking mode
- [x] Step 8 snapshot created: `checkpoints/day3-panel-alerts-stable.tar.gz`
- [ ] Step 8 reboot validation deferred by operator request (no reboot/log out during this session)

## Time Budget

- Total: 3 to 5 hours
- Stop point: Homepage is usable, alerts hit phone, health is visible

## Before You Start

- Confirm snapshot exists: `day2-fort-stable`
- Take pre-change snapshot: `day3-before-visibility`
- Confirm Phase 1 services still healthy after reboot

## Step 1 — Deploy Homepage first

Bring up Homepage and keep it internal-only for now.

### Required section labels (use exactly)

1. Core Access
2. Security
3. Network
4. AI Control
5. Knowledge
6. Media
7. Operations
8. Home

### Minimum cards for Day 3

- Core Access: Authentik
- Security: CrowdSec, AdGuard Home
- Network: Gluetun (Windscribe)
- Operations: Netdata, Beszel, Scrutiny
- AI Control: ntfy (placeholder for n8n/Ollama later)

Verification:

- Homepage loads in browser
- Every card has a friendly title + one-line description
- Dead links are removed or marked "Coming Soon"

## Step 2 — Add plain-language descriptions

For each visible card, include:

- **What it is** (one sentence)
- **Why you care** (one sentence)

Example style:

- "CrowdSec — Blocks suspicious IPs automatically to protect your services."
- "Scrutiny — Watches hard drive health and warns before failure."

Verification:

- A non-technical person can read Homepage and understand each tile

## Step 3 — Deploy ntfy (notifications)

Bring up ntfy and create your first private topic for ops alerts.

Day 3 minimum topics:

- `ops-alerts`
- `security-alerts`

Verification:

- You can publish a test message from terminal
- Phone app receives it on both test topics

## Step 4 — Deploy monitoring baseline

Deploy and verify:

- Netdata (real-time)
- Beszel (historical trends)
- Scrutiny (drive health)

Verification:

- Netdata shows CPU/RAM/network data updating live
- Beszel shows host/container trend history
- Scrutiny detects at least one storage device

## Step 5 — Wire first alert path

Connect at least one monitored event to ntfy.

Recommended first alert:

- Scrutiny drive-health warning -> `security-alerts`

If Scrutiny alerting is not ready yet:

- Use a manual scheduled test message from host to `ops-alerts`

Verification:

- You receive one automated or scheduled health alert on phone

Current implementation note:

- `alert-bridge` stack is deployed at `master-suite/phase1/alerts/`
- Sends CrowdSec detections to `security-alerts`
- Sends service status-change alerts to `ops-alerts`

## Step 6 — Homepage quality pass

Make your control panel beginner-clear:

- Consistent icon style
- No acronym-only titles
- Group tiles by function (not by install order)
- Keep critical cards at top rows

Verification:

- Top row = Authentik, CrowdSec, Gluetun, AdGuard
- Health row = Netdata, Beszel, Scrutiny
- Alert row = ntfy status

## Step 7 — Document control panel map

Create/update your inventory note with:

- Service name
- URL
- Login method
- Purpose
- Alert topic (if any)

Verification:

- You can find any service in under 10 seconds from Homepage

## Step 8 — Snapshot and stability test

- Take snapshot: `day3-panel-alerts-stable`
- Reboot VM
- Re-check Homepage, ntfy, monitoring pages

Verification:

- All core Day 3 cards reachable after reboot
- At least one test alert still arrives on phone

## Do Not Do on Day 3

- Do not enable autonomous command execution yet
- Do not expose Homepage publicly yet
- Do not add 20+ tiles in one pass (keep panel readable)

## Day 3 Definition of Done

You are done when all are true:

1. Homepage has clear labeled sections and readable card text
2. ntfy sends alerts to your phone successfully
3. Netdata, Beszel, and Scrutiny all show data
4. A snapshot exists (`day3-panel-alerts-stable`)

## Day 4 Preview

Next you can add controlled AI interaction:

- n8n + Ollama bridge
- Qdrant for RAG
- Safe command allowlist with confirmation flow
