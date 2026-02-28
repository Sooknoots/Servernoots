#!/usr/bin/env python3
import argparse
import importlib.util
import json
import os
import statistics
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from path_safety import ensure_writable_env_path

ROOT = Path(__file__).resolve().parent.parent
BRIDGE_PATH = ROOT / "bridge" / "telegram_to_n8n.py"
DEFAULT_CASES = ROOT / "evals" / "memory" / "golden-replay.ndjson"


@dataclass
class CaseResult:
    case_id: str
    scope_expected: str | None
    scope_observed: str | None
    scope_match: bool
    retrieved_count: int
    relevant_count: int
    excluded_hits: int
    include_hit: bool
    conflict_expected: int | None
    conflict_observed: int
    conflict_match: bool
    gate_expected: str | None
    gate_observed: str | None
    gate_match: bool
    latency_ms: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay evaluator for memory behavior.")
    parser.add_argument(
        "--cases",
        default=str(DEFAULT_CASES),
        help="NDJSON replay cases file.",
    )
    parser.add_argument(
        "--naturalness-zip",
        action="append",
        default=[],
        metavar="PATH",
        help="Optional ZIP corpus for aggregate naturalness comparison (repeatable).",
    )
    parser.add_argument(
        "--max-zip-files",
        type=int,
        default=200,
        help="Maximum files to sample per ZIP corpus.",
    )
    parser.add_argument(
        "--max-zip-bytes-per-file",
        type=int,
        default=512000,
        help="Maximum bytes to read per file inside ZIP corpora.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON report.",
    )
    return parser.parse_args()


