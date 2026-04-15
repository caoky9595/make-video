# 🎬 TikTok Video Auto-Creator

Hệ thống tự động tạo video TikTok từ kịch bản text. Nhập kịch bản → Xuất video MP4 hoàn chỉnh với giọng đọc tiếng Việt + subtitle + video nền.

**Chi phí: $0/tháng** — Tất cả đều dùng công cụ miễn phí.

## ✨ Tính năng

- 🎙️ **Text-to-Speech**: Giọng đọc tiếng Việt tự nhiên (nữ HoaiMy / nam NamMinh)
- 📝 **Smart Script Parser**: Tự tách lời thoại từ kịch bản có timestamp, chú thích
- 🎬 **Auto Video Render**: Ghép audio + subtitle + video nền → MP4 dọc 1080x1920
- 🔍 **Auto Background**: Tự tìm + tải video nền phù hợp từ Pexels
- 📤 **Auto Upload TikTok**: Upload tự động lên TikTok qua Playwright
- ⚡ **Tuỳ chỉnh**: Tốc độ đọc, giọng đọc, hashtag, tiêu đề
- 💻 **Cross-platform**: Chạy trên Mac, Windows, Linux

## 🚀 Cài đặt

```bash
# Clone repo
git clone https://github.com/YOUR_USERNAME/tiktok-auto-creator.git
cd tiktok-auto-creator

# Cài dependencies
pip install -r requirements.txt

# (Tuỳ chọn) Cài Playwright để dùng auto-upload
python -m playwright install chromium
```

## 📖 Cách dùng

### 1. Viết kịch bản

Tạo file `script.txt` theo 1 trong 2 format:

**Format 1 — Có ngoặc kép (khuyên dùng):**
```
0s - 3s (Hook): (quay mặt) "Tại sao các ông lớn chi hàng tỷ để mua tên miền?"
3s - 15s (Nội dung): "Ví dụ như cái tên này..."
```
→ Tool tự tách phần trong `"..."` để đọc, bỏ hết chú thích.

**Format 2 — Plain text:**
```
Tại sao các ông lớn chi hàng tỷ để mua tên miền?
Ví dụ như cái tên này...
```

### 2. Tạo video

```bash
# Tạo video (mặc định: giọng nữ, tốc độ +20%)
python main.py

# Giọng nam
python main.py --voice namminh

# Tốc độ nhanh hơn
python main.py --rate "+30%"

# Chỉ định file kịch bản khác
python main.py --script my_idea.txt
```

### 3. Upload lên TikTok

```bash
# Đăng nhập lần đầu (quét QR)
python main.py --login

# Tạo + upload tự động
python main.py --upload --title "Mẹo hay" --tags fyp,viral,affiliate
```

## 📁 Cấu trúc dự án

```
├── main.py            # Entry point (CLI)
├── tts.py             # Text-to-Speech + Script Parser
├── video_maker.py     # Video render engine
├── bg_finder.py       # Auto background finder (Pexels)
├── uploader.py        # TikTok auto-upload (Playwright)
├── requirements.txt   # Dependencies
├── script.txt         # File kịch bản
├── backgrounds/       # Video nền (tự tải hoặc bỏ tay)
├── temp/              # File tạm
└── output/            # Video thành phẩm
```

## 🔧 Tuỳ chọn CLI

| Flag | Mặc định | Mô tả |
|---|---|---|
| `--script` | `script.txt` | File kịch bản |
| `--voice` | `hoaimy` | Giọng đọc: `hoaimy` (nữ) / `namminh` (nam) |
| `--rate` | `+20%` | Tốc độ đọc |
| `--output` | `output/final_video.mp4` | File đầu ra |
| `--bg-dir` | `backgrounds/` | Thư mục video nền |
| `--auto-bg` | Bật | Tự tải video nền từ Pexels |
| `--no-auto-bg` | — | Tắt auto background |
| `--upload` | — | Upload lên TikTok sau khi render |
| `--login` | — | Đăng nhập TikTok |
| `--title` | — | Tiêu đề video TikTok |
| `--tags` | `fyp,viral,...` | Hashtag |

## 📋 Yêu cầu

- Python 3.8+
- FFmpeg (thường đã có sẵn trên macOS/Linux)
- Pexels API Key (miễn phí) — cho tính năng auto background

## 📄 License

MIT
