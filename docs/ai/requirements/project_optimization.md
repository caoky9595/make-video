# Phân tích Yêu cầu: Tối ưu hóa Hệ thống Tạo Video Tự động (Project Optimization)

## 1. Context & Objectives
Mục tiêu là phân tích các yêu cầu hiện tại của dự án VideoMaker Pro (make-video), chỉ ra các điểm mâu thuẫn, các lỗi logic, và đề xuất giải pháp tối ưu hóa đồng bộ hệ thống để đáp ứng đúng ý người dùng.

## 2. Gaps & Conflict Analysis
Qua nghiên cứu codebase và các tài liệu định hướng (`RULES.md`, `channel_strategy.md`), hệ thống hiện tại đang gặp các điểm mâu thuẫn và lỗ hổng lớn sau:

### 2.1. Mâu thuẫn Định hướng Chủ đề & Tài nguyên nền (Theme & Visuals)
- **RULES.md**: Chủ đề chính là **Storytelling (kể chuyện)** về đời sống, phụ nữ, gia đình. Yêu cầu video nền phải là **Oddly Satisfying** (nấu ăn, dọn dẹp, cát động học...).
- **channel_strategy.md**: Chủ đề chính là **Sự thật tâm lý học (Psychology Facts)** & Triết lý sống (Stoicism). Yêu cầu video nền là **Lofi, Dark Academia, Cinematic**.
- **Code hiện tại**: `bg_finder.py` chỉ định dạng prompt sinh từ khóa Gemini thiên về "high-end photography, minimal, ancient greek statue..." (theo hướng Stoicism) và fallback keywords cũng chỉ có cinematic landscape, cyberpunk city... Không hề có cơ chế chuyển đổi hoặc chọn chủ đề "Oddly Satisfying".

### 2.2. Lỗi Logic về Tính duy nhất (Uniqueness) & Lưu vết (used_backgrounds.json)
- **Yêu cầu (RULES.md)**: Theo dõi các video nền đã dùng trong `used_backgrounds.json` để đảm bảo tính duy nhất (mỗi video không được lặp lại ở bất kỳ phần nào trước đó).
- **Code hiện tại**: 
  - `used_backgrounds.json` tồn tại dưới dạng một mảng các Pexels IDs nhưng **không có bất kỳ dòng code nào** trong `bg_finder.py` hay `video_maker.py` đọc file này để lọc kết quả tìm kiếm từ Pexels.
  - Khi render thành công, hệ thống cũng **không ghi nhận/append** các video ID đã sử dụng vào `used_backgrounds.json`. Điều này dẫn đến nguy cơ lặp lại video cực kỳ cao.

### 2.3. Lỗi Lặp lại Video nền (Looping) trong cùng một Clip
- **Yêu cầu (RULES.md)**: Tuyệt đối không loop cùng một video nền trong một clip. Nếu video nền ngắn hơn audio, phải nối nhiều video nền khác nhau.
- **Code hiện tại**:
  - Trong `video_maker.py` (dòng 513), khi chia đều visual cho các câu thoại, nếu số lượng file visual ít hơn số câu thoại, hệ thống sẽ thực hiện toán tử modulo: `asset_p = visual_sources[i % len(visual_sources)]`.
  - Nếu chỉ tải được 1 video hoặc thư mục chỉ có 1 video, video đó sẽ bị lặp lại nhiều lần trong clip, vi phạm trực tiếp quy tắc chống loop.

### 2.4. Thiếu cơ chế Xóa nhạc nền cũ & Tải nhạc nền tự động (BGM Freshness & Resolving)
- **Yêu cầu (RULES.md)**: Trước khi tạo video mới, hệ thống phải xóa sạch nhạc nền cũ trong `audio_bg/` và tự động tìm/tải nhạc nền mới phù hợp.
- **Code hiện tại**:
  - `app.py` chỉ thực hiện xóa các video nền cũ bắt đầu bằng `ai_image_`, `pexels_`, `pixabay_` trong thư mục `backgrounds/`. Nó **không hề xóa** các file trong `audio_bg/`.
  - Thêm nữa, `app.py` không hề gọi hàm `resolve_music_for_script` trong `music_finder.py` để tải nhạc nền tự động từ API online. Nó chỉ dùng nhạc local có sẵn. Nếu xóa sạch `audio_bg/` mà không tải mới, render sẽ lỗi vì không tìm thấy nhạc.

