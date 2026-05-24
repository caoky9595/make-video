# Kế hoạch: Tối ưu hóa Hệ thống Tạo Video Tự động (Project Optimization)

## Research Findings
- **used_backgrounds.json**: Chứa danh sách mảng JSON các Pexels IDs của các video nền đã được dùng. Hiện tại không được nạp ở đâu trong code tìm kiếm hoặc render.
- **bg_finder.py**: 
  - Đang tìm kiếm video Pexels & Pixabay dựa trên keyword tạo bởi Gemini.
  - Có hàm `download_video` dùng requests để stream tải mp4.
  - Có hàm sinh ảnh AI qua Pollinations.ai.
- **video_maker.py**:
  - Thực hiện render video dọc 1080x1920 dùng MoviePy.
  - Sử dụng Pillow để vẽ chữ subtitle (Ali, Marker Box, MrBeast, Typewriter, Soft Aesthetic).
  - Có logic Multi-scene chia nhỏ duration theo từng dòng sub để phủ video nền.
- **generate_music_pack.py**:
  - Tạo ra 40 track nhạc nền wav cục bộ (`bgm_XX_mood_bpm.wav`) với các mood: sad_piano_emotional, dark_suspense_cinematic, happy_upbeat, lofi_chill, inspiring_motivational, ambient_soft_story, romantic_warm, epic_trailer_drive.

## Assumptions
- Cần hỗ trợ song song cả 2 chủ đề/phong cách:
  1. Kịch tính/Storytelling (Gia đình, Đời sống) -> Background dạng "Oddly Satisfying" (nấu ăn, dọn dẹp, cát động học, làm bánh...).
  2. Sự thật/Triết lý (Psychology Facts, Stoicism) -> Background dạng Cinematic, Lofi, Dark Academia.
  Hệ thống sẽ tự nhận diện bằng cách phân tích kịch bản bằng Gemini hoặc kiểm tra từ khóa Tiếng Việt trong kịch bản để gợi ý chủ đề phù hợp nhất.
- Khi dọn dẹp `audio_bg/`, chỉ xóa các bản nhạc tải online tự động (bắt đầu bằng `auto_`) và giữ lại bộ package nhạc tổng hợp có sẵn (`bgm_`).

## Implementation Plan
**Files sẽ thay đổi**:

### 1. [MODIFY] [bg_finder.py](file:///home/ky/Desktop/make-video/bg_finder.py)
- Nạp danh sách IDs đã dùng từ `used_backgrounds.json` (nếu không tồn tại thì khởi tạo danh sách rỗng).
- Trong `search_pexels_videos`, lọc bỏ các video có ID đã nằm trong danh sách đã dùng.
- Thiết lập bộ lọc chất lượng cao trong `download_video`: Chỉ chọn các video có độ phân giải chiều cao tối thiểu 1080p hoặc HD (720p vertical trở lên), loại bỏ hoàn toàn các video SD/480p mờ.
- Trong `generate_visual_keywords_with_gemini`, viết lại Prompt để Gemini phân tích sâu kịch bản và phân loại thành 3 ngách thịnh hành để xuất ra các từ khóa tương ứng:
  - *Storytelling ASMR*: Oddly satisfying, sand ASMR, soap cutting, kinetic sand, satisfying cleaning.
  - *Philosophy & Stoic Lofi*: Ancient statue shadow, dark library candle light, cozy rain window, moody lofi room.
  - *Business & Motivation*: Luxury desk setup, keyboard typing close up, clean office space, luxury city timelapse.
- Trong `extract_keywords`, bổ sung mapping các từ khóa Storytelling tiếng Việt sang Oddly Satisfying tiếng Anh.

### 2. [MODIFY] [video_maker.py](file:///home/ky/Desktop/make-video/video_maker.py)
- Lưu vết các video IDs thực tế được sử dụng sau khi render thành công:
  - Parse ID từ tên file video nền được ghép vào (ví dụ `pexels_12345.mp4` -> ID `12345`).
  - Đọc `used_backgrounds.json`, cập nhật thêm các IDs này và lưu lại file.
- Khắc phục lỗi loop lặp lại video:
  - Khi một clip nền được chọn ngắn hơn thời gian của cảnh (scene) hoặc kịch bản, thay vì lặp lại (loop) clip đó, ta sẽ ghép nối (concatenate) clip đó với các clip nền khác chưa sử dụng từ danh sách visual_sources tải về.
- Nâng cấp độ thẩm mỹ cao cấp (Aesthetic Dimming Overlay):
  - Trước khi ghép lớp phụ đề chuyển động, chèn một lớp phủ đen bán trong suốt `ColorClip(color=(0,0,0)).set_opacity(0.35)` đè lên trên video nền. Điều này làm tối nhẹ hậu cảnh giúp chữ phụ đề hiển thị sắc nét, chuyên nghiệp và có độ tương phản cực kỳ tốt.

### 3. [MODIFY] [app.py](file:///home/ky/Desktop/make-video/app.py)
- Cập nhật logic dọn dẹp tài nguyên cũ khi start pipeline:
  - Xóa các file video nền trong `backgrounds/` (giữ nguyên).
  - Xóa các file nhạc online tự động tải về trước đó trong `audio_bg/` (những file có tiền tố `auto_`).
- Tích hợp tải nhạc online tự động:
  - Khi start pipeline, nếu `music_mode` là tự động, đầu tiên gọi `resolve_music_for_script` trong `music_finder.py` để tải BGM mới từ online. Nếu thất bại hoặc không cấu hình API, fallback về gọi `pick_local_music_for_script` để chọn nhạc có sẵn trong `audio_bg/`.

## Rủi ro & Cách khắc phục
- **Hết tài nguyên video độc nhất**: Pexels search có thể trả về ít kết quả. 
  - *Khắc phục*: Tăng số lượng trang tìm kiếm hoặc chuyển sang fallback ảnh AI sinh từ Pollinations.ai (luôn độc nhất nhờ seed ngẫu nhiên).
- **Mất file used_backgrounds.json hoặc lỗi định dạng**: 
  - *Khắc phục*: Sử dụng try-except khi đọc/ghi file này, fallback về danh sách rỗng nếu lỗi.

## Next step
→ Chuyển sang **Coder** thực thi kế hoạch chi tiết.
