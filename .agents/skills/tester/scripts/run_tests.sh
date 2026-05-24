#!/bin/bash
# Universal Test Runner
# Usage: bash .agents/skills/tester/scripts/run_tests.sh

echo "🧪 Running Test Suite"
echo "====================="

PYTHON_PASSED=0
PYTHON_FAILED=0
JS_PASSED=0
JS_FAILED=0

# ─── Python Tests ──────────────────────────────────────────
if [ -f "requirements.txt" ] || [ -f "setup.py" ] || [ -f "pyproject.toml" ]; then
    echo ""
    echo "🐍 Python Tests"
    echo "───────────────"
    
    # Detect virtual env
    if [ -d "venv" ]; then
        PYTEST="venv/bin/pytest"
    elif [ -d ".venv" ]; then
        PYTEST=".venv/bin/pytest"
    else
        PYTEST="python -m pytest"
    fi
    
    if $PYTEST --version &>/dev/null 2>&1; then
        # Run with coverage if available
        if $PYTEST --co -q &>/dev/null 2>&1; then
            $PYTEST -v --tb=short \
                --cov=. --cov-report=term-missing \
                2>&1 | tee /tmp/pytest_output.txt
            
            # Parse results
            PYTHON_PASSED=$(grep -oP '\d+(?= passed)' /tmp/pytest_output.txt | tail -1)
            PYTHON_FAILED=$(grep -oP '\d+(?= failed)' /tmp/pytest_output.txt | tail -1)
        else
            echo "⚠️  No tests found (no test files)"
        fi
    else
        echo "⚠️  pytest not installed: pip install pytest pytest-cov"
    fi
fi

# ─── JavaScript/TypeScript Tests ──────────────────────────
if [ -f "package.json" ]; then
    echo ""
    echo "🟨 JavaScript/TypeScript Tests"
    echo "───────────────────────────────"
    
    TEST_SCRIPT=$(cat package.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('scripts',{}).get('test',''))" 2>/dev/null)
    
    if [ -n "$TEST_SCRIPT" ] && [ "$TEST_SCRIPT" != "echo \"Error: no test specified\" && exit 1" ]; then
        npm test -- --passWithNoTests 2>&1 | tee /tmp/jest_output.txt
        
        JS_PASSED=$(grep -oP '\d+(?= passed)' /tmp/jest_output.txt | tail -1)
        JS_FAILED=$(grep -oP '\d+(?= failed)' /tmp/jest_output.txt | tail -1)
    else
        echo "⚠️  No test script configured in package.json"
    fi
fi

# ─── Summary ───────────────────────────────────────────────
echo ""
echo "====================="
echo "📊 SUMMARY"
echo "====================="

TOTAL_FAILED=$((${PYTHON_FAILED:-0} + ${JS_FAILED:-0}))

if [ -n "$PYTHON_PASSED" ] || [ -n "$PYTHON_FAILED" ]; then
    echo "Python : ${PYTHON_PASSED:-0} passed, ${PYTHON_FAILED:-0} failed"
fi
if [ -n "$JS_PASSED" ] || [ -n "$JS_FAILED" ]; then
    echo "JS/TS  : ${JS_PASSED:-0} passed, ${JS_FAILED:-0} failed"
fi

echo ""
if [ "$TOTAL_FAILED" -eq 0 ] 2>/dev/null; then
    echo "✅ ALL TESTS PASSED"
    exit 0
else
    echo "❌ $TOTAL_FAILED TEST(S) FAILED — Awaiting user decision"
    exit 1
fi
