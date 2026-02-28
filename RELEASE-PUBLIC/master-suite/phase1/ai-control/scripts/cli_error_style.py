#!/usr/bin/env python3
import argparse
import sys

EXIT_USAGE = 2
EXIT_NO_KIND_BLOCKS = 4
EXIT_LOG_NOT_FOUND = 5


def exit_codes_text() -> str:
    return (
        "Exit codes: "
        "2=invalid usage/options, "
        "4=no matching kind blocks (--require-kind), "
        "5=log file not found"
    )


class StrictArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        if message.startswith("unrecognized arguments:"):
            unknown = message.split(":", 1)[1].strip()
            print(f"Unknown option: {unknown}", file=sys.stderr)
        elif message.startswith("the following arguments are required:"):
            required = message.split(":", 1)[1].strip()
            print(f"Missing required argument: {required}", file=sys.stderr)
        else:
            print(f"Error: {message}", file=sys.stderr)
        self.print_usage(sys.stderr)
        raise SystemExit(EXIT_USAGE)
