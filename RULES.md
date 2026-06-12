# TIKTOK VIDEO CREATION RULES

Tài liệu này tổng hợp các quy tắc để hệ thống tạo video TikTok đúng định hướng kênh.
Định hướng kênh chi tiết và căn cứ nghiên cứu: xem `channel_strategy.md`. Kế hoạch sửa đổi dự án: xem `docs/PLAN_2026.md`.

## 1. Nội dung và Chủ đề (Content & Theme)
- **Ngách duy nhất**: Đồ gia dụng / nhà bếp thông minh / mẹo dọn dẹp. KHÔNG trộn ngách khác.
- **Hai loại video** trên cùng một kênh:
    - **Video sản phẩm (~70%)**: 15–20 giây, cấu trúc Hook nỗi đau (2-3s) → Demo sản phẩm (10-14s) → CTA giỏ hàng (2-3s). Gắn giỏ hàng TikTok Shop.
    - **Video mẹo vặt (~30%)**: 15–25 giây, thuần giá trị, không bán gì, kết bằng kêu gọi lưu video/câu hỏi. Mục đích kéo view + follow.
- **Giọng đọc**: Ưu tiên **TikTok TTS giọng Việt** (tiktok_nu_1 / tiktok_nam_1) vì tự nhiên, hợp viral — cần `TIKTOK_SESSION_ID` trong `.env`. Dự phòng: FPT banmai (tự nhiên) hoặc Edge (hoaimy/namminh). Tốc độ +20%. Video dùng giọng AI phải **bật nhãn AI-generated content** khi đăng.
- **Trung thực**: Chỉ nói công dụng thật của sản phẩm. Phóng đại/bịa tính năng = vi phạm chính sách misleading → đóng băng hoa hồng tới 90 ngày.

## 2. Hình ảnh (Visuals)
- **Video sản phẩm (gắn giỏ hàng)**: BẮT BUỘC footage thật tự quay từ hàng mẫu (tay thao tác + sản phẩm + bối cảnh thật, có chuyển động camera, đủ sáng). CẤM ảnh tĩnh, slideshow, footage loop, stock ngẫu nhiên, visual AI thuần.
- **Video mẹo vặt (không gắn giỏ)**: được dùng stock Pexels "satisfying" (nấu ăn, dọn dẹp) hoặc visual AI như cũ.
- **Quy tắc duy nhất (Uniqueness)**: video nền stock không lặp lại giữa các video; theo dõi qua `used_backgrounds.json`; nối nhiều video khác nhau nếu ngắn hơn audio, không loop 1 file.
- **Subtitle**: phong cách Ali Abdaal hoặc MrBeast, màu nổi bật (Vàng/Trắng), viền đen. Vị trí bottom để không che sản phẩm đang demo.
- **Nhạc nền (BGM)**: nhạc nhẹ upbeat/chill, volume thấp (~0.2) để không át giọng đọc.

## 3. SEO và Phân phối (Distribution)
- **Caption**: nêu nỗi đau + giải pháp, không giật tít sai sự thật.
- **Hashtag chuẩn ngách**: #dogiadung #meovat #nhabep #tiktokshop #xuhuong #fyp.
- **Vị trí**: Hà Nội, TP. HCM.
- **Khung giờ vàng**: 11h-13h, 18h-21h.

## 4. Quy tắc vận hành hệ thống (Operational Rules)
- **Pipeline video sản phẩm**: Footage thật (input) → Script Gemini → TTS → Render (ghép footage + caption + CTA).
- **Pipeline video mẹo vặt**: Script Gemini → TTS → Tìm BG stock → Render.
- **Không tự động upload**: đăng thủ công, tần suất như người thật (1-2 video/ngày). Mass-upload tự động = rủi ro khóa kênh + đóng băng hoa hồng.
- **Hàng mẫu**: xin qua chương trình Mẫu miễn phí của TikTok Shop; footage/ảnh seller cung cấp chỉ dùng cho chính seller đó.

---
*Cập nhật lần cuối: 2026-06-12 — chuyển định hướng từ storytelling tâm lý sang đồ gia dụng + affiliate (xem channel_strategy.md)*
