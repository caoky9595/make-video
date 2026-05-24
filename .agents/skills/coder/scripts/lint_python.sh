#!/bin/bash
# Python Linting & Formatting Script
# Usage: bash .agents/skills/coder/scripts/lint_python.sh [target_dir]

TARGET="${1:-.}"
echo "🐍 Python Lint & Format: $TARGET"
echo "================================"

# Check if ruff is available, else try black/flake8
if command -v ruff &>/dev/null; then
    echo "▶ Formatting with ruff..."
    ruff format "$TARGET"
    echo "▶ Linting with ruff..."
    ruff check "$TARGET" --fix
elif command -v black &>/dev/null; then
    echo "▶ Formatting with black..."
    black "$TARGET"
    if command -v flake8 &>/dev/null; then
        echo "▶ Linting with flake8..."
        flake8 "$TARGET" --max-line-length=100
    fi
else
    echo "⚠️  No formatter found. Install: pip install ruff"
fi

# Type checking
if command -v mypy &>/dev/null; then
    echo "▶ Type checking with mypy..."
    mypy "$TARGET" --ignore-missing-imports --no-error-summary 2>&1 | tail -5
else
    echo "⚠️  mypy not found. Install: pip install mypy"
fi

echo "================================"
echo "✅ Python lint complete"
