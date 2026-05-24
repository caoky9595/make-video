# TIKTOK VIDEO CREATION RULES

Tài liệu này tổng hợp các yêu cầu và quy tắc quan trọng để hệ thống tạo video TikTok hoạt động đúng ý người dùng.

## 1. Nội dung và Chủ đề (Content & Theme)
- **Chủ đề chính**: Storytelling (kể chuyện) tập trung vào phụ nữ, đời sống, phát triển bản thân, kịch tính gia đình.
- **Phong cách kể**: Kịch tính, có cliffhanger (cao trào ở cuối mỗi phần) để giữ chân người xem và tạo sự tò mò cho phần tiếp theo.
- **Giọng đọc**: Ưu tiên giọng nữ (HoaiMy) hoặc giọng nam (NamMinh) tùy theo nhân vật, tốc độ đọc nhanh (+20%) để tăng nhịp điệu.

## 2. Hình ảnh và Hiệu ứng (Visuals & FX)
- **Video nền (Background)**: Sử dụng video "Oddly Satisfying" (nấu ăn, dọn dẹp, làm bánh, cát động học...) để tăng tỉ lệ giữ chân người xem.
- **Quy tắc duy nhất (Uniqueness)**: Mỗi video mới **không được lặp lại** video nền đã sử dụng ở bất kỳ phần nào trước đó.
- **Tươi mới (Freshness)**: Trước khi tạo video mới, hệ thống sẽ **xóa sạch** các video nền cũ trong thư mục `backgrounds/` và nhạc nền trong `audio_bg/` để đảm bảo không dùng lại file cũ.
- **Nhạc nền (BGM)**: Mỗi lần chạy sẽ tự động tìm và tải nhạc nền (BGM) mới phù hợp với tâm trạng (lofi, chill, drama).
- **Độ dài video nền**: 
    - Tuyệt đối không lặp lại (loop) cùng một video trong một clip.
    - Phải tải đủ số lượng video khác nhau để tổng thời lượng lớn hơn thời lượng audio.
    - Nếu video nền ngắn hơn audio, phải **nối (concatenate) nhiều video khác nhau** để phủ kín thời lượng audio.
- **Subtitle**: 
    - Phong cách hiện đại (Ali Abdaal hoặc MrBeast).
    - Màu chữ nổi bật (Vàng/Trắng trên nền tối), có viền đen để dễ đọc.

## 3. SEO và Phân phối (Distribution)
- **Tiêu đề (Caption)**: Phải thu hút, tóm tắt được cao trào của video.
- **Hashtag**: Luôn kèm theo bộ hashtag chuẩn (#tamly #giadinh #phunu #storytelling #xuhuong #fyp).
- **Vị trí (Location)**: Ưu tiên đặt tại các thành phố lớn (Hà Nội, TP. HCM) để tiếp cận tệp người dùng năng động.

## 4. Quy tắc vận hành hệ thống (Operational Rules)
- **Pipeline tự động**: TTS -> Tìm BG -> Render Video.
- **Không tự động upload**: Tải lên thủ công để tránh bị TikTok đánh dấu là bot.
- **Lưu vết**: Theo dõi các video nền đã dùng trong `used_backgrounds.json` để đảm bảo tính duy nhất.

---
*Cập nhật lần cuối: 2026-04-21*
