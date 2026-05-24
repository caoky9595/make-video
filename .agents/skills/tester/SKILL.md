---
name: Coding Tester
description: Viết và chạy tests cho code vừa implement. Hỗ trợ pytest (Python) và Jest (JS/TS). Sau khi chạy test, nếu có failure sẽ báo kết quả chi tiết cho user và HỎI Ý KIẾN trước khi kích hoạt Debugger.
---

# Tester Agent

## QUICK REFERENCE — Read This First

```
STEP 1: Check test infrastructure
        Run: ls tests/ 2>/dev/null && echo "✅ tests/ exists"
        Run: python3 -m pytest --version 2>/dev/null && echo "✅ pytest available"

STEP 2: Write tests for new code
        □ At least 1 happy-path test per public function
        □ Edge cases: empty input, None, negative numbers
        □ Tests must be independent (no order dependency)
        □ Cleanup test data in teardown

STEP 3: Run tests — use THIS command, PASTE FULL output:
        bash .agents/skills/tester/scripts/run_tests.sh

        OR for specific file:
        python3 -m pytest tests/test_X.py -v --tb=short 2>&1

STEP 4: Report using this EXACT format:

        IF ALL PASS:
        "## ✅ Test Results: PASS
         [paste full terminal output here]"

        IF ANY FAIL:
        "## ❌ Test Results: FAILED
         [paste full terminal output here]
         Failed: [list test names + error messages]
         ---
         Do you want me to activate Debugger? (yes/no)"

RULES:
- You MUST paste terminal output — no summary without evidence
- NEVER say "tests pass" if you haven't run the command
- NEVER auto-activate Debugger — ASK user first and WAIT
```

---

<details>
<summary><strong>📖 Test Examples & Coverage Standards (expand)</strong></summary>

### Python (pytest) Example
```python
import pytest
from cache_manager import CacheManager

class TestCacheManager:
    def setup_method(self):
        self.cache = CacheManager(cache_file="/tmp/test_cache.json")
    
    def teardown_method(self):
        self.cache.clear()
    
    def test_set_and_get(self):
        self.cache.set("key1", "value1")
        assert self.cache.get("key1") == "value1"
    
    def test_get_nonexistent_returns_none(self):
        assert self.cache.get("nonexistent") is None
```

### TypeScript (Jest) Example
```typescript
import { CacheManager } from '../src/cacheManager';

describe('CacheManager', () => {
  let cache: CacheManager;
  beforeEach(() => { cache = new CacheManager(); });
  afterEach(() => { cache.clear(); });

  it('should set and get a value', () => {
    cache.set('key1', 'value1');
    expect(cache.get('key1')).toBe('value1');
  });
});
```

### Coverage Standards

| Code type | Min coverage |
|-----------|-------------|
| Core business logic | 80% |
| Utility functions | 70% |
| API handlers | 75% |
| Config/setup | 50% |

### Test Quality Checklist
- [ ] Each public function has ≥1 happy path test
- [ ] Important edge cases covered
- [ ] Tests independent (no order dependency)
- [ ] Test data cleaned up in teardown
- [ ] No sleep() or hardcoded delays in tests

</details>

---

## Output Templates

**PASS:**
```markdown
## ✅ Test Results: PASS
- Python: X/X tests passed
[paste full terminal output]
```

**FAIL:**
```markdown
## ❌ Test Results: FAILED

### Failed Tests:
1. `test_name` — Error message
   Stack: file.py:L23 in function()

---
**Do you want me to activate Debugger to fix these? (yes/no)**
```
