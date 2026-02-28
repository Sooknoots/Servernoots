#!/usr/bin/env bash

CLI_EXIT_USAGE=2
CLI_EXIT_NO_KIND_BLOCKS=4
CLI_EXIT_LOG_NOT_FOUND=5

cli_exit_codes_text() {
  echo "Exit codes: ${CLI_EXIT_USAGE}=invalid usage/options, ${CLI_EXIT_NO_KIND_BLOCKS}=no matching kind blocks (--require-kind), ${CLI_EXIT_LOG_NOT_FOUND}=log file not found"
}
