#!/bin/bash
set -e

uv lock
uv sync -U --link-mode=copy
uv run ruff format
uv run ruff check --fix
uv run ty check
uv run shellcheck "$(dirname "$0")/dev.sh"
uv tool install --reinstall .
