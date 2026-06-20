#!/bin/bash
set -e

rtk uv lock
rtk uv sync -U --link-mode=copy
rtk uv run ruff format
rtk uv run ruff check --fix
rtk uv run ty check
rtk uv run shellcheck "$(dirname "$0")/dev.sh"
uv tool install --reinstall .
