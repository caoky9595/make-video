# Brainstorm Lại Concept Kênh — Sau Khi Đổi Sang Pipeline Google Flow/Veo

> Viết lúc: 2026-08-20. Bổ sung tầng "concept" phía trên `docs/content_ideas_bank.md` (danh sách ý tưởng cụ thể) và `channel_strategy.md` (chiến lược/chính sách).
>
> **Cập nhật pivot ngách (2026-08-20):** tài liệu này ban đầu viết cho ngách Mẹo Vặt Nhà Bếp & Gia Đình, tập trung vào việc nghĩ lại CÁCH KỂ khi đổi pipeline (Veo chuyển động thật thay ảnh tĩnh). Kênh vừa đổi ngách sang **Sự Thật Thú Vị & Tâm Lý Cuộc Sống** (lý do: xem `channel_strategy.md` mục pivot ở đầu file) — nội dung dưới đây đã re-theme lại toàn bộ ví dụ theo ngách mới. Các insight về pipeline (khả năng Veo, thư viện cảnh tái dùng) vẫn giữ nguyên vì đây là insight ở tầng sản xuất, không phụ thuộc ngách.

## 1. Insight cốt lõi thay đổi mọi thứ

Trước đây (ảnh AI tĩnh + Ken Burns): hình ảnh chỉ là "nền minh hoạ", giá trị nằm hết ở giọng đọc + phụ đề. Giờ (Veo): hình ảnh có thể **diễn** — nhân vật biểu cảm thật, ngôn ngữ cơ thể thật, chuyển cảnh mượt. Nhưng đổi lại **mỗi cảnh tốn 1 lần thao tác tay**. Hai hệ quả:

1. **Nhân vật giờ đáng để "diễn" hơn** — trước chỉ là hình nền, giờ có thể là lý do khiến người xem nhớ kênh và quay lại (giống nhân vật hoạt hình quen mặt của các kênh giáo dục/kids content).
2. **Sản xuất phải khôn hơn về số cảnh** — không thể vung tay làm 5-6 cảnh mỗi video như trước; cần thiết kế để MỖI CẢNH ĐÁNG GIÁ VÀ TÁI DÙNG ĐƯỢC.

> Lưu ý riêng cho ngách mới: đây là lý do ngách Sự Thật & Tâm Lý hợp với hoạt hình AI hơn hẳn ngách mẹo vặt bếp cũ — nội dung "sự thật/tâm lý" chỉ cần ĐÚNG và BẤT NGỜ, không cần "chứng minh nó hoạt động" như mẹo bếp (khán giả xem mẹo bảo quản/dọn dẹp bản năng nghi ngờ 1 bản demo hoạt hình vì không "thấy tận tay nó work"; còn sự thật tâm lý thì animation không hề bị nghi ngờ là giả).

## 2. Đề xuất: đặt tên + cố định nhân vật (mascot) — vẫn là ĐỀ XUẤT cho tương lai, chưa phải hiện trạng code

Hiện tại mô tả nhân vật do Gemini/Groq **tự chốt mới hoàn toàn cho mỗi video** (chỉ nhất quán TRONG PHẠM VI các cảnh của 1 video, không khoá cứng xuyên suốt kênh) — đổi tóc/trang phục/bối cảnh khác nhau giữa các video. Đề xuất **cố định 1 nhân vật xuyên suốt kênh** thay vì để AI tự chọn lại mỗi lần:

> *Gợi ý:* "chị Bống" — cô gái trẻ, tóc bob đen, phong cách đời thường/năng động, biểu cảm thân thiện dễ đồng cảm. Không gắn cố định với 1 bối cảnh nào vì nhân vật cần xuất hiện hợp lý ở nhiều bối cảnh khác nhau (phòng ngủ, văn phòng, công viên, quán café...) tuỳ chủ đề tâm lý từng video. (Tên/ngoại hình cụ thể do bạn chốt — quan trọng là CỐ ĐỊNH, không đổi mỗi video.)

