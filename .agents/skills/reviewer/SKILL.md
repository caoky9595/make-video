---
name: Coding Reviewer
description: Review code vừa được viết theo checklist chi tiết về chất lượng, bảo mật, performance và maintainability. Chạy sau Coder, trước Tester. Báo cáo issues và fix trước khi chạy test.
sources:
  - jwadow/agentic-prompts (Gardener role)
  - baz-scm/awesome-reviewers (real-world PR patterns)
---

# Reviewer Agent

## QUICK REFERENCE — Read This First

```
STEP 1: BASELINE — Run tests, paste output (must all pass before reviewing):
        bash .agents/skills/tester/scripts/run_tests.sh

STEP 2: AUTO-SCAN — Run pre_submit_check.sh, paste output:
        bash .agents/scripts/pre_submit_check.sh
        ↳ This auto-detects: secrets, print(), bare except, missing
          docstrings, missing type hints, TODOs, syntax errors.
        ↳ Fix every ❌ error before proceeding.

STEP 3: MANUAL SCAN — Check what scripts can't catch:
        □ Duplicate code blocks (DRY violations)?
        □ Functions > 30 lines? → decompose
        □ Dead code? → Run: vulture . --min-confidence 80 (if available)

STEP 4: FIX — One issue at a time, run tests after each fix:
        bash .agents/skills/tester/scripts/run_tests.sh

STEP 5: FINAL CHECK — Run pre_submit_check.sh again, paste output:
        bash .agents/scripts/pre_submit_check.sh
        ↳ Must show "✅ ALL CHECKS PASSED" or "⚠️ PASSED WITH WARNINGS"

STEP 6: Generate Review Report (use template below)

RULES:
- Do NOT mix refactoring with new features
- Refactor = change INTERNAL structure, NEVER external behavior
```

---

<details>
<summary><strong>📖 Detailed Principles & Code Examples (expand)</strong></summary>

### Principle #0: Do No Harm

> "Refactor cải thiện cấu trúc BÊN TRONG mà KHÔNG thay đổi hành vi BÊN NGOÀI."

1. Chạy tests hiện có → Đảm bảo pass
2. Thay đổi nhỏ, nguyên tử
3. Chạy tests lại → Verify vẫn pass

### Code Smell Hunting

**🔴 Critical — Secret Exposure**:
```bash
grep -rn "api_key\s*=\s*['\"]" . --include="*.py" --include="*.ts" | grep -v ".env"
grep -rn "password\s*=\s*['\"]" . --include="*.py" --include="*.ts"
```

**🔴 Critical — Bare Exception**:
```python
# ❌ Bad
try:
    result = api.call()
except:
    pass

# ✅ Good
try:
    result = api.call()
except requests.exceptions.Timeout as e:
    logger.error("API timeout: %s", e)
    raise
```

**🟡 Important — DRY Violations**: Extract duplicate blocks into shared functions.

**🟡 Important — Long Methods**: Functions > 30 lines → decompose.

**🟡 Important — Magic Numbers**:
```python
# ❌ time.sleep(5)
# ✅ RETRY_DELAY_SECONDS = 5; time.sleep(RETRY_DELAY_SECONDS)
```

**🟢 Nice-to-have — Boundary Conditions**:
```python
def find_background(query: str) -> Optional[str]:
    if not query:          # Handle empty string
        return None
    if len(query) > 200:   # Handle very long query
        query = query[:200]
```

### Dependency Hygiene
- Update **one dependency at a time**
- Read CHANGELOG before updating
- Run full test suite after each update

### Dead Code Surgery
```bash
# Python
vulture . --min-confidence 80
# JavaScript/TypeScript
npx ts-prune
```

</details>

---

## Output: Review Report

```markdown
## Code Review: [File/Feature]

### 🔴 Critical Issues (MUST fix)
1. `file.py:L42` — Issue description → Fix: description

### 🟡 Important Issues (Should fix)
1. `file.py:L78` — Issue description → Suggestion: description

### 🟢 Suggestions
1. `file.py:L23` — Minor improvement

### ✅ Overall: [PASS / NEEDS WORK]
```
