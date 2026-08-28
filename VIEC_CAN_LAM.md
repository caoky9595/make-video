# Việc Cần Làm — Kênh "Bống Kể"

> Cập nhật 28/08/2026. File này ghi việc CẦN LÀM TIẾP, không phải tài liệu kiến trúc.
> Chiến lược tổng thể xem `channel_strategy.md`.

---

## Tình hình hiện tại (số liệu thật, 5 video đầu)

| Video | Dài | View | Xem TB | % xem hết | Rời tại |
|---|---|---|---|---|---|
| Não ghi nhớ khuôn mặt (22/08) | 20s | 129 | 4,18s | 3,1% | 0:01 |
| Không trả lời tin nhắn (24/08) | 13s | 117 | 3,52s | 4,8% | 0:02 |
| 99% người nghĩ cười (25/08) | 11s | 122 | 3,89s | 6,2% | 0:01 |
| Trì hoãn không phải lười (25/08) | 8s | 116 | 2,77s | 8,1% | 0:02 |
| Não nhớ chuyện buồn (26/08) | 9s | 102 | — | — | — |

**Tổng: ~586 view · 0 bình luận · 0 follower.** Traffic For You ~100%.

### Đọc số cho đúng

**KHÔNG dùng "% xem hết" làm thước đo.** Video ngắn đi 2,5 lần (20s → 8s) mà thời
gian xem thật gần như không đổi (2,77-4,18s) — "% xem hết" tăng 3,1% → 8,1% chỉ vì
mẫu số nhỏ đi, không phải người xem ở lại lâu hơn.

**Chỉ số đúng: `Average watch time` tính bằng GIÂY.** Hiện đóng đinh 2,77-4,18s.

Vào TikTok Studio → Analytics → bấm từng video → xem ô "Average watch time".

---

## BƯỚC 1 — Làm 2 video mới, không đổi gì ngoài bản vá kỹ thuật

4 lỗi dưới đây đã sửa trong code nhưng **chưa video nào chạy thật**. Cả 5 video đã
đăng đều dựng TRƯỚC khi có các bản vá này:

| Lỗi | Đo được | Đã sửa thành |
|---|---|---|
| Hình đứng yên | 99% pixel giống hệt giữa 2 frame | Thêm chuyển động camera (pixel đổi 26,6% → 68,5%) |
| Cảnh quá dài | 6-8s/cảnh không đổi hình | 4s/cảnh, cắt cảnh dày gấp đôi |
| Video dìm tối | clip gốc 126/255 → xuất ra 81/255 | 113/255 |
| Ảnh bìa dìm tối | 46/255, tối gần gấp 3 clip gốc | 89/255 |

### Việc phải làm

1. Sinh kịch bản MỚI trong app (đừng dùng lại kịch bản cũ — bản vá hook và CTA
   nằm trong phần sinh kịch bản).
2. Kiểm tra kịch bản đạt 2 điều:
   - 3-5 từ đầu là **con số** hoặc điều bất ngờ. Không được mở bằng "Bạn có biết…",
     "Bạn có bao giờ…", "Hôm nay mình sẽ…".
   - Kết bằng **câu hỏi trả lời được trong 2-3 chữ**. Bản vá CTA này **chưa từng
     chạy thật lần nào** — 0 bình luận hiện tại là vì các video cũ kết bằng
     "Lưu lại nha", không hề hỏi gì.
3. Sinh prompt cảnh → giờ ra **3-5 cảnh × 4s** (trước là 2 cảnh × 6-8s).
   → Phải tạo nhiều clip Flow hơn: **5 clip thay vì 3** với kịch bản 65 từ.
   Nếu nặng tay quá, kéo thanh "Độ dài kịch bản" xuống ~45 từ → chỉ 3 clip.
4. Upload clip theo đúng thứ tự, kiểm số 1-2-3 ở khối "Bước 3 · Media Nền",
   sai thì sửa bằng mũi tên ↑↓.
5. Xuất video, đăng, **để Everyone**, bật nhãn AI, đặt ảnh bìa `_cover.jpg`.

### Sau 2 video, đọc kết quả

| Average watch time | Kết luận | Làm gì |
|---|---|---|
| **≥ 6-7s** | Lỗi là kỹ thuật, format sống được | Giữ nguyên quy trình tự động, tăng sản lượng lên 1-2 video/ngày |
| **vẫn 3-4s** | Format có vấn đề thật | Sang Bước 2 |

