# Antigravity Agent Framework 🚀

**Framework Multi-Agent cho Trợ Lý AI Lập Trình — SOTA 2026**

Biến trợ lý AI của bạn thành một đội kỹ sư phần mềm kỷ luật với 9 vai trò chuyên biệt, luật thép không thương lượng, và bộ nhớ dài hạn.

---

## 🌟 Tính Năng Chính

- **8 AI Agent chuyên biệt** — Product Manager, Analyst, Architect, Coder, Reviewer, Tester, Debugger, DevOps
- **Luật Thép** — Các quy tắc bắt buộc ngăn AI code bừa:
  - Không đoán cấu trúc file → phải đọc trước
  - Không nói "xong" → phải chạy test, paste output
  - Không sửa bug mà không tìm root cause trước
- **Workflow theo loại task** — Hướng dẫn từng bước cho fix bug, thêm feature, quick fix, refactor
- **Script kiểm tra tự động** — Auto-verify: secrets, print(), bare except, docstrings, type hints, syntax, tests
- **Bộ nhớ dài hạn** — Docs-as-Code: kế hoạch, thiết kế, bài học rút ra lưu vào `docs/ai/`

---

## 📂 Cấu Trúc

```
.
├── ../AGENTS.md                      # Nội quy project — AI đọc đầu tiên
├── README.md                      # File này
│
├── 
│   ├── skills/                    # 8 vai trò
│   │   ├── product_manager/SKILL.md
│   │   ├── analyst/SKILL.md       # Nghiên cứu & lên kế hoạch
│   │   ├── architect/SKILL.md     # Thiết kế hệ thống & ADR
│   │   ├── coder/SKILL.md         # Viết code sạch
│   │   ├── reviewer/SKILL.md      # Review chất lượng & bảo mật
│   │   ├── tester/SKILL.md        # Viết & chạy tests
│   │   ├── debugger/SKILL.md      # Phân tích root cause
│   │   └── devops/SKILL.md        # Docker, CI/CD, monitoring
│   │
│   ├── workflows/                 # Hướng dẫn từng bước theo loại task
│   │   ├── fix_bug.md             # Quy trình sửa bug
│   │   ├── new_feature.md         # Quy trình thêm feature
│   │   ├── quick_fix.md           # Sửa nhỏ (không cần pipeline)
│   │   └── refactor.md            # Quy trình refactor
│   │
│   └── scripts/                   # Công cụ kiểm tra tự động
│       └── pre_submit_check.sh    # Kiểm tra 9 hạng mục chất lượng
│
└── docs/ai/                       # Bộ nhớ dài hạn (AI tự tạo)
    ├── repomap.txt                # Bản đồ cấu trúc project
    ├── KNOWLEDGE.md               # Sổ tay phục hồi (bài học debug)
    ├── requirements/              # Tài liệu yêu cầu (PRD)
    ├── planning/                  # Kế hoạch triển khai
    └── design/                    # Thiết kế kiến trúc & ADR
```

---

## 🚀 Hướng Dẫn Bắt Đầu

### 1. Cấu hình cho dự án của bạn
Mở `../AGENTS.md` và điền thông tin project. Đây là file AI bắt buộc phải đọc trước khi làm việc:
```markdown
## 1. Project Context
- **Project name**: Tên app của bạn
- **Purpose**: Mô tả ngắn
- **Stack**: Python / FastAPI / PostgreSQL
```

### 2. Cách 1: Dùng Workflow (Khuyến nghị cho 80% công việc)
Nói cho AI biết workflow nào cần follow:

| Tình huống | Prompt mẫu |
|-----------|------------|
| Sửa bug | *"Đọc `workflows/fix_bug.md` và follow đúng workflow để fix [mô tả bug]"* |
| Thêm tính năng mới | *"Đọc `workflows/new_feature.md` và thêm [mô tả feature]"* |
| Sửa nhỏ (typo, config) | *"Đọc `workflows/quick_fix.md` và fix [mô tả]"* |
| Refactor / dọn code | *"Đọc `workflows/refactor.md` và refactor [phạm vi]"* |
| Cập nhật Tài Liệu | *"Đọc `workflows/update_docs.md` và đồng bộ tài liệu với code"* |

### 3. Cách 2: Gọi đích danh một Role (Trường hợp đặc biệt)
Dùng khi bạn muốn ép AI suy nghĩ theo một chuyên môn cụ thể (Ví dụ: ép nó vạch lá tìm sâu, ép nó thiết kế hạ tầng):
```
"Đọc skills/debugger/SKILL.md và debug lỗi này: [paste error]"
"Đọc skills/reviewer/SKILL.md và tìm lỗ hổng bảo mật trong file X"
```

