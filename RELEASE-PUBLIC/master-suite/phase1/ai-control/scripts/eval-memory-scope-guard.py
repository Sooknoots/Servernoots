#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guardrail: fail when replay memory scope accuracy drifts below threshold.")
    parser.add_argument("--threshold", type=float, default=0.95, help="Minimum required memory_scope_accuracy (default: 0.95)")
    parser.add_argument("--summary-file", default="/tmp/memory-scope-guard.json", help="Output summary JSON path")
    parser.add_argument("--cases", default="", help="Optional replay cases NDJSON path")
    parser.add_argument("--python", default="/usr/bin/python3", help="Python executable to run replay evaluator")
    return parser.parse_args()


def run_replay(args: argparse.Namespace) -> tuple[int, str, str]:
    cmd = [args.python, "scripts/eval-memory-replay.py", "--json"]
    if str(args.cases or "").strip():
        cmd.extend(["--cases", str(args.cases).strip()])
    proc = subprocess.run(cmd, text=True, capture_output=True)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def parse_replay_output(stdout_text: str) -> tuple[dict, list[str]]:
    issues: list[str] = []
    payload: dict = {}
    try:
        obj = json.loads(stdout_text)
        if isinstance(obj, dict):
            payload = obj
        else:
            issues.append("replay_output_not_json_object")
    except Exception as exc:
        issues.append(f"replay_output_not_json:{exc}")
    return payload, issues


def main() -> None:
    args = parse_args()
    rc, out, err = run_replay(args)

    summary: dict = {
        "threshold": float(args.threshold),
        "command_rc": rc,
        "checks": [],
        "overall_passed": False,
        "metrics": {},
        "stdout_tail": "\n".join((out or "").splitlines()[-20:]),
        "stderr_tail": "\n".join((err or "").splitlines()[-20:]),
    }

    if rc != 0:
        summary["checks"].append({"name": "replay_exec", "ok": False, "detail": f"rc={rc}"})
    else:
        summary["checks"].append({"name": "replay_exec", "ok": True, "detail": "ok"})

    payload, parse_issues = parse_replay_output(out)
    if parse_issues:
        for issue in parse_issues:
            summary["checks"].append({"name": "replay_json_parse", "ok": False, "detail": issue})

    replay_summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    scope_accuracy_raw = replay_summary.get("memory_scope_accuracy")
    total_cases_raw = replay_summary.get("total_cases")

    try:
        scope_accuracy = float(scope_accuracy_raw)
        summary["metrics"]["memory_scope_accuracy"] = scope_accuracy
        summary["checks"].append({
            "name": "memory_scope_accuracy_threshold",
            "ok": scope_accuracy >= float(args.threshold),
            "detail": f"value={scope_accuracy:.4f} threshold={float(args.threshold):.4f}",
        })
    except Exception:
        summary["checks"].append({
            "name": "memory_scope_accuracy_present",
            "ok": False,
            "detail": f"invalid_value={scope_accuracy_raw}",
        })

    try:
        total_cases = int(total_cases_raw)
        summary["metrics"]["total_cases"] = total_cases
        summary["checks"].append({"name": "total_cases_positive", "ok": total_cases > 0, "detail": f"value={total_cases}"})
    except Exception:
        summary["checks"].append({"name": "total_cases_present", "ok": False, "detail": f"invalid_value={total_cases_raw}"})

    checks = summary.get("checks", []) if isinstance(summary.get("checks"), list) else []
    summary["overall_passed"] = bool(checks) and all(bool(item.get("ok")) for item in checks)

    output_path = Path(args.summary_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"MEMORY_SCOPE_GUARD={'PASS' if summary['overall_passed'] else 'FAIL'}")
    print(f"SUMMARY_FILE={output_path}")
    for item in checks:
        print(f"- {item.get('name')}: {'PASS' if item.get('ok') else 'FAIL'} ({item.get('detail')})")

    if not summary["overall_passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