**Vì sao đáng làm:** một nhân vật xuất hiện lặp lại qua nhiều video tạo cảm giác quen thuộc như "xem tiếp 1 series" thay vì "xem 1 clip lạ mỗi lần" — đúng playbook tăng follow (#5 trong `channel_strategy.md`: series đánh số/nhân vật quen giữ chân). Việc này không tốn thêm công — chỉ cần khoá cứng mô tả nhân vật trong prompt thay vì để AI tự nghĩ lại.

**Thực trạng code (quan trọng, tránh hiểu nhầm):** `core/engines/bg_finder.py` hiện tại chỉ yêu cầu AI chốt 1 mô tả nhân vật + phong cách NHẤT QUÁN TRONG 1 VIDEO (để các cảnh của cùng 1 video trông như "cùng 1 bộ phim") — KHÔNG có cơ chế khoá mô tả nhân vật xuyên suốt toàn kênh. Nói cách khác, mascot "chị Bống" ở trên vẫn chỉ là **đề xuất cho tương lai** (cần thêm 1 bước: hard-code mô tả nhân vật cố định vào prompt thay vì để AI tự sinh) — chưa phải điều hệ thống đang làm.

## 3. Đề xuất: xây "thư viện cảnh tái sử dụng" — giảm việc thao tác Flow theo thời gian

Đây là ý quan trọng nhất để giải quyết mâu thuẫn "khối lượng vs. công sức tay":

- Mỗi khi tạo 1 cảnh đẹp/trung tính (vd: "chị Bống ngồi trầm ngâm nhìn ra cửa sổ", "chị Bống mỉm cười nhẹ nhõm gật đầu", cảnh nền không gắn với hành động/chủ đề cụ thể) → **lưu lại riêng** thành 1 thư viện cảnh dùng chung (đặt tên rõ, vd `stock_smile_01.mp4`, `stock_window_wide.mp4`).
- Những cảnh này dùng lại được cho **HOOK hoặc CHỐT** của nhiều video khác nhau (2 đoạn ít cần khớp nội dung cụ thể nhất) — chỉ cảnh GIẢI THÍCH (thân bài, gắn với chủ đề sự thật/tâm lý cụ thể của video đó) mới cần tạo mới mỗi lần.
- Kết quả: từ video thứ ~5-10 trở đi, mỗi video có thể chỉ cần tạo **1 cảnh mới** (cảnh giải thích) thay vì 2-3 cảnh, vì hook/chốt lấy từ thư viện có sẵn. Công sức giảm dần theo thời gian, không phải trả giá mãi mãi.

## 4. Content Pillars (thay vì chỉ liệt kê theo định dạng)

Tổ chức lại thành các "chuyên mục" lặp lại có tên riêng — giúp khán giả nhận diện kênh rõ hơn là danh sách sự thật rời rạc:

| Pillar | Định dạng nền | Nhịp gợi ý | Số cảnh |
|---|---|---|---|
| **"Sự Thật Bất Ngờ"** | Myth-busting | 2 lần/tuần | 2-3 |
| **"Vì Sao Ta..."** | Before/After nhận thức | 2 lần/tuần | 2 |
| **"Mẹo Tâm Lý Đổi Đời"** | Khoảnh khắc đồng cảm, đánh số tập | 1 lần/tuần | 1-2 |
| **"Hỏi Đáp Tâm Lý"** | Reply-to-comment | 1 lần/tuần | 2-3 |
| Theo mùa/dịp (chen ngang khi hợp) | — | Không cố định | 2-3 |

Lịch mẫu 1 tuần (khớp nhịp 1-2 video/ngày trong `channel_strategy.md`):
Thứ 2: Sự Thật Bất Ngờ · Thứ 3: Vì Sao Ta... · Thứ 4: Mẹo Tâm Lý Đổi Đời #N · Thứ 5: Sự Thật Bất Ngờ · Thứ 6: Hỏi Đáp Tâm Lý · Thứ 7: Vì Sao Ta... · CN: nghỉ hoặc theo mùa.

## 5. Định dạng tận dụng đúng thế mạnh "chuyển động thật" của Veo

Những thứ ảnh tĩnh KHÔNG làm được nhưng Veo làm tốt — ưu tiên khai thác:
- **Biểu cảm thay đổi trong 1 cảnh**: mặt lo lắng/căng thẳng → mặt nhẹ nhõm (rất hợp hook myth-busting hoặc before/after nhận thức, không cần 2 cảnh riêng).
- **Ngôn ngữ cơ thể liên tục mượt** (thở dài bần thần nhìn trần nhà, giật mình quay đầu nhìn đồng hồ, ôm gối co ro, xoa tay lên đầu ngạc nhiên) — nền tảng của pillar "Mẹo Tâm Lý Đổi Đời" (khoảnh khắc đồng cảm). Đây là thay thế trực tiếp cho triết lý cũ "hành động tay oddly satisfying" của ngách mẹo bếp — giờ trọng tâm là biểu cảm/ngôn ngữ cơ thể khớp đúng cảm xúc của câu thoại.
- **Pan/reveal trong 1 clip**: camera lia từ tư thế co ro nhìn xuống điện thoại (căng thẳng, suy nghĩ sai) sang tư thế ngồi thẳng nhìn xa xăm bình thản (nhận thức đúng) CÙNG 1 cảnh — nếu Flow làm được, có thể gộp before/after nhận thức vào đúng 1 cảnh thay vì 2 (thử nghiệm, không chắc luôn khả thi tuỳ prompt).

## 6. Format nâng cao (thử nghiệm nhỏ trước khi mở rộng)
- **Hội thoại ngầm** (đã bàn ở lượt trước): 1 nhân vật chính kể lại lời người khác ("bạn A hỏi mình...") — giữ được kịch tính hội thoại mà KHÔNG cần dựng nhân vật phụ riêng (tránh nhân đôi chi phí nhất quán). Nếu muốn thử hội thoại 2 nhân vật thật, giới hạn thí điểm 1-2 video trước khi mở rộng.

## 7. Việc đã đổi vs. việc không đổi (pivot 2026-08-20)

**Đã đổi (do pivot ngách):**
- Ngách nội dung: từ "Mẹo Vặt Nhà Bếp & Gia Đình" sang "Sự Thật Thú Vị & Tâm Lý Cuộc Sống".
- Triết lý visual cho scene-prompt: từ "hành động tay oddly satisfying" (đổ, gấp, lau, đóng nắp) sang "khoảnh khắc đời thường relatable + biểu cảm/ngôn ngữ cơ thể" khớp cảm xúc câu thoại.
- Tên/chủ đề content pillars và ví dụ nhân vật/thư viện cảnh (mục 2-4-5 ở trên).
- Sản phẩm GĐ2 affiliate và nhóm nỗi đau digital-affiliate (xem `channel_strategy.md`, `content_ideas_bank.md`).

**Không đổi (đã đúng, giữ nguyên):** 2 giai đoạn viral→affiliate, công thức hook-thân-chốt 3 phần, cấu trúc "thư viện cảnh tái dùng" cho hook/chốt, chính sách AIGC/footage thật cho video bán hàng — tất cả trong `channel_strategy.md`/`RULES.md` vẫn đúng, không có lý do đổi.

---
*Xem `docs/content_ideas_bank.md` để lấy ý tưởng cụ thể theo từng pillar/định dạng ở trên.*
