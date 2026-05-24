#!/bin/bash
# JS/TS Linting & Formatting Script
# Usage: bash .agents/skills/coder/scripts/lint_js.sh [target_dir]

TARGET="${1:-.}"
echo "🟨 JS/TS Lint & Format: $TARGET"
echo "================================"

# Check package manager
if [ -f "yarn.lock" ]; then
    PM="yarn"
elif [ -f "pnpm-lock.yaml" ]; then
    PM="pnpm"
else
    PM="npx"
fi

# Prettier formatting
if [ -f ".prettierrc" ] || [ -f "prettier.config.*" ] || [ -f ".prettierrc.json" ]; then
    echo "▶ Formatting with prettier..."
    $PM prettier --write "$TARGET/**/*.{ts,tsx,js,jsx,json}" 2>/dev/null || \
    npx prettier --write "$TARGET" 2>/dev/null
else
    echo "⚠️  No .prettierrc found — skipping prettier"
fi

# ESLint
if [ -f ".eslintrc*" ] || [ -f "eslint.config*" ]; then
    echo "▶ Linting with eslint..."
    $PM eslint "$TARGET" --fix --ext .ts,.tsx,.js,.jsx 2>/dev/null || \
    npx eslint "$TARGET" --fix 2>/dev/null
else
    echo "⚠️  No eslint config found — skipping eslint"
fi

# TypeScript type checking
if [ -f "tsconfig.json" ]; then
    echo "▶ Type checking with tsc..."
    npx tsc --noEmit 2>&1 | head -20
else
    echo "⚠️  No tsconfig.json found — skipping tsc"
fi

echo "================================"
echo "✅ JS/TS lint complete"
