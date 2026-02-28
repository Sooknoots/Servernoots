.PHONY: m8-proof m8-proof-verbose m8-proof-clean m8-proof-fresh m8-proof-quick m8-proof-status m8-proof-all m9-parity m9-parity-status m3-policy-gate m3-policy-gate-status ops-alerts-evidence ops-alerts-evidence-status install-ops-alerts-evidence-cron uninstall-ops-alerts-evidence-cron telegram-role-allowlist-smoke telegram-role-allowlist-smoke-status memory-scope-guard memory-scope-guard-status memory-release-gate memory-release-gate-status memory-release-gate-checkpoint memory-release-gate-checkpoint-status memory-release-gate-signal-status memory-release-gate-signal-alert memory-release-gate-signal-log-cleanup install-memory-release-gate-cron uninstall-memory-release-gate-cron install-memory-release-gate-signal-cron uninstall-memory-release-gate-signal-cron deep-research-workflow deep-research-workflow-verify deep-research-regression deep-research-regression-status deep-research-regression-alert install-deep-research-regression-cron uninstall-deep-research-regression-cron





































m8-proof:
	/usr/bin/python3 scripts/eval-discord-memory-persistence-proof-pack.py

m8-proof-verbose:
	/usr/bin/python3 scripts/eval-discord-memory-persistence-proof-pack.py && \
	echo '--- M8 SUMMARY ---' && \
	head -n 40 /tmp/discord-m8-proof-pack-summary.json && \
	echo '--- CLI PROOF (tail) ---' && \
	tail -n 40 /tmp/discord-m8-persistence-cli-proof.txt && \
	echo '--- HTTP PROOF (tail) ---' && \
	tail -n 40 /tmp/discord-m8-persistence-http-proof.txt

m8-proof-clean:
	rm -f /tmp/discord-m8-proof-pack-summary.json \
	      /tmp/discord-m8-persistence-cli-proof.txt \
	      /tmp/discord-m8-persistence-http-proof.txt \
	      /tmp/discord-m8-state-cli.json \
	      /tmp/discord-m8-state-http.json \
	      /tmp/discord-m8-audit-cli.jsonl \
	      /tmp/discord-m8-audit-http.jsonl

m8-proof-fresh: m8-proof-clean m8-proof-verbose

m8-proof-quick: m8-proof-clean m8-proof

m8-proof-status:
	@if [ ! -f /tmp/discord-m8-proof-pack-summary.json ]; then \
		echo 'M8_PROOF_STATUS=NO_SUMMARY'; \
		exit 2; \
	fi
	@python3 -c "import json; d=json.load(open('/tmp/discord-m8-proof-pack-summary.json')); print('M8_PROOF_STATUS=' + ('PASS' if d.get('overall_passed') else 'FAIL'))"

m8-proof-all: m8-proof-fresh m8-proof-status

m9-parity:
	/usr/bin/python3 scripts/eval-discord-channel-parity-pack.py

m9-parity-status:
	@if [ ! -f checkpoints/m9-parity-summary.json ]; then \
		echo 'M9_PARITY_STATUS=NO_SUMMARY'; \
		exit 2; \
	fi
	@python3 -c "import json; d=json.load(open('checkpoints/m9-parity-summary.json')); print('M9_PARITY_STATUS=' + ('PASS' if d.get('overall_passed') else 'FAIL'))"

m3-policy-gate:
	/usr/bin/python3 scripts/eval-m3-policy-release-gate.py

m3-policy-gate-status:
	@if [ ! -f checkpoints/m3-policy-release-gate-summary.json ]; then \
		echo 'M3_POLICY_GATE_STATUS=NO_SUMMARY'; \
		exit 2; \
	fi
	@python3 -c "import json; d=json.load(open('checkpoints/m3-policy-release-gate-summary.json')); print('M3_POLICY_GATE_STATUS=' + ('PASS' if d.get('overall_passed') else 'FAIL'))"

ops-alerts-evidence:
	/usr/bin/python3 scripts/capture-ops-alerts-evidence.py

ops-alerts-evidence-status:
	@if [ ! -f checkpoints/ops-alerts-evidence-latest.json ]; then \
		echo 'OPS_ALERTS_EVIDENCE_STATUS=NO_SUMMARY'; \
		exit 2; \
	fi
	@python3 -c "import json; d=json.load(open('checkpoints/ops-alerts-evidence-latest.json')); print('OPS_ALERTS_EVIDENCE_STATUS=' + ('PASS' if d.get('overall_passed') else 'FAIL')); print('OPS_ALERTS_EVIDENCE_FILTERED=' + str(d.get('filtered_events', 0)))"

install-ops-alerts-evidence-cron:
	bash ./scripts/install-ops-alerts-evidence-cron.sh

uninstall-ops-alerts-evidence-cron:
	bash ./scripts/uninstall-ops-alerts-evidence-cron.sh

telegram-role-allowlist-smoke:
	/usr/bin/python3 scripts/eval-telegram-role-allowlist-smoke.py

telegram-role-allowlist-smoke-status:
	@if [ ! -f /tmp/telegram-role-allowlist-smoke.json ]; then \
		echo 'TELEGRAM_ROLE_ALLOWLIST_SMOKE_STATUS=NO_SUMMARY'; \
		exit 2; \
	fi
	@python3 -c "import json; d=json.load(open('/tmp/telegram-role-allowlist-smoke.json')); print('TELEGRAM_ROLE_ALLOWLIST_SMOKE_STATUS=' + ('PASS' if d.get('overall_passed') else 'FAIL'))"

memory-scope-guard:
	/usr/bin/python3 scripts/eval-memory-scope-guard.py

