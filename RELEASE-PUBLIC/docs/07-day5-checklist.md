# Day 5 Checklist (Media + Automation + Photo Stack)

## Day 5 Goal

Deploy your media layer safely:

- Plex
- Tautulli
- Sonarr, Radarr, Prowlarr, Overseerr

- Immich


## Progress Status

Last updated: 2026-02-27



- [x] Day 5 pre-change snapshot created: `checkpoints/day5-before-media.tar.gz`

- [x] Step 1 bootstrap script prepared: `master-suite/phase1/media/day5-step1-storage-bootstrap.sh`
- [x] Step 1 apply complete: `/srv/media/*` and `/srv/photos/immich` provisioned with `sook:media` + setgid permissions
- [x] Step 2 initial deploy complete: Plex container running and reachable at `http://localhost:32400/web`
- [x] Plex storage drives ready: `/dev/sda2` -> `/srv/media/movies` (`PLEX_MOVIES`) and `/dev/sdc2` -> `/srv/media/tv` (`PLEX_TV`)
- [x] Step 2 closeout complete: Plex libraries configured and local playback validated
- [x] Step 3 initial deploy complete: Tautulli running at `http://localhost:8181`
- [x] Step 3 ntfy path validated: test message reached `media-alerts` from Tautulli runtime
- [x] Step 3 closeout complete: Tautulli linked to Plex and real playback-driven alert path validated
- [x] Step 4 deploy complete: Prowlarr + Sonarr + Radarr + qBittorrent running on Gluetun network path
- [x] Step 4 storage mapping validated: `/srv/media/downloads`, `/srv/media/tv`, `/srv/media/movies` writable from arr services
- [x] Step 4 live verification pass: Sonarr currently has indexers (7), qBittorrent client (1), and root folder (1)
- [x] Step 4 live verification pass: Radarr now has indexers (7), qBittorrent client (1), and root folder (1)
- [x] Step 4 integration verification: Prowlarr now links both Sonarr and Radarr applications
- [x] Step 4 API test run: Radarr `MoviesSearch` and Sonarr `MissingEpisodeSearch` commands completed successfully
- [x] Step 4 path hygiene check: Sonarr test series path/root now resolve to TV library (`/tv/Chernobyl` under `/tv`)
- [x] Step 4 interim issue resolved: earlier no-import state (`queue=0`, `hasFile=false`) cleared after qBittorrent recovery and rerun
- [x] Step 4 blocker root cause identified: qBittorrent was down, causing Arr grab failures (`Connection refused (localhost:8080)`)
- [x] Step 4 grab verification pass: Radarr manual release grab now succeeds and records `grabbed` history event
- [x] Step 4 reliability hardening: qBittorrent restart policy corrected to `unless-stopped` in Gluetun compose
- [x] Step 4 closeout complete: successful Radarr end-to-end import confirmed (`downloadFolderImported`, `hasFile=true`, file in `/srv/media/movies/Big Buck Bunny (2008)`)
- [x] Step 5 started: Overseerr deployed and reachable at `http://localhost:5055`
- [x] Step 5 runtime verification pass: Overseerr API responding (`/api/v1/status`) on version `1.35.0`
- [x] Step 5 setup initialized: Overseerr first-run state completed (`initialized=true`) via authenticated Plex bootstrap
- [x] Step 5 service wiring complete: Plex libraries enabled (Movies + TV Shows), Radarr and Sonarr instances linked in Overseerr
- [x] Step 5 closeout complete: one Overseerr request successfully handed off to Radarr (request `id=1`, title `Sintel`, TMDB `45745`, Radarr match found)
- [x] Step 6 pipeline verification (partial): Overseerr request is active and Radarr shows `grabbed` event for `Sintel` (TMDB `45745`)
- [x] Step 6 Plex visibility fix: Plex container mount refreshed after restart; Movies library now indexes imported media (`Big Buck Bunny` visible)
- [x] Step 6 transfer watch update: additional faster `Sintel` release grabbed (`Sintel (2010) 720p BRRip x264 -YTS`) to improve completion odds
- [x] Step 6 import complete: `Sintel` now imported (`hasFile=true`, `sizeOnDisk=576700012`) with `downloadFolderImported` events recorded
- [x] Step 6 Plex indexing complete: `Sintel` and `Big Buck Bunny` both visible in Plex Movies after refresh
- [x] Playback compatibility workaround: created `Sintel (2010) DirectPlay.mp4` (H.264 + AAC, faststart) so Plex clients can avoid transcode path failures
- [x] Step 6 final closeout complete: real Plex playback session observed; Tautulli fired playback actions (`on_play`, `on_pause`, `on_resume`, `on_stop`) and sent webhook notifications to `media-alerts`
- [x] Step 7 complete: Immich deployed + first successful phone/mobile backup confirmation captured (`public.asset` count increased from `0` to `2`)
- [ ] Step 10 in progress: `day5-media-stable` created and post-restart service checks passing; true host reboot validation deferred by operator for now


