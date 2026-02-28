# Day 6 Kopia Policy + First Restore Drill Template

## Purpose

Provide a one-page, fill-in-ready policy and execution checklist so Day 6 can start immediately with consistent backup and restore standards.

## 1) Backup policy (fill in)

- Policy owner: `<name>`
- Effective date: `<YYYY-MM-DD>`
- Review cadence: `<weekly/monthly>`

### Backup scope

Include:

- `master-suite/phase1/*/docker-compose.yml`
- Service config paths under `master-suite/phase1/**`
- `docs/`
- `master-suite/phase1/ai-control/workflows/`
- `master-suite/phase1/ai-control/guardrails/`
- Immich metadata and DB artifacts (`media/immich/backups/*`)

Exclude (re-creatable/high-churn):

- Media payloads under `/srv/media/*`
- Photo originals under `/srv/photos/library/*` if separately replicated
- Cache/temp/runtime sockets and transient db files

### Retention policy

- Hourly snapshots: `<N hours>`
- Daily snapshots: `<N days>`
- Weekly snapshots: `<N weeks>`
- Monthly snapshots: `<N months>`

### Backup SLO

- Backup completion SLO: `<e.g., 99% successful daily jobs>`
- Restore verification SLO: `<e.g., one tested restore per week>`

## 2) Kopia baseline commands (starter)

Repository init example (filesystem target):

- `kopia repository create filesystem --path /srv/backups/kopia-repo`

Set global policy example:

- `kopia policy set --global --keep-hourly=24 --keep-daily=14 --keep-weekly=8 --keep-monthly=6`

Create path policies (examples):

- `kopia policy set $INSTALL_DIR/docs`
- `kopia policy set $INSTALL_DIR/master-suite/phase1/ai-control`
- `kopia policy set $INSTALL_DIR/master-suite/phase1/media`

Run first snapshot examples:

- `kopia snapshot create /media/sook/Content/Servernoots/docs`
- `kopia snapshot create /media/sook/Content/Servernoots/master-suite/phase1/ai-control`
- `kopia snapshot create /media/sook/Content/Servernoots/master-suite/phase1/media`

Verification:

- `kopia snapshot list`

## 3) First restore drill checklist (must pass)

Target file for drill (low-risk):

- `<path/to/test-file>`

### Drill steps

1. Record hash/version before change:
   - `sha256sum <path/to/test-file>`
2. Modify file intentionally:
   - Add a marker line: `RESTORE_DRILL_TEST_<date>`
3. Restore file from latest snapshot:
   - `kopia restore <snapshot-id>:<path/to/test-file> /tmp/restore-drill/`
4. Compare restored file with expected baseline:
   - `diff -u /tmp/restore-drill/<filename> <expected-source>`
5. Document result and elapsed time.

### Pass criteria

- [ ] Restore command completed without manual workaround
- [ ] Restored content matched expected baseline
- [ ] End-to-end elapsed time recorded
- [ ] Runbook updated with exact restore command used

## 4) Day 6 execution record

- Date/time run: `<timestamp>`
- Operator: `<name>`
- Backup command result: `<pass/fail>`
- Restore drill result: `<pass/fail>`
- Follow-up actions: `<items>`

## 5) Sign-off

- Security review complete: `[ ]`
- Ops review complete: `[ ]`
- Ready to mark Day 6 in runbook: `[ ]`
