#!/bin/bash
set -e

# Lock and sync dependencies
rtk uv lock
rtk uv sync -U --link-mode=copy

# Format code
rtk uv run ruff format

# Check for linting errors
rtk uv run ruff check --fix

# Run type checking
rtk uv run ty check

# Bash files
echo "Checking bash files..."
sh_count=$(find ./scripts -name "*.sh" 2>/dev/null | wc -l)
echo "Found $sh_count bash file(s) to check"

if [ "$sh_count" -gt 0 ]; then
    # Format bash files
    shfmt_changed=$(find ./scripts -name "*.sh" -not -name ".deploy-*.sh" -exec shfmt -l -w {} + 2>/dev/null | wc -l)
    if [ "$shfmt_changed" -eq 0 ]; then
        echo "All bash files already formatted correctly!"
    else
        echo "Formatted $shfmt_changed bash file(s)"
    fi

    # Lint bash files
    if find ./scripts -name "*.sh" -not -name ".deploy-*.sh" -exec rtk uv run shellcheck {} +; then
        echo "All bash files passed shellcheck!"
    fi
fi
