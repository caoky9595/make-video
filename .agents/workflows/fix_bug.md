# Workflow: Fix Bug

> Use this workflow for any bug fix. Follow steps IN ORDER, do NOT skip.

## Step 1: REPRODUCE
```bash
# Run the failing command/test — paste FULL output
[PROJECT_TEST_COMMAND] [path_to_failing_test] 2>&1
```

## Step 2: ROOT CAUSE ANALYSIS
Write this template BEFORE writing any fix code:
```
Surface Error : [exact error message from Step 1]
Error Location: [file:line — from stack trace]
Root Cause    : [WHY it happens — trace data flow backwards]
Hypothesis    : "I believe [X] causes this because [Y]"
```
→ If you can't fill all 4 fields, you don't understand the bug yet. Read more code.

## Step 3: FIX
Apply the SMALLEST possible change to fix the root cause.
- Do NOT refactor other code
- Do NOT suppress the error with try/except
- Do NOT change unrelated files

## Step 4: VERIFY
Run BOTH commands and paste FULL output:
```bash
# 1. Verify the specific test passes
[PROJECT_TEST_COMMAND] [path_to_fixed_test] 2>&1

# 2. Verify nothing else broke
bash .agents/scripts/pre_submit_check.sh
```
→ Both must show ✅. If not → go back to Step 2.
→ After 3 failed attempts → STOP and ask user for guidance.

## Step 5: REPORT
```markdown
## 🔍 Fix Report

### Root Cause Analysis
Surface Error : [from Step 2]
Error Location: [from Step 2]
Root Cause    : [from Step 2]

### Fix Applied
`file.py:L42`: `old_code` → `new_code`

### Verification Output
[paste FULL output from Step 4]
```
