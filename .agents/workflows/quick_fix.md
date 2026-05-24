# Workflow: Quick Fix

> Use for simple, low-risk changes: typo fix, add a constant, rename a variable,
> small config change, etc. NO pipeline needed.

## Step 1: READ the relevant file(s)
Do NOT guess what the code looks like. Open and read it.

## Step 2: MAKE the change
Keep it minimal. Only change what's needed.

## Step 3: VERIFY
```bash
# Python
python -m py_compile <file>.py && echo "✅ Syntax OK"

# TypeScript  
npx tsc --noEmit && echo "✅ Compile OK"

# If tests exist
pytest tests/ -v --tb=short
```

Paste the output. Done.
