#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

from cli_error_style import (
    EXIT_LOG_NOT_FOUND,
    EXIT_NO_KIND_BLOCKS,
    StrictArgumentParser,
    exit_codes_text,
)


def parse_number(value: str):
    if value.endswith('%'):
        try:
            return float(value[:-1]) / 100.0
        except ValueError:
            return value
    try:
        if re.fullmatch(r"-?\d+", value):
            return int(value)
        if re.fullmatch(r"-?\d+\.\d+", value):
            return float(value)
    except ValueError:
        pass
    return value


def parse_kv_line(line: str):
    out = {}
    for key, value in re.findall(r"([a-zA-Z_]+)=([^\s]+)", line):
        out[key] = parse_number(value)
    return out


def parse_list_field(value: str):
    value = value.strip()
    if not value or value == "none":
        return []
    return [item.strip() for item in value.split(',') if item.strip()]


def parse_top_cues_line(line: str):
    m = re.match(r"^top_negative_cues=(.*?)(?:\s+cue_samples=(\d+))?$", line.strip())
    if not m:
        return {}

    top_raw = (m.group(1) or "").strip()
    cue_samples = m.group(2)
    parsed = {
        "top_negative_cues": parse_list_field(top_raw),
    }
    if cue_samples is not None:
        parsed["cue_samples"] = int(cue_samples)
    return parsed


def parse_block(lines):
    block = {
        "kind": "unknown",
    }

    if not lines:
        return block

    first = lines[0].strip()
    if first.startswith("UX metrics summary on "):
        block["kind"] = "daily"
        m = re.match(r"^UX metrics summary on (.+) at (.+)$", first)
        if m:
            block["host"] = m.group(1)
            block["timestamp"] = m.group(2)
    elif first.startswith("Weekly UX rollup on "):
        block["kind"] = "weekly"
        m = re.match(r"^Weekly UX rollup on (.+) at (.+)$", first)
        if m:
            block["host"] = m.group(1)
            block["timestamp"] = m.group(2)

    for raw in lines[1:]:
        line = raw.strip()
        if not line:
            continue

        if line.startswith("["):
            continue

        if "=" not in line:
            continue

        if line.startswith("top_negative_cues="):
            block.update(parse_top_cues_line(line))
            continue

        if line.startswith("warn_reasons="):
            _, value = line.split("=", 1)
            block["warn_reasons"] = parse_list_field(value)
            continue

        if line.startswith("warn_codes="):
            _, value = line.split("=", 1)
            block["warn_codes"] = parse_list_field(value)
            continue

        if line.startswith("log="):
            _, value = line.split("=", 1)
            block["log"] = value.strip()
            continue

        parsed = parse_kv_line(line)
        block.update(parsed)

    block.setdefault("warn_reasons", [])
    block.setdefault("warn_codes", [])
    block.setdefault("top_negative_cues", [])
    return block


def extract_blocks(text: str):
    lines = text.splitlines()
    blocks = []
    current = []

    header_pattern = re.compile(r"^(UX metrics summary on |Weekly UX rollup on )")

    for line in lines:
        if header_pattern.match(line.strip()):
            if current:
                blocks.append(parse_block(current))
            current = [line]
        elif current:
            current.append(line)

    if current:
        blocks.append(parse_block(current))

    return blocks


def main():
    parser = StrictArgumentParser(
        description="Parse UX metrics log summaries into JSON",
        epilog=exit_codes_text(),
    )
    parser.add_argument("log_file", help="Path to a daily or weekly UX metrics log file")
    parser.add_argument("--all", action="store_true", help="Output all parsed blocks from the file")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    parser.add_argument("--ndjson", action="store_true", help="Emit newline-delimited JSON (one block per line)")
    parser.add_argument("--latest-ndjson", action="store_true", help="Emit only the latest block as one NDJSON line")
    parser.add_argument("--kind", choices=["daily", "weekly", "both", "auto"], help="Filter parsed blocks by summary kind")
    parser.add_argument("--require-kind", action="store_true", help="Exit non-zero if --kind filtering yields no matching blocks")
    args = parser.parse_args()

    path = Path(args.log_file)
    if not path.exists():
        print(f"log file not found: {path}", file=sys.stderr)
        raise SystemExit(EXIT_LOG_NOT_FOUND)

    blocks = extract_blocks(path.read_text(encoding="utf-8", errors="ignore"))
    if args.kind and args.kind not in {"both", "auto"}:
        blocks = [block for block in blocks if block.get("kind") == args.kind]
        if args.require_kind and not blocks:
            print(f"no '{args.kind}' blocks found in {path}", file=sys.stderr)
            raise SystemExit(EXIT_NO_KIND_BLOCKS)

    if args.latest_ndjson:
        output = blocks[-1] if blocks else {}
        print(json.dumps(output, separators=(",", ":"), sort_keys=True))
        return

    if args.all:
        output = blocks
    else:
        output = blocks[-1] if blocks else {}

    if args.ndjson:
        rows = output if isinstance(output, list) else [output]
        for row in rows:
            print(json.dumps(row, separators=(",", ":"), sort_keys=True))
        return

    if args.pretty:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(json.dumps(output, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
