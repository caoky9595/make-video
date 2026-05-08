# 🎬 VideoMaker Pro - AI Video Creator

Hệ thống tạo video TikTok tự động với giao diện web premium. Tích hợp AI thông minh để biến ý tưởng thành video thành phẩm chỉ trong vài phút.

### ✨ Tính năng mới (v2.0)
*   **Giao diện 3 cột chuyên nghiệp:** Trải nghiệm Studio thực thụ với Script - Settings - Preview trên cùng một màn hình.
*   **Thư viện Video (Dashboard):** Quản lý video dưới dạng lưới (Grid) với Thumbnail trực quan.
*   **Hệ thống Quản lý Output:** Hỗ trợ xem trước video ngay trên web, chọn nhiều file, xóa hàng loạt.
*   **AI Script Generator:** Tích hợp Gemini Flash để tạo kịch bản từ ý tưởng chỉ trong 5 giây.
*   **Studio Visual Mode:** Upload ảnh riêng và chọn 1 trong 3 chế độ nền: Pexels mặc định, mix Pexels + ảnh upload, hoặc chỉ ảnh upload.
*   **Music Library trong Studio:** Upload nhạc nhiều định dạng, chọn file nhạc nền và chọn mốc giây bắt đầu để cắt đoạn chèn vào video.
*   **BGM Volume Control:** Tinh chỉnh âm lượng nhạc nền trực tiếp trong Studio trước khi render.
*   **AI Local Music Picker:** AI tự chọn nhạc phù hợp từ thư viện local `audio_bg/` (không cần gọi thư viện online).
*   **Persistence:** Ghi nhớ Tab làm việc ngay cả khi tải lại trang (F5).
*   **Unique Output:** Tự động đặt tên video theo thời gian, không lo ghi đè.

## 🚀 Khởi chạy Web App

```bash
# Kích hoạt môi trường
source .venv/bin/activate

# Chạy web server
python app.py

# → Mở http://localhost:5000
```

## 💻 Chạy CLI (không cần web)

```bash
python main.py                          # Tạo video từ script.txt
python main.py --voice banmai           # Dùng giọng FPT.AI Ban Mai
python main.py --upload                 # Tạo + upload TikTok
python main.py --list-voices            # Xem danh sách giọng đọc
python main.py --auto-split             # AI cắt phần tự động
```

## 🎙️ Giọng đọc hỗ trợ (9 giọng)

| ID | Tên | Giới tính | Vùng miền | Engine |
|---|---|---|---|---|
| `hoaimy` | Hoài My | Nữ | Bắc | Edge-TTS (Free) |
| `namminh` | Nam Minh | Nam | Bắc | Edge-TTS (Free) |
| `banmai` | Ban Mai | Nữ | Bắc | FPT.AI |
| `thuminh` | Thu Minh | Nữ | Bắc | FPT.AI |
| `leminh` | Lê Minh | Nam | Bắc | FPT.AI |
| `myan` | Mỹ An | Nữ | Trung | FPT.AI |
| `giahuy` | Gia Huy | Nam | Trung | FPT.AI |
| `lannhi` | Lan Nhi | Nữ | Nam | FPT.AI |
| `linhsan` | Linh San | Nữ | Nam | FPT.AI |

## 🌐 API Endpoints

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/api/voices` | Danh sách giọng đọc |
| GET | `/api/stats` | Thống kê tổng quan |
| GET | `/api/script/load` | Đọc kịch bản |
| POST | `/api/script/save` | Lưu kịch bản |
| POST | `/api/tts/preview` | Preview giọng đọc |
| POST | `/api/pipeline/start` | Bắt đầu tạo video |
| GET | `/api/pipeline/status` | Trạng thái pipeline |
| GET | `/api/backgrounds` | Video nền có sẵn |
| GET | `/api/images` | Danh sách ảnh đã upload |
| POST | `/api/images/upload` | Upload một hoặc nhiều ảnh |
| POST | `/api/images/delete` | Xóa ảnh đã upload |
| GET | `/api/music` | Danh sách thư viện nhạc |
| POST | `/api/music/upload` | Upload một hoặc nhiều file nhạc |
| POST | `/api/music/delete` | Xóa file nhạc đã upload |
| GET | `/api/bgm` | Nhạc nền có sẵn |
| GET | `/api/outputs` | Danh sách video thành phẩm |
| POST | `/api/outputs/delete` | Xóa một hoặc nhiều video |
| POST | `/api/outputs/delete_all` | Dọn dẹp sạch thư viện video |

## 📁 Cấu trúc dự án

```
play/
├── app.py              # Flask web server + API
├── main.py             # CLI pipeline
├── tts.py              # Text-to-Speech (Edge + FPT.AI)
├── video_maker.py      # Video renderer
├── bg_finder.py        # Tìm video nền Pexels
├── uploader.py         # Upload TikTok
├── ai_splitter.py      # AI cắt phần (Gemini)
├── webapp/             # Giao diện web SPA
│   ├── index.html      # Layout chính (Tailwind CSS + Glassmorphism)
│   └── app.js          # Logic điều hướng, API & UI
├── script.txt          # Kịch bản mẫu
├── backgrounds/        # Video nền
├── audio_bg/           # Nhạc nền
├── output/             # Video đã xuất
└── .env                # API keys
```

## ⚙️ Cài đặt

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Thêm API keys
```

Studio hỗ trợ nhập thời điểm bắt đầu nhạc theo `mm:ss` (ví dụ `01:30`) hoặc `hh:mm:ss`.

