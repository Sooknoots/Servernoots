#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CLI + HTTP M8 persistence proofs and report PASS/FAIL")
    parser.add_argument("--user-id", default="111")
    parser.add_argument("--expected-summary", default="allowed_should_persist")
    parser.add_argument("--summary-file", default="/tmp/discord-m8-proof-pack-summary.json")
    return parser.parse_args()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def run_script(script_path: Path) -> tuple[bool, str]:
    proc = subprocess.run(
        ["/usr/bin/python3", str(script_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(script_path.parent.parent),
        check=False,
    )
    output = proc.stdout.decode("utf-8", errors="replace")
    errors = proc.stderr.decode("utf-8", errors="replace")
    ok = proc.returncode == 0
    return ok, (output + ("\n" + errors if errors else "")).strip()


def evaluate(
    *,
    label: str,
    state_file: Path,
    audit_file: Path,
    proof_file: Path,
    user_id: str,
    expected_summary: str,
    run_ok: bool,
    run_output: str,
) -> dict:
    checks: list[dict[str, object]] = []

    checks.append({"name": "script_exit_ok", "ok": run_ok})

    state_exists = state_file.exists()
    checks.append({"name": "state_file_exists", "ok": state_exists, "path": str(state_file)})
    state_summary = ""
    if state_exists:
        try:
            state_obj = read_json(state_file)
            state_summary = str(((state_obj.get("users") or {}).get(user_id) or {}).get("memory_summary") or "")
            checks.append({"name": "state_summary_expected", "ok": state_summary == expected_summary, "value": state_summary})
        except Exception as exc:
            checks.append({"name": "state_parse_ok", "ok": False, "error": str(exc)})

    audit_exists = audit_file.exists()
    checks.append({"name": "audit_file_exists", "ok": audit_exists, "path": str(audit_file)})
    if audit_exists:
        audit_text = read_text(audit_file)
        checks.append({"name": "audit_has_blocked_false", "ok": '"memory_summary_persisted":false' in audit_text})
        checks.append({"name": "audit_has_allowed_true", "ok": '"memory_summary_persisted":true' in audit_text})

    proof_exists = proof_file.exists()
    checks.append({"name": "proof_file_exists", "ok": proof_exists, "path": str(proof_file)})

    passed = all(bool(item.get("ok")) for item in checks)
    return {
        "label": label,
        "passed": passed,
        "checks": checks,
        "state_summary": state_summary,
        "run_output_tail": "\n".join(run_output.splitlines()[-8:]),
    }


def main() -> None:
    args = parse_args()
    scripts_dir = Path(__file__).resolve().parent

    cli_script = scripts_dir / "eval-discord-memory-persistence-cli-proof.py"
    http_script = scripts_dir / "eval-discord-memory-persistence-http-proof.py"

    cli_ok, cli_output = run_script(cli_script)
    http_ok, http_output = run_script(http_script)

    cli_result = evaluate(
        label="cli",
        state_file=Path("/tmp/discord-m8-state-cli.json"),
        audit_file=Path("/tmp/discord-m8-audit-cli.jsonl"),
        proof_file=Path("/tmp/discord-m8-persistence-cli-proof.txt"),
        user_id=args.user_id,
        expected_summary=args.expected_summary,
        run_ok=cli_ok,
        run_output=cli_output,
    )
    http_result = evaluate(
        label="http",
        state_file=Path("/tmp/discord-m8-state-http.json"),
        audit_file=Path("/tmp/discord-m8-audit-http.jsonl"),
        proof_file=Path("/tmp/discord-m8-persistence-http-proof.txt"),
        user_id=args.user_id,
        expected_summary=args.expected_summary,
        run_ok=http_ok,
        run_output=http_output,
    )

    overall_passed = bool(cli_result["passed"] and http_result["passed"])
    summary = {
        "overall_passed": overall_passed,
        "expected_summary": args.expected_summary,
        "results": [cli_result, http_result],
    }

    summary_path = Path(args.summary_file)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"M8_PROOF_PACK={'PASS' if overall_passed else 'FAIL'}")
    print(f"SUMMARY_FILE={summary_path}")
    print(f"CLI_PROOF_FILE=/tmp/discord-m8-persistence-cli-proof.txt")
    print(f"HTTP_PROOF_FILE=/tmp/discord-m8-persistence-http-proof.txt")

    if not overall_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
