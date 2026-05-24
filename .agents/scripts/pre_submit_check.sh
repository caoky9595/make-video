#!/bin/bash
# Pre-submit quality check — enforces AGENTS.md rules automatically
# Usage: bash .agents/scripts/pre_submit_check.sh [directory]
#
# This script is the SINGLE SOURCE OF TRUTH for enforceable rules.
# If a rule can't be checked by this script, it's aspirational, not enforceable.

TARGET_DIR="${1:-.}"
ERRORS=0
WARNINGS=0

echo "============================================="
echo "  🔍 Pre-Submit Quality Check"
echo "============================================="
echo ""

# --- CHECK 1: Hardcoded secrets ---
echo "🔐 [1/9] Hardcoded secrets..."
SECRET_HITS=$(grep -rn "api_key\s*=\s*['\"]" "$TARGET_DIR" --include="*.py" --include="*.ts" --include="*.js" 2>/dev/null | grep -v ".env" | grep -v "node_modules" | grep -v "venv" | grep -v "\.venv" | grep -v "__pycache__" | grep -v "example" | grep -v "SKILL.md" || true)
if [ -n "$SECRET_HITS" ]; then
    echo "$SECRET_HITS"
    echo "  ❌ FAIL: Hardcoded API keys found"
    ERRORS=$((ERRORS + 1))
else
    echo "  ✅ PASS"
fi

SECRET_HITS2=$(grep -rn "password\s*=\s*['\"]" "$TARGET_DIR" --include="*.py" --include="*.ts" --include="*.js" 2>/dev/null | grep -v "node_modules" | grep -v "venv" | grep -v "\.venv" | grep -v "test_" | grep -v "_test." | grep -v "example" | grep -v "SKILL.md" || true)
if [ -n "$SECRET_HITS2" ]; then
    echo "$SECRET_HITS2"
    echo "  ❌ FAIL: Hardcoded passwords found"
    ERRORS=$((ERRORS + 1))
else
    echo "  ✅ PASS (no hardcoded passwords)"
fi

# --- CHECK 2: print() in production code ---
echo ""
echo "🖨️  [2/9] print() in production code..."
PRINT_HITS=$(grep -rn "^\s*print(" "$TARGET_DIR" --include="*.py" 2>/dev/null | grep -v "test_" | grep -v "_test." | grep -v "venv" | grep -v "\.venv" | grep -v "__pycache__" | grep -v "scripts/" | grep -v "benchmark" | grep -v "SKILL.md" | grep -v "refactor_prints.py" | grep -v "add_docstrings.py" | grep -v "fix_docstrings.py" || true)
if [ -n "$PRINT_HITS" ]; then
    echo "$PRINT_HITS"
    echo "  ❌ FAIL: Use logger instead of print()"
    ERRORS=$((ERRORS + 1))
else
    echo "  ✅ PASS"
fi

# --- CHECK 3: Bare except blocks ---
echo ""
echo "🛡️  [3/9] Bare except blocks..."
EXCEPT_HITS=$(grep -rn "except:" "$TARGET_DIR" --include="*.py" 2>/dev/null | grep -v "venv" | grep -v "\.venv" | grep -v "__pycache__" | grep -v "# noqa" | grep -v "SKILL.md" | grep -v "node_modules" || true)
if [ -n "$EXCEPT_HITS" ]; then
    echo "$EXCEPT_HITS"
    echo "  ❌ FAIL: Use specific exceptions (except ValueError, except KeyError, etc.)"
    ERRORS=$((ERRORS + 1))
else
    echo "  ✅ PASS"
fi

# --- CHECK 4: Missing docstrings on public functions (Python) ---
echo ""
echo "📝 [4/9] Missing docstrings on public functions..."
MISSING_DOCS=0
for f in $(find "$TARGET_DIR" -name "*.py" -not -path "*/venv/*" -not -path "*/.venv/*" -not -path "*/__pycache__/*" -not -path "*/node_modules/*" -not -path "*/test_*" -not -name "test_*" -not -name "add_docstrings.py" -not -name "fix_docstrings.py" 2>/dev/null); do
    # Find public functions (not starting with _) that don't have a docstring on the next line
    while IFS= read -r line_info; do
        LINENUM=$(echo "$line_info" | cut -d: -f1)
        NEXT_LINE=$((LINENUM + 1))
        NEXT_CONTENT=$(sed -n "${NEXT_LINE}p" "$f" 2>/dev/null)
        if ! echo "$NEXT_CONTENT" | grep -q '"""\|'"'"''"'"''"'"'' 2>/dev/null; then
            echo "  ⚠️  $f:L$LINENUM — public function missing docstring"
            MISSING_DOCS=$((MISSING_DOCS + 1))
        fi
    done < <(grep -n "^\s*def [a-zA-Z][a-zA-Z0-9_]*(" "$f" 2>/dev/null | grep -v "def _" | grep -v "add_docstrings.py" | grep -v "fix_docstrings.py" || true)