## Telegram Media Hardening Tracker


Use this tracker to execute the post-deploy hardening plan while Day 5 context is still active.



### Phase A — Day 1 critical controls

- [x] A1 Health watchdog verification

  - Run: `cd /media/sook/Content/Servernoots/master-suite/phase1/ai-control && docker compose ps telegram-n8n-bridge ntfy-n8n-bridge n8n`

  - Pass: all services remain `Up` through restart test.



- [x] A2 Synthetic end-to-end check
  - Run one Telegram media request (`/media ...`) and one ntfy publish test:
  - `curl -sS -H 'Title: Media Ready Synthetic' -H 'Priority: default' -d 'synthetic media ready' http://127.0.0.1:8091/media-alerts`
  - Pass: request reaches Overseerr and `telegram_notify_stats.json` records `media-alerts sent`.


- [x] A3 Secret rotation and validation

  - Rotate `TELEGRAM_BOT_TOKEN` + `OVERSEERR_API_KEY` in `ai-control/.env`.

  - Recreate bridges: `docker compose up -d --force-recreate telegram-n8n-bridge ntfy-n8n-bridge`
  - Pass: `/media` requests continue to succeed with new credentials.

  - Final status (2026-02-27): apply drill run succeeded after forced bridge recreation; `telegram-healthcheck` + synthetic request/fanout checks green; both secrets confirmed rotated across finalized apply sequence.



### Phase B — Week 1 stability controls


- [x] B1 Request disambiguation improvement
  - Add match-selection flow for ambiguous titles.

  - Pass: ambiguous queries do not auto-submit wrong media.


- [x] B2 Polling/backoff verification
  - Check: `docker logs --since 15m ntfy-n8n-bridge | grep -E 'HTTP Error 429|bridge error'`

  - Pass: no sustained throttling/error loops under normal load.



- [x] B3 Dedupe/idempotency validation

  - Re-send identical test event and verify first delivery + controlled suppression after.
  - Pass: no noisy duplicates while first alert remains delivered.


### Phase C — Week 2 resilience controls


- [ ] C1 Transactional state migration plan (JSON -> SQLite/Postgres)

  - Scope: users, dedupe, notify stats, incident state.

  - Pass: documented migration path + rollback path.


- [ ] C2 True availability-ready signal
  - Gate final user message on explicit Plex/Overseerr availability status.

  - Pass: "ready" notification aligns with actual playback availability.



- [ ] C3 Weekly control-plane audit report
  - Include request count, approval/deny count, failures, suppression totals.
  - Pass: recurring report artifact exists and is archived.



- [ ] C4 Restore drill for Telegram media control path

  - Restore bridge state from snapshot and re-run synthetic checks.

  - Pass: recovery meets expected time target and all checks return green.

## Next Sprint Execution Card (Telegram -> Plex)



Goal:

- Raise confidence that user requests and "ready" notifications are accurate, durable, and observable.



Execution checklist:


