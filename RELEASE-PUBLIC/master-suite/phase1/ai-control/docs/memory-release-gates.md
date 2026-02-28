# Memory Release Gates (Go / No-Go)

## Required Gates
- `memory_scope_accuracy >= 0.95`
- `conflict_false_positive_rate <= 0.05`
- `memory_write_gate_accuracy >= 0.98`
- `memory_context_latency_ms_p95 <= 250`
- Telegram smoke `--mode all` must pass
- Replay eval must pass

## Enforcement Commands
1. `./scripts/eval-telegram-chat-smoke.py --mode all`
2. `python3 ./scripts/eval-memory-replay.py --json > /tmp/memory-replay.json`
3. `make memory-scope-guard`
4. `make memory-release-gate`
5. `make memory-release-gate-checkpoint` (stores timestamped artifacts under `checkpoints/memory-release-gate/`)

## Rollback Triggers
- Any required gate fails twice consecutively
- Live `rag-query` webhook validation returns `HTTP 500`
- Scope accuracy drops by `>= 0.03` from previous accepted baseline

## Environment Overrides
- `MEMORY_SCOPE_MIN` (default `0.95`)
- `MEMORY_CONFLICT_FP_MAX` (default `0.05`)
- `MEMORY_WRITE_GATE_MIN` (default `0.98`)
- `MEMORY_LATENCY_P95_MAX` (default `250`)

## Cron Helpers
- Install daily checkpoint cron: `make install-memory-release-gate-cron`
- Uninstall cron: `make uninstall-memory-release-gate-cron`
- Optional schedule override: `MEMORY_RELEASE_GATE_CRON_SCHEDULE="40 6 * * *" make install-memory-release-gate-cron`
