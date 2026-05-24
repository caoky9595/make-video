# Workflow: Refactor

> Use this for code cleanup, reducing duplication, improving structure.
> Refactoring changes INTERNAL structure without changing EXTERNAL behavior.

## Step 1: BASELINE
Run tests and paste output — ALL must pass before refactoring:
```bash
bash .agents/skills/tester/scripts/run_tests.sh
```
→ If tests fail → fix them first. Do NOT refactor broken code.

## Step 2: AUTO-SCAN
Run pre_submit_check.sh to find issues automatically:
```bash
bash .agents/scripts/pre_submit_check.sh
```
→ Note all ❌ and ⚠️ items.

## Step 3: FIX ONE ISSUE
Pick ONE issue from the scan results. Make the smallest change:
- Duplicate code → extract into shared function
- Function > 30 lines → decompose
- Bare except → use specific exception
- print() → use logger
- Missing docstring → add docstring

## Step 4: VERIFY
Run tests again — paste output:
```bash
bash .agents/skills/tester/scripts/run_tests.sh
```
→ All tests must still pass. If any fail, your refactor changed behavior. Revert.

## Step 5: REPEAT or REPORT
More issues? → Go back to Step 3.
Done? → Run final check and report:
```bash
bash .agents/scripts/pre_submit_check.sh
```

```markdown
## ♻️ Refactor Report

### Changes Made
1. `file.py:L42` — [what changed]

### Verification Output
[paste FULL pre_submit_check.sh output]
```