---

## BƯỚC 2 — Chỉ làm nếu Bước 1 thất bại: bỏ TTS, tự thu giọng

**Đổi đúng MỘT biến**, giữ nguyên mọi thứ khác (mascot, hình, phụ đề, nội dung).

### Vì sao là giọng, không phải hình

- Giọng TTS tiếng Việt lộ ra trong **chưa tới 1 giây** — khớp đúng mốc mất người xem
- Dữ liệu 2026: **78% người xem tin video có người thật hơn video AI**; tỉ lệ ưa
  nội dung AI **tụt còn 26%, từ 60% năm 2023**
- **"Faceless" không có nghĩa là "không giọng"** — phần lớn kênh faceless top dùng
  giọng thật
- Tốn 0 đồng, giữ nguyên toàn bộ pipeline hình và mascot Bống
- Giúp luôn phần chuyển đổi follow (đang 0) vì tạo kết nối người-với-người

### Vì sao KHÔNG gộp Bước 1 và Bước 2

Giá của chúng khác hẳn nhau. Bản vá kỹ thuật **miễn phí và tự động**. Thu giọng thật
thì **mất tự động hoá** — mỗi video phải ngồi thu, không còn bấm một nút ra video.
Gộp lại mà thành công thì không biết có thật sự cần thu giọng không, dễ tự trói mình
vào quy trình thủ công một cách vô ích.

---

## BƯỚC 3 — Chỉ làm nếu Bước 2 cũng thất bại

Lúc đó mới đổi format thật: **bỏ nhân vật anime AI**, thay bằng footage thật hoặc
kiểu chữ động trên nền tối giản. Đừng nhảy tới đây sớm — đã đầu tư nhiều vào mascot
Bống và chưa có bằng chứng nào cho thấy chính nó là thủ phạm.

---

## Việc lặt vặt còn treo

### Dựng profile cho "Bống Kể"
Tên đã chốt nhưng chưa dựng. Profile view mới 1-3%, 0 follower.
- Tên hiển thị `Bống Kể`, handle `@bongke` — **tự kiểm tra còn trống không**, lấy cả
  trên YouTube cho đồng bộ
- Ảnh đại diện: crop cận mặt từ ảnh tham chiếu Bống
- Bio gợi ý:
  > Sự thật tâm lý bạn đang hiểu sai 🧠
  > 1 sự thật mỗi ngày · 15 giây

### Nhạc nền
Đã tải sẵn 12 bài CC0 (6 mood × 2 bài) vào `audio_bg/`, tên đặt đúng chuẩn khớp mood.
- **Cần nghe thử** — tôi không nghe được, chỉ lọc được lỗi khách quan (im lặng,
  one-shot, trùng lặp). Bài nào chối tai thì xoá.
- Tải bù: `python -m core.engines.music_fetcher 3`
- File `alex-morgan-classical-royal-english-music-545533.mp3` không khớp mood nào nên
  chỉ được chọn ngẫu nhiên — đổi tên có tiền tố mood nếu muốn nó khớp đúng.

### Nếu định gắn nhạc trending TikTok
- Chỉ gắn được bằng **app điện thoại** (web không có "Add sound")
- Nhớ chọn "Không dùng nhạc" ở phần BGM trong app để tránh chồng 2 lớp nhạc
- Nhưng cân nhắc: thuật toán 2026 **ưu tiên original audio hơn nhạc mượn**; nhạc
  trending chỉ tăng reach trong sóng 1-3 tuần rồi hết

### Rủi ro cần biết cho Giai đoạn 2
YouTube từ 7/2025 có chính sách "inauthentic content" **cấm kiếm tiền** với nội dung
AI sản xuất hàng loạt theo khuôn. Kế hoạch đăng chéo YouTube Shorts lấy doanh thu
quảng cáo có thể vướng chính sách này — cần kiểm tra kỹ trước khi đầu tư vào nhánh đó.

---

## Nhắc lại: chỉ nhìn MỘT con số

**`Average watch time` (giây).** Hiện 2,77-4,18s.

View không thể tăng khi con số này còn 3-4 giây. Mọi thứ khác — like, bình luận,
follower, ảnh bìa, caption, hashtag — đều vô nghĩa cho tới khi giữ được người xem
quá giây thứ 6.