- [x] Sprint-1 Disambiguation interaction
  - Implement top-choice reply flow for ambiguous `/media` search results.
  - Require explicit selection token before request submission.
  - Validate with at least 3 ambiguous titles.

  - Validation run (2026-02-27, controlled live harness with Overseerr API):

    - `/media movie Dune` -> `requires_pick=true`, `auto_submitted=false`, `options_count=3` (PASS)
    - `/media movie Batman` -> `requires_pick=true`, `auto_submitted=false`, `options_count=3` (PASS)

    - `/media tv Shameless` -> `requires_pick=true`, `auto_submitted=false`, `options_count=3` (PASS)

    - Overall: `overall_pass=true`



- [x] Sprint-2 True-ready gating
  - Add explicit availability check before final "ready" Telegram message.
  - Prevent false-positive ready alerts when media is not playable.

  - Validate with one movie and one TV episode path.

  - Implementation status (2026-02-27): gate added in ntfy bridge (`media-alerts` ready-like events now verify Overseerr `mediaInfo.status >= 5` before Telegram fanout).
  - Validation run (targeted gate checks):
    - `Sintel is now available in Plex.` -> `allowed=true`, `reason=ready_verified:Sintel:status=5` (PASS)

    - `DefinitelyNotARealMovieXYZ is now available in Plex.` -> `allowed=false`, `reason=ready_gate_no_search_results` (PASS)

  - Closeout run (movie + TV path):

    - Movie path `Sintel is now available in Plex.` -> `allowed=true`, `reason=ready_verified:Sintel:status=5` (PASS)

    - TV path `Shameless is now available in Plex.` -> `allowed=false`, `reason=ready_not_confirmed:Shameless:status=0` (PASS, false-positive prevented)


- [x] Sprint-3 Scheduled synthetic checks

  - Add recurring check for request-path and `media-alerts` fanout-path.
  - Emit daily success heartbeat and immediate failure alert.

  - Validate alert behavior by forcing one controlled failure.

  - Implementation status (2026-02-27):

    - Added `scripts/run-media-synthetic-check-and-alert.sh` (request-path + fanout-path checks)
    - Added `scripts/install-media-synthetic-check-cron.sh` (daily cron at 07:05 local)
    - Heartbeat file path: `logs/media-synthetic-heartbeat.json`
  - Runtime evidence:
    - Request-path check: PASS (`request_path_ok`)
    - Fanout-path check: PASS (`fanout_processed:sent_partial:telegram_http_400`)
    - Latest heartbeat: `{ "status": "ok", "request_check": "request_path_ok", "fanout_check": "fanout_processed:sent_partial:telegram_http_400" }`

    - Post-hardening probe: PASS (`ops-alerts result=sent`, `quarantined=1`; invalid `telegram_http_400` recipient skipped)

    - Post-fallback run: PASS (`request_path_ok` + `fanout_processed:sent:none`; host-shell DNS mismatch no longer blocks check)


- [x] Sprint-4 Runtime state migration prep

  - Define schema for users, dedupe keys, notify stats, incident markers.
  - Prepare migration + rollback runbook for JSON -> DB state.
  - Validate restart consistency using migrated state.

  - Implementation status (2026-02-27): optional SQLite state backend scaffolded in `ntfy_to_n8n.py` with one-shot migration helper `scripts/migrate-telegram-state-json-to-sqlite.py`.

  - Operational status (2026-02-27): one-command cutover/rollback helpers added (`scripts/cutover-telegram-state-backend-sqlite.sh`, `scripts/rollback-telegram-state-backend-json.sh`).
  - Validation status (2026-02-27): rollback→validate→cutover→validate flip-test passed; synthetic monitor green in both backend modes; final backend set to `sqlite`.

