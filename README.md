# 🎬 TikTok Video Kể Truyện Auto-Creator

Hệ thống tự động tạo video TikTok chuẩn Affiliate/Viral từ kịch bản text. Hệ thống đặc biệt tối ưu cho ngách **Video Đọc Truyện (Reddit Stories, Tâm Sự, Creepy Pastas)**.
Nhập kịch bản → Xuất một hoặc nhiều video MP4 hoàn chỉnh với Giọng đọc tiếng Việt (Cảm xúc) + Subtitle tịnh tâm + Ảnh bìa + Nhạc nền Lofi + Chia Part vòng lặp bằng AI.

**Chi phí API: $0/tháng** — Tất cả đều dùng công cụ miễn phí hoặc gói Free.

## ✨ Tính năng Viral Tích Hợp

- 🎙️ **Text-to-Speech**: Giọng đọc tiếng Việt mượt mà (nữ HoaiMy / nam NamMinh).
- 🔤 **Dynamic Subtitles**: Vẽ phụ đề động nhảy chữ từng từ theo giọng đọc. Hỗ trợ 4 phong cách (Ali Abdaal, Marker Box, MrBeast, Typewriter)
- 🖼️ **Auto Thumbnail**: Mỗi video xuất ra sẽ tự động kèm theo 1 ảnh bìa `_cover.jpg` giật tít câu đầu tiên phong cách tò mò.
- 🎶 **Auto BGM Mixing**: Tự động lặp lại nhạc lofi/piano trong folder `audio_bg/` và dìm âm lượng (ducking) xuống 10% bảo vệ giọng đọc.
- ✂️ **AI Auto-Splitter**: Khi bật `--auto-split`, não bộ AI Gemini sẽ tự phân tích cốt truyện và "bổ đôi" ngay khúc gay cấn nhất để nhử người xem sang Part 2.
- 📤 **Auto Upload TikTok**: Upload tự động qua tài khoản đã login Playwright đính kèm HashTags.
- 💻 **Cross-platform**: Chạy mượt trên Mac, Windows, Linux.

## 🚀 Cài đặt

1. Install dependencies
```bash
pip install -r requirements.txt
```
2. Cài trình giả lập duyệt Web Playwright (tùy chọn tải video TikTok tự động)
```bash
python -m playwright install chromium
```
3. Kết nối não bộ AI (Tuyệt mật)
Lấy API miễn phí tại Google AI Studio. Tạo file `.env` cùng thư mục code và khai báo:
```bash
GEMINI_API_KEY=mã_ai_miễn_phí_từ_google
```

## 📖 Hướng Dẫn Sử Dụng Tool (CLI)

### 1. Viết kịch bản
Tạo file `script.txt`. Cách tốt nhất là Plain text (văn xuôi). Công cụ tự động parse.

### 2. Tạo video Đọc Truyện Chuẩn (Tự Động)
Hệ thống mặc định thiết kế cho kênh chuyện: Chữ nằm dưới (`--position bottom`), Style tĩnh lặng (`--style 1`).
Chỉ cần Copy paste nhạc nền ngẫu nhiên vào thư mục `audio_bg/` và chạy lệnh ngắn nhất:
```bash
python main.py
```

### 3. Chia Phần Bằng AI Kéo View (Auto Split)
Nếu truyện cực dài, thay vì người xem lướt đi mất do ngán, hãy chia nhỏ video ra làm 2 phần tại nơi Hồi hộp nhất để kéo follow:
```bash
python main.py --auto-split
```
Hệ thống sẽ gọi tính toán AI, sau đó xuất ra `output/final_video_part1.mp4` và `output/final_video_part2.mp4` liên tục tự động!

### 4. Tùy chỉnh Khác
Đổi sang phong cách tin tức năng lượng cao:
```bash
python main.py --style 3 --position center --rate "+20%"
```
Vừa tạo video xong vừa Login TikTok Tự Đăng:
```bash
python main.py --upload --title "Creepypasta đêm mưa" --tags storiestiktok,reddit
```

## 🔧 Danh sách Thuộc Tính Tham Số (Options)

| Flag | Mặc định | Mô tả |
|---|---|---|
| `--script` | `script.txt` | File chứa kịch bản. |
| `--style` | `1` | 1: Ali (Tối giản), 2: Box, 3: MrBeast, 4: Typewriter. |
| `--position`| `bottom` | `center` (Giữa) hoặc `bottom` (Dưới chân). |
| `--auto-split`| Tắt | Bật để kích hoạt AI bổ luống video (cần GEMINI API). |
| `--voice` | `hoaimy` | Giọng `hoaimy` (nữ) / `namminh` (nam). |
| `--rate` | `+20%` | Tốc độ. VD: `+0%` (chuẩn), `+20%` (Nhanh xíu). |
| `--bg-dir` | `backgrounds/` | Thư mục chứa Background Satisfying Gameplay (mp4). |
| `--bgm-dir` | `audio_bg/` | Thư mục chứa nhạc nền Lofi / Creepy Sound (mp3/wav/ogg) |
| `--auto-bg` | Bật | Nếu thư mục video trống, tự động lên Pexels tải (Khuyên tắt). |
| `--upload` | Tắt | Tự động mở Playwright tải lên TikTok lúc Render xong. |

## 📄 License
MIT License
Dự án được xây dựng mô phỏng luồng Affiliate Automation Story Format.