memory-scope-guard-status:
	@if [ ! -f /tmp/memory-scope-guard.json ]; then \
		echo 'MEMORY_SCOPE_GUARD_STATUS=NO_SUMMARY'; \
		exit 2; \
	fi
	@python3 -c "import json; d=json.load(open('/tmp/memory-scope-guard.json')); print('MEMORY_SCOPE_GUARD_STATUS=' + ('PASS' if d.get('overall_passed') else 'FAIL'))"

memory-release-gate:
	./scripts/run-memory-release-gate.sh

memory-release-gate-status:
	@if [ ! -f /tmp/memory-replay.json ]; then \
		echo 'MEMORY_RELEASE_GATE_STATUS=NO_REPLAY'; \
		exit 2; \
	fi
	@MEMORY_SCOPE_MIN="$${MEMORY_SCOPE_MIN:-0.95}" \
	 MEMORY_CONFLICT_FP_MAX="$${MEMORY_CONFLICT_FP_MAX:-0.05}" \
	 MEMORY_WRITE_GATE_MIN="$${MEMORY_WRITE_GATE_MIN:-0.98}" \
	 MEMORY_LATENCY_P95_MAX="$${MEMORY_LATENCY_P95_MAX:-250}" \
	 python3 -c "import json, os, sys; s=(json.load(open('/tmp/memory-replay.json')).get('summary') or {}); parse=lambda n,d: float(s[n]) if n in s and s[n] is not None else float(d); scope=parse('memory_scope_accuracy',0); cfp=parse('conflict_false_positive_rate',1); wg=parse('memory_write_gate_accuracy',0); lat=parse('memory_context_latency_ms_p95',10**9); ok=(scope>=float(os.environ['MEMORY_SCOPE_MIN']) and cfp<=float(os.environ['MEMORY_CONFLICT_FP_MAX']) and wg>=float(os.environ['MEMORY_WRITE_GATE_MIN']) and lat<=float(os.environ['MEMORY_LATENCY_P95_MAX'])); print('MEMORY_RELEASE_GATE_STATUS=' + ('PASS' if ok else 'FAIL')); sys.exit(0 if ok else 1)"

memory-release-gate-checkpoint:
	./scripts/run-memory-release-gate-checkpoint.sh

memory-release-gate-checkpoint-status:
	@if [ ! -f checkpoints/memory-release-gate/latest-memory-release-gate-summary.json ]; then \
		echo 'MEMORY_RELEASE_GATE_CHECKPOINT_STATUS=NO_SUMMARY'; \
		exit 2; \
	fi
	@python3 -c "import json; d=json.load(open('checkpoints/memory-release-gate/latest-memory-release-gate-summary.json')); print('MEMORY_RELEASE_GATE_CHECKPOINT_STATUS=' + ('PASS' if d.get('overall_passed') else 'FAIL'))"

memory-release-gate-signal-status:
	@if [ ! -f checkpoints/memory-release-gate/latest-memory-release-gate-summary.json ]; then \
		echo 'MEMORY_RELEASE_GATE_SIGNAL_STATUS=NO_SUMMARY'; \
		exit 2; \
	fi
	@python3 -c "import json, sys; d=json.load(open('checkpoints/memory-release-gate/latest-memory-release-gate-summary.json')); s=d.get('live_smoke_signal') or {}; enabled=bool(s.get('enabled')); passed=bool(s.get('passed')); mode=str(s.get('mode') or 'unknown'); rc=s.get('rc'); note=str(s.get('note') or ''); status=('DISABLED' if not enabled else ('PASS' if passed else 'FAIL')); print('MEMORY_RELEASE_GATE_SIGNAL_STATUS=' + status); print('MEMORY_RELEASE_GATE_SIGNAL_MODE=' + mode); print('MEMORY_RELEASE_GATE_SIGNAL_RC=' + str(rc)); print('MEMORY_RELEASE_GATE_SIGNAL_NOTE=' + note); sys.exit(0 if (not enabled or passed) else 1)"

memory-release-gate-signal-alert:
	./scripts/run-memory-release-gate-signal-alert.sh

memory-release-gate-signal-log-cleanup:
	./scripts/cleanup-memory-release-gate-signal-logs.sh

install-memory-release-gate-cron:
	./scripts/install-memory-release-gate-cron.sh

uninstall-memory-release-gate-cron:
	./scripts/uninstall-memory-release-gate-cron.sh

install-memory-release-gate-signal-cron:
	./scripts/install-memory-release-gate-signal-cron.sh

uninstall-memory-release-gate-signal-cron:
	./scripts/uninstall-memory-release-gate-signal-cron.sh

deep-research-workflow:
	./scripts/publish-deep-research-workflow.sh

deep-research-workflow-verify:
	./scripts/publish-deep-research-workflow.sh --verify

deep-research-regression:
	/usr/bin/python3 scripts/eval-deep-research-regression.py

deep-research-regression-status:
	@if [ ! -f checkpoints/deep-research-regression-latest.json ]; then \
		echo 'DEEP_RESEARCH_REGRESSION_STATUS=NO_SUMMARY'; \
		exit 2; \
	fi
	@python3 -c "import json; d=json.load(open('checkpoints/deep-research-regression-latest.json')); print('DEEP_RESEARCH_REGRESSION_STATUS=' + ('PASS' if d.get('overall_passed') else 'FAIL')); print('DEEP_RESEARCH_REGRESSION_RUN_ID=' + str(d.get('run_id_observed') or ''))"

deep-research-regression-alert:
	./scripts/run-deep-research-regression-and-alert.sh

install-deep-research-regression-cron:
	./scripts/install-deep-research-regression-cron.sh

uninstall-deep-research-regression-cron:
	./scripts/uninstall-deep-research-regression-cron.sh