- [x] Sprint-5 Secret rotation drill
  - Rotate Telegram + Overseerr secrets in staging order.
  - Validate `/media` request + alert fanout after rotation.
  - Record rollback command path in runbook.

  - Implementation status (2026-02-27): added `scripts/run-secret-rotation-drill.sh` (rehearsal + apply modes).

  - Validation status (2026-02-27): rehearsal PASS; final apply PASS with `--force-recreate` propagation fix (bridge restart + `telegram-healthcheck` + synthetic checks green; rollback command emitted).


Definition of done:



- [x] E2E happy path demo recorded and reproducible.

- [x] Ambiguous-title safety demo recorded and reproducible.

- [x] Restart/recovery demo recorded and reproducible.

  - Sign-off evidence (2026-02-27): request→Overseerr→fanout path validated, ambiguous title pick-flow validation passed, and state-backend cutover/rollback recovery drills passed with green synthetic heartbeats.



## Time Budget

- Total: 4 to 6 hours
- Stop point: one complete request-to-playback flow + one Immich backup test


## Before You Start

- Confirm snapshot exists: `day4-ai-rag-stable`

- Take pre-change snapshot: `day5-before-media`

- Confirm Authentik and ntfy still healthy



## Step 1 — Plan storage and permissions first (critical)

Create your media/data folder map before starting containers.



Recommended top-level structure:

- `/srv/media/movies`

- `/srv/media/tv`

- `/srv/media/downloads`

- `/srv/media/incomplete`
- `/srv/photos/immich`


Use one shared media group and consistent UID/GID mapping across media containers.



Verification:

- Containers can read/write expected folders
- No root-owned surprise files in media paths

## Step 2 — Deploy Plex only

Bring up Plex first and complete base library setup.



Initial tasks:

- Add Movies and TV libraries
- Confirm metadata fetch works
- Set remote access strategy (do not overexpose)

Verification:

- Local playback works from one client
- Library scan completes
- Playback does not fail due to file permissions

## Step 3 — Deploy Tautulli

Connect Tautulli to Plex and test alert output to ntfy.

Minimum alerts:

- Playback started
- Server down/recovered (if available)
- Library update complete

Verification:

- Tautulli sees active Plex sessions
- At least one test alert arrives on `ops-alerts` or `media-alerts`

## Step 4 — Deploy Prowlarr, then Sonarr/Radarr

Order matters for beginners:

1. Prowlarr (indexer manager)
2. Sonarr (TV)
3. Radarr (Movies)

Connect Sonarr/Radarr to Prowlarr and your download client.

Verification:

- Sonarr/Radarr can query indexers through Prowlarr
- One test search returns results
- Import paths map correctly to Plex folders

## Step 5 — Deploy Overseerr

Use Overseerr as your clean request interface.

Minimum setup:

- Link to Plex
- Link to Sonarr/Radarr
- Set request approval policy

Verification:

- Submit one test request in Overseerr
- Request reaches Sonarr/Radarr
- Item is eventually imported and visible in Plex

## Step 6 — End-to-end media workflow test

Run one complete movie or TV workflow:

1. Request in Overseerr
2. Search/queue in Sonarr or Radarr
3. Download + import to library path
4. Plex detects and plays
5. Tautulli sends alert

Verification:

- Entire path completes without manual file moving
- File naming and folder structure are clean

## Step 7 — Deploy Immich

Bring up Immich and connect storage path.

Initial tasks:

- Create admin account
- Enable mobile backup from one phone
- Keep AI/heavy jobs conservative initially

Verification:

- One photo backup from phone succeeds
- Timeline loads
- Thumbnails and metadata are visible

## Step 8 — Optional hardware acceleration check

Because your environment is advanced, verify acceleration deliberately.

Verification targets:

- Plex transcoding behavior is understood (with/without pass features)
- Immich ML/processing jobs do not starve system resources

If unstable:

- Reduce worker/job concurrency
- Keep playback priority over background indexing

## Step 9 — Homepage updates (Media section)

Add these clear cards:

- Plex — "Primary media playback server"
- Tautulli — "Plex activity and alerting"
- Overseerr — "Request movies and shows"
- Sonarr — "TV automation"
- Radarr — "Movie automation"
- Prowlarr — "Indexer manager"
- Immich — "Private photo backup and gallery"

