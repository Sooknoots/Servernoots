# AI Personality System: 2-Week Implementation Plan

## Purpose

Define and deliver the next reliability layer for AI behavior in production:

1. **Persona Contract v1** (versioned behavior schema)
2. **Response Style Gate** (pre-send compliance checks)
3. **Correction Learning Loop v1** (structured adaptation from user corrections)

This plan assumes current Day 4 AI stack is active and telemetry scripts are already in place.

---

## Scope and Non-Goals

### In scope

- Deterministic response-shape controls before publish to `ai-replies`
- Explicit behavior contract fields carried in workflow debug metadata
- Lightweight correction-memory loop with clear safety bounds
- Validation and rollout gates with measurable pass/fail criteria

### Out of scope (this sprint)

- Full model fine-tuning
- Multi-language personality packs
- New channel integrations beyond existing Telegram + ntfy path

---

## Success Criteria

- Style-compliance pass rate >= 95% on smoke/eval sets
- Correction-acceptance latency remains within current operational bounds
- No increase in unsafe command routing or policy bypass incidents
- Weekly UX rollup shows stable or improved perceived score and reduced correction-related negatives

---

## Workstreams

## A) Persona Contract v1

### A Deliverables

- Contract schema fields defined and versioned (`persona_contract_version`)
- Contract attached to every AI reply decision path (smalltalk/RAG/general)
- Contract fields visible in debug metadata for telemetry parsing

### A Implementation targets

- `master-suite/phase1/ai-control/workflows/rag-query-webhook.json`
- `master-suite/phase1/ai-control/README.md`

### Minimum contract fields

- `persona_contract_version`
- `tone_target` (effective target tone)
- `brevity_target` (`short|balanced|detailed`)
- `style_must` (array)
- `style_must_not` (array)
- `safety_mode` (`default|strict`)

## B) Response Style Gate

### B Deliverables

- Gate step runs before publishing final AI reply
- Violations map to deterministic fallback rewrite (single retry)
- Gate result encoded in metadata (`style_gate_pass`, `style_gate_reason`)

### B Implementation targets

- `master-suite/phase1/ai-control/workflows/rag-query-webhook.json`
- `master-suite/phase1/ai-control/scripts/eval-routing.py` (or adjacent eval script)

### Initial gate checks

- No policy-disallowed phrasing
- No contradictory tone markers
- Bounded length based on `brevity_target`
- Required acknowledgement pattern when correction intent is detected

## C) Correction Learning Loop v1

### C Deliverables

- Structured extraction of correction events into per-user preference memory
- Preference merge policy with expiry and reset path
- Application of learned preferences only for stylistic behavior (never policy/safety overrides)

### C Implementation targets

- `master-suite/phase1/ai-control/bridge/telegram_to_n8n.py`
- `master-suite/phase1/ai-control/bridge/telegram_users.json` state model
- `master-suite/phase1/ai-control/README.md` operator controls

### Guardrails

- Learning disabled for non-allowlisted users
- Safety- and command-related constraints are immutable
- Admin reset command for correction memory

---

## Sprint Schedule (10 Working Days)

## Week 1

### Day 1-2: Persona Contract v1

- Add contract object in routing/format nodes
- Propagate contract into all reply branches
- Add basic contract presence checks to eval script

### Day 3-4: Style Gate v1

- Insert pre-send gate node
- Implement deterministic fallback rewrite path
- Emit structured gate pass/fail reasons

### Day 5: Week-1 hardening

- Run smoke set (smalltalk, RAG, general, correction prompts)
- Fix false positives/negatives in gate
- Update docs and examples

## Week 2

### Day 6-7: Correction Learning Loop v1

- Add correction-intent extraction and preference memory merge
- Apply learned stylistic preferences in prompt assembly
- Add reset/show admin controls for learned preferences

### Day 8: Telemetry integration

- Add correction-learning counters to daily/weekly summaries
- Include style-gate fail-rate and fallback-rewrite rate

### Day 9: Rollout rehearsal

- Replay eval cases + synthetic telegram smoke
- Verify no regression in command safety routing

### Day 10: Production rollout gate

- Final go/no-go review against acceptance checks
- Enable by default with rollback switch documented

---

## Acceptance Tests

- **Contract presence:** all AI replies include `persona_contract_version` in debug metadata
- **Gate behavior:** known bad-style fixtures trigger gate fail + deterministic rewrite
- **Correction memory:** repeated user correction changes subsequent style response
- **Safety isolation:** correction memory cannot alter command safety policies
- **Telemetry continuity:** daily/weekly scripts run clean with new fields present

---

## Rollout Gates

1. **Dev gate:** all syntax/JSON checks pass; no broken branches
2. **Eval gate:** >= 95% style-gate pass on approved fixture set
3. **Safety gate:** 0 critical policy regressions in routing eval
4. **Ops gate:** daily + weekly telemetry include new fields without parser breaks
5. **Prod gate:** monitored enablement with rollback toggle ready

---

## Risks and Mitigations

- **Risk:** gate over-rejects valid answers  
  **Mitigation:** bounded single-rewrite fallback + reason-codes review
- **Risk:** correction loop drifts behavior unexpectedly  
  **Mitigation:** short preference TTL, allowlist-only learning, admin reset
- **Risk:** telemetry schema drift breaks downstream parsing  
  **Mitigation:** additive fields only; keep existing keys stable

---

## Operator Checklist (Execution)

- [x] Implement Persona Contract v1 in workflow
- [x] Implement Style Gate node + fallback path
- [x] Implement Correction Learning Loop v1 in bridge
- [x] Extend eval/smoke scripts for contract and gate assertions
- [x] Extend daily/weekly metrics outputs with new counters
- [x] Update README and runbook references
- [x] Run final go/no-go gate review

## Go/No-Go Evidence (2026-02-27)

- Deploy/health:
  - `./scripts/publish-rag-query-workflow.sh`
  - Direct webhook probe returned healthy response with personality markers (`pc`, `tone_target`, `brevity`, `rb`) after parser regression fix.
- Routing + contract gate:
  - `python3 scripts/eval-routing.py --require-contract`
  - Result: all routing checks passed, including style-gate marker assertions (`sg`, `sgr`) and route budget expectations.
- Personality smoke validation:
  - `python3 scripts/eval-telegram-chat-smoke.py --mode all`
  - Result: `38/38` checks passed (live + local), including correction acknowledgement, uncertainty handling, confidence tier, recovery mode, and budget markers.
- Telemetry/KPI gate continuity:
  - `./scripts/run-ux-metrics-and-alert.sh`
  - Result: runs clean with KPI outputs present (`uncertainty_compliance`, `repeat_mistake_rate`) and no parser break.
- Decision: **GO** for current AI personality scope; continue with next milestone workstream (channel parity/Discord path) while monitoring daily/weekly UX and routing/smoke alerts.

---

## Phase 2 Backlog (Started 2026-02-27)

- [x] Start confidence-tier policy (`conf:<high|medium|low`) with low-confidence uncertainty enforcement.
- [x] Add per-user style preference controls (`/profile style ...`) and payload propagation.
- [x] Add personality smoke checks for correction + uncertainty + low-confidence tier.
- [x] Add micro-feedback controls (`/feedback too_short|too_long|too_formal|too_vague|good`) that auto-tune per-user style preferences.
- [x] Start persona drift detection telemetry (preference mismatch streaks + counters in bridge user state).
- [x] Add frustration recovery templates (acknowledge → restate → concise next step).
- [x] Add route-specific response budget enforcement refinements (smalltalk/ops/rag).
- [x] Add KPI release gates for uncertainty compliance + repeat-mistake rate.