done
if [ $MISSING_DOCS -eq 0 ]; then
    echo "  ✅ PASS"
else
    echo "  ⚠️  WARNING: $MISSING_DOCS public function(s) missing docstrings"
    WARNINGS=$((WARNINGS + 1))
fi

# --- CHECK 5: Missing type hints on public functions (Python) ---
echo ""
echo "🏷️  [5/9] Missing return type hints on public functions..."
MISSING_HINTS=0
for f in $(find "$TARGET_DIR" -name "*.py" -not -path "*/venv/*" -not -path "*/.venv/*" -not -path "*/__pycache__/*" -not -path "*/node_modules/*" 2>/dev/null); do
    HINTS=$(grep -n "^\s*def [a-zA-Z][a-zA-Z0-9_]*(.*)[^-]:" "$f" 2>/dev/null | grep -v "def _" | grep -v "\->" || true)
    if [ -n "$HINTS" ]; then
        while IFS= read -r hit; do
            echo "  ⚠️  $f:$hit"
            MISSING_HINTS=$((MISSING_HINTS + 1))
        done <<< "$HINTS"
    fi
done
if [ $MISSING_HINTS -eq 0 ]; then
    echo "  ✅ PASS"
else
    echo "  ⚠️  WARNING: $MISSING_HINTS function(s) missing return type hints (-> Type)"
    WARNINGS=$((WARNINGS + 1))
fi

# --- CHECK 6: TODO/FIXME/HACK left in code ---
echo ""
echo "📌 [6/9] TODO/FIXME/HACK markers in code..."
TODO_HITS=$(grep -rn "TODO\|FIXME\|HACK\|XXX" "$TARGET_DIR" --include="*.py" --include="*.ts" --include="*.js" 2>/dev/null | grep -v "node_modules" | grep -v "venv" | grep -v "\.venv" | grep -v "__pycache__" | grep -v "SKILL.md" | grep -v "KNOWLEDGE.md" || true)
if [ -n "$TODO_HITS" ]; then
    echo "$TODO_HITS"
    echo "  ⚠️  WARNING: Found TODO/FIXME markers — resolve or convert to issues"
    WARNINGS=$((WARNINGS + 1))
else
    echo "  ✅ PASS"
fi

# --- CHECK 7: Python syntax check ---
echo ""
echo "🐍 [7/9] Python syntax..."
PY_SYNTAX_ERRORS=0
for f in $(find "$TARGET_DIR" -name "*.py" -not -path "*/venv/*" -not -path "*/.venv/*" -not -path "*/__pycache__/*" -not -path "*/node_modules/*" 2>/dev/null); do
    if ! python3 -m py_compile "$f" 2>/dev/null; then
        echo "  ❌ Syntax error in: $f"
        PY_SYNTAX_ERRORS=$((PY_SYNTAX_ERRORS + 1))
    fi
done
if [ $PY_SYNTAX_ERRORS -eq 0 ]; then
    echo "  ✅ PASS"
else
    echo "  ❌ FAIL: $PY_SYNTAX_ERRORS file(s) with syntax errors"
    ERRORS=$((ERRORS + PY_SYNTAX_ERRORS))
fi

# --- CHECK 8: TypeScript compile check ---
echo ""
echo "📘 [8/9] TypeScript compilation..."
if [ -f "$TARGET_DIR/tsconfig.json" ]; then
    if npx tsc --noEmit 2>/dev/null; then
        echo "  ✅ PASS"
    else
        echo "  ❌ FAIL: TypeScript compilation errors"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "  ⏭️  SKIP (no tsconfig.json)"
fi

# --- CHECK 9: Run tests ---
echo ""
echo "🧪 [9/9] Tests..."
if [ -f "$TARGET_DIR/pytest.ini" ] || [ -f "$TARGET_DIR/pyproject.toml" ] || [ -d "$TARGET_DIR/tests" ]; then
    echo "  Running pytest..."
    if python3 -m pytest "$TARGET_DIR" -v --tb=short 2>&1; then
        echo "  ✅ PASS"
    else
        echo "  ❌ FAIL: Some tests failed"
        ERRORS=$((ERRORS + 1))
    fi
elif [ -f "$TARGET_DIR/package.json" ]; then
    echo "  Running npm test..."
    if npm test 2>&1; then
        echo "  ✅ PASS"
    else
        echo "  ❌ FAIL: Some tests failed"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "  ⏭️  SKIP (no test infrastructure)"
fi

# --- SUMMARY ---
echo ""
echo "============================================="
echo "  RESULTS"
echo "============================================="
echo "  ❌ Errors:   $ERRORS (must fix)"
echo "  ⚠️  Warnings: $WARNINGS (should fix)"
echo ""
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo "  ✅ ALL CHECKS PASSED"
elif [ $ERRORS -eq 0 ]; then
    echo "  ⚠️  PASSED WITH WARNINGS"
else
    echo "  ❌ FAILED — fix $ERRORS error(s) before proceeding"
fi
echo "============================================="

exit $ERRORS
