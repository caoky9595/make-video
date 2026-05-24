# Workflow: New Feature

> Use this for adding a new feature. Follow steps IN ORDER.

## Step 1: UNDERSTAND
```bash
# Read project structure — don't guess
cat docs/ai/repomap.txt
# Read relevant source files
cat <relevant_file>.py
```
List the files you read: [file1, file2, ...]

## Step 2: PLAN
Write a brief plan:
- Files to create/modify
- Function signatures (with type hints)
- Data flow (input → process → output)

## Step 3: IMPLEMENT
Write code following existing project patterns:
□ Docstrings on all public functions
□ Use logger (not print)
□ Use specific exceptions (not bare except)
□ No hardcoded secrets

## Step 4: VERIFY
Run ALL commands and paste FULL output:
```bash
# 1. Lint and format (using your project's linter)
[PROJECT_LINT_COMMAND]

# 2. Full quality check (secrets, print, except, docstrings, type hints, TODOs, syntax, tests)
bash .agents/scripts/pre_submit_check.sh
```
→ Fix any ❌ errors before reporting done.

## Step 5: REPORT
```markdown
## ✅ Feature Complete: [Name]

### Files changed
- `file.py` — [what changed]

### Verification Output
[paste FULL pre_submit_check.sh output]
```
