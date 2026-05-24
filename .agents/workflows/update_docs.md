# Workflow: Update Docs

> Sử dụng workflow này để đồng bộ tài liệu kiến trúc với thực tế code sau khi đã hoàn thành một tính năng lớn hoặc sau một khoảng thời gian dài làm việc. (Docs-as-code sync).

## Step 1: LẤY THÔNG TIN HIỆN TẠI (SCAN)
```bash
# Tạo bản đồ code mới nhất
bash .agents/scripts/generate_repomap.sh

# Đọc repomap để hiểu toàn bộ cấu trúc hiện tại
cat docs/ai/repomap.txt
```

## Step 2: SO SÁNH TÀI LIỆU
1. Đọc các tài liệu thiết kế cũ trong `docs/ai/design/` hoặc `docs/ai/planning/`.
2. Đối chiếu những function/class được mô tả trong tài liệu với những function/class có thực sự trong `repomap.txt`.
3. Tìm kiếm những API, biến số, hoặc luồng data đã bị thay đổi trong quá trình code (mà tài liệu chưa cập nhật).

## Step 3: ĐỒNG BỘ HÓA (SYNC)
Viết lại/Sửa đổi các file Markdown trong `docs/ai/design/` để chúng phản ánh đúng 100% sự thật của code hiện tại.
- Cập nhật lại tên hàm.
- Cập nhật lại đường dẫn file nếu đã bị move.
- Cập nhật lại luồng xử lý nếu đã thay đổi.

## Step 4: BÁO CÁO (REPORT)
```markdown
## 📝 Update Docs Report

### Tài liệu đã được đồng bộ:
1. `docs/ai/design/[tên-file].md`
   - [Nêu tóm tắt những gì đã thay đổi để khớp với code]

### Tài liệu lỗi thời đã bị xóa (nếu có):
- `[tên-file]`
```