def load_cases(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"cases file missing: {path}")
    rows: list[dict[str, Any]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        obj = json.loads(line)
        if not isinstance(obj, dict):
            raise ValueError(f"line {line_no}: case must be object")
        for key in ("case_id", "user_id", "query", "expected"):
            if key not in obj:
                raise ValueError(f"line {line_no}: missing '{key}'")
        rows.append(obj)
    if not rows:
        raise ValueError("cases file has no usable rows")
    return rows


def bootstrap_bridge(tmp_path: Path):
    os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
    os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
    os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
    os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
    os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
    os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
    os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
    os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
    ensure_writable_env_path(
        "TELEGRAM_MEMORY_TELEMETRY_PATH",
        "/state/telegram_memory_telemetry.jsonl",
        tmp_path / "memory_telemetry.jsonl",
    )
    os.environ["TELEGRAM_MEMORY_MAX_ITEMS"] = "20"
    os.environ["TELEGRAM_MEMORY_SYNTHESIS_ENABLED"] = "1"
    os.environ["TELEGRAM_MEMORY_SYNTHESIS_MAX_ITEMS"] = "12"
    os.environ["TELEGRAM_MEMORY_CONFLICT_REQUIRE_CONFIRMATION"] = "1"
    os.environ["TELEGRAM_MEMORY_CONFLICT_PROMPT_ENABLED"] = "1"
    os.environ["TELEGRAM_MEMORY_INTENT_SCOPE_ENABLED"] = "1"

    spec = importlib.util.spec_from_file_location("telegram_bridge_memory_eval", BRIDGE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("bridge import spec failure")
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    return bridge


def extract_retrieved_lines(summary: str) -> list[str]:
    lines: list[str] = []
    for raw in str(summary).splitlines():
        line = raw.strip()
        if not line.startswith("- "):
            continue
        text = line[2:].strip()
        if not text:
            continue
        lines.append(text)
    return lines


def compute_case_result(bridge, case: dict[str, Any], now_ts: int) -> CaseResult:
    case_id = str(case.get("case_id", ""))
    user_id = int(case.get("user_id", 0) or 0)
    if user_id <= 0:
        raise ValueError(f"case {case_id}: invalid user_id")

    bridge.set_user_record(bridge.USER_REGISTRY, user_id, "user", status="active")
    bridge.save_user_registry(bridge.USER_REGISTRY)
    bridge.clear_memory(user_id)
    bridge.set_memory_enabled(user_id, True)

    setup_notes = case.get("setup_notes") if isinstance(case.get("setup_notes"), list) else []
    entry = bridge.get_memory_entry(user_id)
    entry["enabled"] = True
    entry["notes"] = []
    for note in setup_notes:
        if not isinstance(note, dict):
            continue
        ts = int(now_ts + int(note.get("ts_offset_s", -300)))
        entry["notes"].append(
            {
                "text": str(note.get("text", "")).strip(),
                "source": str(note.get("source", "telegram_user_note")),
                "tier": str(note.get("tier", "session")),
                "confidence": float(note.get("confidence", 0.9)),
                "ts": ts,
            }
        )
    bridge.save_memory_state(bridge.MEMORY_STATE)

    query_obj = case.get("query") if isinstance(case.get("query"), dict) else {}
    query_text = str(query_obj.get("text", "")).strip()
    mode = str(query_obj.get("mode", "rag")).strip().lower()

    expected_obj = case.get("expected") if isinstance(case.get("expected"), dict) else {}
    expected_scope_raw = expected_obj.get("scope")
    expected_scope = str(expected_scope_raw).strip().lower() if isinstance(expected_scope_raw, str) else None
    include_tokens = [str(x).strip().lower() for x in (expected_obj.get("must_include_any") or []) if str(x).strip()]
    exclude_tokens = [str(x).strip().lower() for x in (expected_obj.get("must_exclude_all") or []) if str(x).strip()]
    expected_conflict = expected_obj.get("expect_conflict_count")
    expected_conflict_count = int(expected_conflict) if isinstance(expected_conflict, int) else None
    expected_gate = expected_obj.get("expect_gate_reason")
    expected_gate_reason = str(expected_gate).strip() if isinstance(expected_gate, str) and str(expected_gate).strip() else None

    observed_scope_raw = bridge.infer_memory_intent_scope(query_text, mode=mode)
    observed_scope = str(observed_scope_raw).strip().lower() if observed_scope_raw else None

    started = time.perf_counter()
    enabled, summary, _provenance = bridge.get_memory_context(user_id, intent_scope=observed_scope)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if not enabled:
        summary = ""

    retrieved_lines = extract_retrieved_lines(summary)
    lower_lines = [line.lower() for line in retrieved_lines]

    include_hit = True if not include_tokens else any(any(tok in line for tok in include_tokens) for line in lower_lines)
    excluded_hits = 0
    for line in lower_lines:
        if any(tok in line for tok in exclude_tokens):
            excluded_hits += 1

    relevant_count = 0
    for line in lower_lines:
        has_excluded = any(tok in line for tok in exclude_tokens)
        if has_excluded:
            continue
        if include_tokens:
            if any(tok in line for tok in include_tokens):
                relevant_count += 1
        else:
            relevant_count += 1

    conflicts = bridge.list_memory_conflicts(user_id)
    observed_conflict_count = len(conflicts)
    conflict_match = True if expected_conflict_count is None else observed_conflict_count == expected_conflict_count

    gate_observed = None
    gate_match = True
    if expected_gate_reason:
        _allowed, gate_reason = bridge.memory_write_gate_decision(
            text=query_text,
            source="telegram_user_note",
            tier="preference",
            confidence=1.0,
            provenance={"channel": "telegram"},
        )
        gate_observed = str(gate_reason)
        gate_match = gate_observed == expected_gate_reason

    scope_match = observed_scope == expected_scope

    return CaseResult(
        case_id=case_id,
        scope_expected=expected_scope,
        scope_observed=observed_scope,
        scope_match=scope_match,
        retrieved_count=len(retrieved_lines),
        relevant_count=relevant_count,
        excluded_hits=excluded_hits,
        include_hit=include_hit,
        conflict_expected=expected_conflict_count,
        conflict_observed=observed_conflict_count,
        conflict_match=conflict_match,
        gate_expected=expected_gate_reason,
        gate_observed=gate_observed,
        gate_match=gate_match,
        latency_ms=round(elapsed_ms, 3),
    )


def safe_read_zip_texts(path: Path, max_files: int, max_bytes_per_file: int) -> list[str]:
    if not path.exists():
        return []
    snippets: list[str] = []
    allowed_ext = {".txt", ".md", ".json", ".jsonl", ".log", ".csv"}
    with zipfile.ZipFile(path, "r") as zf:
        names = [name for name in zf.namelist() if not name.endswith("/")]
        taken = 0
        for name in names:
            if taken >= max_files:
                break
            suffix = Path(name).suffix.lower()
            if suffix not in allowed_ext:
                continue
            with zf.open(name, "r") as fh:
                raw = fh.read(max(1, max_bytes_per_file))
            text = raw.decode("utf-8", errors="ignore").strip()
            if not text:
                continue
            snippets.append(text)
            taken += 1
    return snippets


def text_feature_vector(texts: list[str]) -> dict[str, float]:
    if not texts:
        return {
            "avg_chars": 0.0,
            "avg_words": 0.0,
            "punct_ratio": 0.0,
            "question_ratio": 0.0,
        }
    lines = []
    for blob in texts:
        for line in str(blob).splitlines():
            s = line.strip()
            if s:
                lines.append(s)
    if not lines:
        lines = [x.strip() for x in texts if str(x).strip()]
    if not lines:
        lines = [""]

    char_counts = [len(line) for line in lines]
    word_counts = [len(line.split()) for line in lines]
    punct = sum(sum(1 for ch in line if ch in ".,!?;:") for line in lines)
    chars = max(1, sum(len(line) for line in lines))
    questions = sum(1 for line in lines if "?" in line)

    return {
        "avg_chars": float(statistics.mean(char_counts)),
        "avg_words": float(statistics.mean(word_counts)),
        "punct_ratio": float(punct / chars),
        "question_ratio": float(questions / max(1, len(lines))),
    }


def naturalness_score(reference: dict[str, float], replay: dict[str, float]) -> float:
    diffs = []
    for key, scale in (("avg_chars", 120.0), ("avg_words", 24.0), ("punct_ratio", 0.25), ("question_ratio", 1.0)):
        base = float(reference.get(key, 0.0))
        obs = float(replay.get(key, 0.0))
        diffs.append(min(1.0, abs(base - obs) / max(0.0001, scale)))
    return round(max(0.0, 1.0 - float(statistics.mean(diffs))), 4)


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    total_retrieved = sum(r.retrieved_count for r in results)
    total_relevant = sum(r.relevant_count for r in results)
    total_excluded_hits = sum(r.excluded_hits for r in results)

    scope_cases = [r for r in results if r.scope_expected is not None]
    conflict_cases = [r for r in results if r.conflict_expected is not None]
    gate_cases = [r for r in results if r.gate_expected is not None]

    conflict_flagged = sum(r.conflict_observed for r in results)
    false_conflicts = sum(
        r.conflict_observed
        for r in conflict_cases
        if (r.conflict_expected is not None and r.conflict_observed > int(r.conflict_expected))
    )

    latencies = [r.latency_ms for r in results]
    lat_sorted = sorted(latencies)
    idx = max(0, min(len(lat_sorted) - 1, int(round(0.95 * (len(lat_sorted) - 1)))))
    p95 = lat_sorted[idx] if lat_sorted else 0.0

    precision = float(total_relevant / max(1, total_retrieved))
    scope_accuracy = float(sum(1 for r in scope_cases if r.scope_match) / max(1, len(scope_cases)))
    conflict_fp = float(false_conflicts / max(1, conflict_flagged)) if conflict_flagged > 0 else 0.0
    conflict_clear_rate = float(sum(1 for r in conflict_cases if r.conflict_match) / max(1, len(conflict_cases)))
    gate_accuracy = float(sum(1 for r in gate_cases if r.gate_match) / max(1, len(gate_cases))) if gate_cases else 1.0

    return {
        "total_cases": len(results),
        "memory_hit_precision": round(precision, 4),
        "memory_scope_accuracy": round(scope_accuracy, 4),
        "conflict_false_positive_rate": round(conflict_fp, 4),
        "conflict_resolution_clear_rate": round(conflict_clear_rate, 4),
        "memory_write_gate_accuracy": round(gate_accuracy, 4),
        "memory_context_latency_ms_p95": round(float(p95), 3),
        "excluded_token_hits": int(total_excluded_hits),
    }


def print_human(summary_obj: dict[str, Any], naturalness_obj: dict[str, Any] | None, results: list[CaseResult]) -> None:
    print(f"Memory replay evaluation: {summary_obj['total_cases']} case(s)")
    print("privacy_mode=in_memory_aggregate_only")
    print(f"- memory_hit_precision={summary_obj['memory_hit_precision']}")
    print(f"- memory_scope_accuracy={summary_obj['memory_scope_accuracy']}")
    print(f"- conflict_false_positive_rate={summary_obj['conflict_false_positive_rate']}")
    print(f"- conflict_resolution_clear_rate={summary_obj['conflict_resolution_clear_rate']}")
    print(f"- memory_write_gate_accuracy={summary_obj['memory_write_gate_accuracy']}")
    print(f"- memory_context_latency_ms_p95={summary_obj['memory_context_latency_ms_p95']}")
    if naturalness_obj:
        if naturalness_obj.get("status") == "ok":
            print(f"- naturalness_similarity_score={naturalness_obj['similarity_score']}")
            print(f"- naturalness_reference_files={naturalness_obj['reference_files']}")
        else:
            print(f"- naturalness_status={naturalness_obj.get('status', 'skipped')}")
            missing = naturalness_obj.get("missing_zips") or []
            if missing:
                print(f"- naturalness_missing_zips={','.join(str(x) for x in missing)}")
    failed = [
        r for r in results if not (r.scope_match and r.conflict_match and r.gate_match and r.include_hit and r.excluded_hits == 0)
    ]
    if failed:
        print("Top failures:")
        for item in failed[:10]:
            reasons = []
            if not item.scope_match:
                reasons.append("scope")
            if not item.include_hit:
                reasons.append("include")
            if item.excluded_hits > 0:
                reasons.append("exclude")
            if not item.conflict_match:
                reasons.append("conflict")
            if not item.gate_match:
                reasons.append("gate")
            reason = ",".join(reasons) if reasons else "unknown"
            print(f"  - {item.case_id}: {reason}")


def main() -> int:
    args = parse_args()
    cases_path = Path(args.cases)
    cases = load_cases(cases_path)

    with tempfile.TemporaryDirectory(prefix="memory-replay-") as tmp:
        bridge = bootstrap_bridge(Path(tmp))
        now_ts = int(time.time())
        results: list[CaseResult] = []
        for case in cases:
            results.append(compute_case_result(bridge, case, now_ts=now_ts))

    summary_obj = summarize(results)

    naturalness_obj = None
    if args.naturalness_zip:
        corpus_texts: list[str] = []
        consumed_files = 0
        missing_zips: list[str] = []
        for raw in args.naturalness_zip:
            path = Path(raw)
            if not path.exists():
                missing_zips.append(str(path))
                continue
            blobs = safe_read_zip_texts(path, max_files=max(1, args.max_zip_files), max_bytes_per_file=max(1024, args.max_zip_bytes_per_file))
            corpus_texts.extend(blobs)
            consumed_files += len(blobs)

        replay_texts: list[str] = []
        for case in cases:
            q = case.get("query") if isinstance(case.get("query"), dict) else {}
            replay_texts.append(str(q.get("text", "")))
            notes = case.get("setup_notes") if isinstance(case.get("setup_notes"), list) else []
            replay_texts.extend(str(item.get("text", "")) for item in notes if isinstance(item, dict))

        if corpus_texts:
            ref_vec = text_feature_vector(corpus_texts)
            replay_vec = text_feature_vector(replay_texts)
            naturalness_obj = {
                "status": "ok",
                "similarity_score": naturalness_score(ref_vec, replay_vec),
                "reference_files": consumed_files,
                "reference_features": ref_vec,
                "replay_features": replay_vec,
                "missing_zips": missing_zips,
            }
        else:
            naturalness_obj = {
                "status": "skipped_no_corpus",
                "reference_files": 0,
                "missing_zips": missing_zips,
            }

    if args.json:
        payload = {
            "summary": summary_obj,
            "naturalness": naturalness_obj,
            "cases": [r.__dict__ for r in results],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_human(summary_obj, naturalness_obj, results)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