### 2.5. Mâu thuẫn Cơ chế Upload (Manual vs 100% Automation)
- **RULES.md**: Không tự động upload (Manual upload) để tránh bị TikTok đánh dấu bot.
- **channel_strategy.md**: Tự động upload hoàn toàn (100% Automation) sử dụng trình duyệt ẩn danh/anti-detect (`DrissionPage`).
- **Code hiện tại**: Có đầy đủ cả 2 cơ chế (dashboard hỗ trợ mở trình duyệt cho user tự đăng, hoặc chạy queue upload tự động, hoặc lên lịch tự động đăng qua scheduler). Cần làm rõ và đồng bộ cấu hình tùy theo mục đích sử dụng.

### 2.6. Tối ưu hóa tính thẩm mỹ và chất lượng của Video nền (Premium Aesthetics & Quality)
- **Yêu cầu của người dùng**: Phần sinh video background phải thật xịn, thu hút người xem.
- **Hiện tại**:
  - Không có lớp phủ (overlay) tối làm nổi bật chữ, dẫn đến chữ bị chìm vào nền video sáng.
  - API Pexels có thể trả về video chất lượng thấp (SD/480p) làm mờ/vỡ hình trên màn hình điện thoại lớn.
  - Phân loại từ khóa còn chung chung, chưa chia rõ các ngách (niche) thịnh hành trên TikTok.
- **Giải pháp**:
  - **Dimming Overlay**: Thêm lớp phủ đen bán trong suốt (`set_opacity(0.35)`) nằm trên background để tăng độ tương phản giúp phụ đề MrBeast nổi bật và dễ đọc hơn.
  - **High-Res Enforcement**: Thiết lập filter chỉ tải video Pexels có chiều cao tối thiểu 1920 (Vertical Full HD) hoặc tối thiểu 1080p, loại bỏ các file SD.
  - **Dynamic Niche Keyword Generator**: Nâng cấp prompt Gemini trong `bg_finder.py` để phân loại kịch bản thành 3 ngách rõ rệt:
    1. *Storytelling ASMR* (Oddly satisfying, Sand ASMR, Soap cutting...)
    2. *Philosophy & Stoic Lofi* (Ancient statue shadow, Dark academia library, Rain window...)
    3. *Business & Money Motivation* (Luxury desk setup, Mechanical keyboard typing, Cinematic city timelapse...)

---

## 3. Scope of Optimization
Các thành phần cần được tối ưu hóa bao gồm:
1. `bg_finder.py`: 
   - Đọc và lọc các Pexels IDs đã có trong `used_backgrounds.json`.
   - Nâng cấp prompt Gemini phân loại ngách nội dung (Niche-based) và tạo từ khóa chất lượng cao.
   - Lọc độ phân giải tối thiểu (Full HD 1080p vertical) để đảm bảo hình ảnh sắc nét.
2. `video_maker.py`:
   - Ghi nhận các video IDs đã được sử dụng thành công vào `used_backgrounds.json`.
   - Đảm bảo ghép nối các clip nền khác nhau để tránh lặp lại (loop) cùng một clip nếu tổng độ dài không đủ.
   - Thêm lớp phủ tối `ColorClip` với độ mờ 35% trên nền video trước khi vẽ phụ đề để tạo chiều sâu điện ảnh.
3. `app.py` & `music_finder.py`:
   - Thực hiện dọn dẹp các bản nhạc nền tải tự động cũ trong `audio_bg/` khi bắt đầu pipeline.
   - Tích hợp gọi `resolve_music_for_script` để tải BGM tự động từ online nếu được cấu hình.

