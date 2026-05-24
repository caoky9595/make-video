# AI Agent Handbook (AGENTS.md)

> **Every agent MUST read and follow this file before executing any task.**

## 1. Project Context
- **Project name**: TikTok Auto Video Maker (make-video)
- **Purpose**: Tự động hóa quá trình tạo video từ script (TTS, background music/video ghép nối).
- **Stack**: Python / FFmpeg

## 2. MANDATORY CHECKLIST — Run Before Every Response

> [!CAUTION]
> These are **enforceable rules**, not suggestions. Violating any rule = failed task.

```
BEFORE writing any code, verify:
□ Have I read the relevant files first? (Not guessing structure)
□ Am I using the project's existing patterns? (Check existing code)

BEFORE saying "Done" or "Fixed", verify:
□ Have I run the actual command (test/lint/build) and pasted FULL output?
□ Does the output show 0 failures / 0 errors?
□ If I haven't run verification → I MUST NOT claim completion

BEFORE fixing a bug, verify:
□ Have I traced the root cause? (Not just suppressing the error)
□ Can I explain WHY the bug happens, not just WHERE?

ALWAYS:
□ Use logger (not print()) for Python
□ Use specific exceptions (not bare except/catch)
□ Read from os.getenv() for secrets (never hardcode)
□ Add type hints (Python) / JSDoc (JS/TS) to public functions
```

## 3. Iron Laws (NON-NEGOTIABLE)

1. **NO GUESSING** — If you don't know the file structure, READ it first. Never fabricate file paths, function names, or outputs.
2. **NO COMPLETION WITHOUT EVIDENCE** — You must run the verification command and paste its output. "It should work" is not evidence.
3. **NO FIXES WITHOUT ROOT CAUSE** — Trace the data flow. Explain the chain: Error → Direct cause → Root cause → Hypothesis.
4. **MINIMAL CHANGES** — Fix what's asked. Don't refactor, rename, or reorganize things that aren't part of the task.

## 4. Verification Commands (USE THESE — not just words)

Every rule above has a concrete verification. Run these, paste output:

| What to verify | Command |
|---------------|---------|
| Secrets, print(), bare except, syntax, docstrings, type hints, TODOs, tests | `bash .agents/scripts/pre_submit_check.sh` |
| Python syntax only | `python3 -m py_compile <file>.py && echo "✅ OK"` |
| Python lint + format | `bash .agents/skills/coder/scripts/lint_python.sh` |
| JS/TS lint + format | `bash .agents/skills/coder/scripts/lint_js.sh` |
| Run all tests | `bash .agents/skills/tester/scripts/run_tests.sh` |
| Check for hardcoded secrets | `grep -rn "api_key\|password\|token\|secret" . --include="*.py" \| grep -v venv` |
| Check for print() | `grep -rn "^\s*print(" . --include="*.py" \| grep -v test_ \| grep -v venv` |
| Check for bare except | `grep -rn "except:" . --include="*.py" \| grep -v venv` |
| Check for TODOs left behind | `grep -rn "TODO\|FIXME\|HACK" . --include="*.py" \| grep -v venv` |

> [!IMPORTANT]
> If you cannot run a verification command, STATE that explicitly:
> "I cannot verify because [reason]. Please run: `[command]`"
> NEVER silently skip verification.

## 5. Persistent Memory (Docs-as-Code)
- Save analysis/plans to `docs/ai/` for cross-session persistence
- Log lessons learned to `docs/ai/KNOWLEDGE.md` (Recovery Ledger)
- Use `docs/ai/repomap.txt` to understand project structure before grepping blindly

## 6. Tech Standards
- **Python**: pytest, type hints required, docstrings on public methods
- **Error Handling**: Specific exceptions, with context logged
- **Logging**: Structured (JSON preferred), never `print()`
- **Secrets**: Always `os.getenv()`, never in source code
- **MCP**: Prefer MCP Servers for external tool integration (DB, GitHub, Slack)