### 4. Dự án khám phá & Sáng tạo (Brainstorming)
Nếu bạn có dự án mới tinh chưa rõ yêu cầu, đừng vội ép AI viết code. Hãy dùng **Roles** để ép AI tư duy chậm và bài bản trước:

1. **Định hình ý tưởng (Dùng Product Manager):**
   * Prompt: *"Đóng vai `skills/product_manager/SKILL.md`. Tôi muốn làm [tên app]. Hãy brainstorm 3 hướng đi (Options). Sau khi chốt, viết PRD lưu vào `docs/ai/requirements/`"*
2. **Thẩm định công nghệ (Dùng Analyst):**
   * Prompt: *"Đọc `skills/analyst/SKILL.md`. Dựa trên PRD vừa lưu, hãy research xem ecosystem có thư viện nào phù hợp. Lập Implementation Plan lưu vào `docs/ai/planning/`"*
3. **Thiết kế kiến trúc (Dùng Architect):**
   * Prompt: *"Đọc `skills/architect/SKILL.md`. Dựa vào Plan, thiết kế Data flow và API interfaces. Lưu ADR vào `docs/ai/design/`"*
4. **Thi công (Chuyển sang dùng Workflow):**
   * Prompt: *"Đọc `workflows/new_feature.md`. Mở file thiết kế ở `docs/ai/design/` ra. Hãy viết code cho module đầu tiên."*

*Nguyên lý: Cắt não bộ của AI. Bắt nó tư duy và lưu bản vẽ (text file) xuống ổ cứng trước khi lao vào viết code.*

### 5. Cải tiến code có sẵn (Legacy Code)
Khi bạn muốn đập đi xây lại hoặc nâng cấp một tính năng cũ mà không làm gãy hệ thống:

1. **Khám bệnh (Dùng Analyst):**
   * Prompt: *"Chạy `bash scripts/generate_repomap.sh`. Đóng vai `skills/analyst/SKILL.md`. Phân tích chức năng [X], nó nằm ở những file nào và có điểm yếu thiết kế gì?"*
2. **Thiết kế lại (Dùng Architect) - Tùy chọn:**
   * Prompt: *"Đóng vai `skills/architect/SKILL.md`. Thiết kế lại chức năng [X] với luồng data mới. Không viết code."*
3. **Phẫu thuật (Dùng Workflow):**
   * Nếu chỉ dọn dẹp code cho sạch: *"Đọc `workflows/refactor.md` và refactor chức năng [X]."*
   * Nếu đổi hoàn toàn logic mới: *"Đọc `workflows/new_feature.md` và code lại chức năng [X] theo bản thiết kế mới."*
4. **Tái khám (Dùng Reviewer):**
   * Prompt: *"Đóng vai `skills/reviewer/SKILL.md`. Tự soi lại code mày vừa viết xem có side-effect nào ảnh hưởng đến các file khác không."*

---

## 🔧 Kiểm Tra Chất Lượng Tự Động

Khác với các AI Assistant thông thường, framework này ép AI (và cả bạn) phải verify chất lượng qua script:
```bash
bash scripts/pre_submit_check.sh
```
Kịch bản này bắt buộc AI vượt qua 9 bài test: Hardcoded secrets, `print()` rác, `except:` rỗng, thiếu docstrings, thiếu type hints, còn sót TODOs, lỗi syntax, và chạy test.

---

## 🛑 Xử Lý Khi AI Làm Sai (Luật Thép)

| Vấn đề | Prompt chấn chỉnh |
|--------|--------|
| AI đoán cấu trúc file | *"Vi phạm Luật Thép #1. Đọc file thật trước đã."* |
| AI nói 'xong' mà chưa test | *"Vi phạm: Chưa có bằng chứng. Chạy test và paste output."* |
| AI sửa bừa không tìm root cause | *"Vi phạm: Chưa trace root cause. Quay lại bước phân tích."* |
| AI tự ý sửa thêm thứ không yêu cầu | *"Vi phạm: Thay đổi tối thiểu. Revert và chỉ sửa cái tôi yêu cầu."* |
| AI bịa đặt cấu trúc project | *"Chạy script `bash scripts/generate_repomap.sh` và đọc file `docs/ai/repomap.txt`"* |