Verification:

- Media section can be understood by a non-technical user
- Every card opens correct URL

## Step 10 — Snapshot and recovery point

- Take snapshot: `day5-media-stable`
- Reboot VM
- Re-test Plex playback + Overseerr request page + Immich login

Current status (this run):

- [x] `checkpoints/day5-media-stable.tar.gz` created (config/docs checkpoint archive)
- [x] In-session resilience validation completed via `docker compose restart` for Plex/Tautulli/Overseerr/Immich services; all recovered and endpoint probes returned expected status codes (Plex `302`, Overseerr `307`, Immich `200`)
- [x] Latest health verification rerun (2026-02-27): media stack `docker compose ps` shows Plex/Tautulli/Overseerr/Immich services `Up`
- [x] Latest endpoint verification rerun (2026-02-27): Plex `302`, Overseerr `307`, Immich `200`
- [x] Latest Immich backup validation rerun (2026-02-27): `validate-immich-backup.sh` passed with new artifacts under `media/immich/backups/2026-02-27-192427/`
- [x] Immich mobile backup evidence captured (2026-02-27): `BEFORE_COUNT=0`, `AFTER_COUNT=2`, `MOBILE_BACKUP_EVIDENCE_OK`
- [ ] True host reboot re-check deferred by operator for this session

Verification:

- Core media services recover automatically after reboot
- No missing mounts/paths after restart

Post-reboot verification command block (copy/paste):

Media service state:

`cd /media/sook/Content/Servernoots/master-suite/phase1/media && docker compose ps`

Endpoint checks:

`curl -sS -I --max-time 15 http://127.0.0.1:32400/web | head -n 1`

`curl -sS -I --max-time 15 http://127.0.0.1:5055 | head -n 1`

`curl -sS -I --max-time 15 http://127.0.0.1:2283 | head -n 1`

Expected status lines:

- Plex: `HTTP/1.1 302 Moved Temporarily`
- Overseerr: `HTTP/1.1 307 Temporary Redirect`
- Immich: `HTTP/1.1 200 OK`

Re-run Immich backup validation:

`cd /media/sook/Content/Servernoots/master-suite/phase1/media && ./validate-immich-backup.sh`

Immich mobile-backup evidence block (copy/paste):

Baseline asset count:

`BEFORE_COUNT=$(docker exec immich-postgres psql -U immich -d immich -tAc "select count(*) from public.asset;") && echo "BEFORE_COUNT=$BEFORE_COUNT"`

Then upload one new photo from the Immich mobile app, wait ~10-20s, and run:

`AFTER_COUNT=$(docker exec immich-postgres psql -U immich -d immich -tAc "select count(*) from public.asset;") && echo "AFTER_COUNT=$AFTER_COUNT"`

`docker logs --since 2m immich-server 2>&1 | grep -Ei 'assets|upload|/api/assets' | tail -n 40 || true`

`if [ "$AFTER_COUNT" -gt "$BEFORE_COUNT" ]; then echo MOBILE_BACKUP_EVIDENCE_OK; else echo MOBILE_BACKUP_EVIDENCE_MISSING; fi`

Mark closeout in this checklist:

- Flip `True host reboot re-check still pending` to complete once the above checks pass.

## Do Not Do on Day 5

- Do not combine media and security troubleshooting in same session
- Do not bypass permissions with broad `chmod 777`
- Do not expose downloader/indexer UIs publicly

## Day 5 Definition of Done

You are done when all are true:

1. Plex streams local content successfully
2. Tautulli alerts reach ntfy
3. Overseerr -> arr -> Plex path works end-to-end
4. Immich receives at least one successful mobile backup
5. Snapshot `day5-media-stable` exists

## Day 6 Preview

Operations hardening and resilience:

- Kopia backup policies
- Watchtower update strategy
- Scrutiny + alert tuning
- Restore drill and incident playbook
