# 🎬 VideoMaker — Tạo video TikTok faceless tự động

Công cụ tạo video dọc 1080x1920 cho TikTok từ kịch bản: AI sinh kịch bản → giọng đọc AI → tự tìm video nền → render phụ đề động.

**Định hướng kênh:** ngách Mẹo Vặt Nhà Bếp & Gia Đình, faceless, xây follower rồi làm affiliate TikTok Shop. Chi tiết: [channel_strategy.md](channel_strategy.md), [RULES.md](RULES.md), [docs/PLAN_2026.md](docs/PLAN_2026.md).

> Không có chức năng tự động upload — đăng thủ công để an toàn với chính sách TikTok (xem RULES.md).

---

## ✨ Tính năng

- **AI sinh kịch bản (Gemini):** 2 chế độ — Mẹo vặt (kéo view/follow) và Affiliate (bán hàng, giai đoạn sau).
- **Giọng đọc AI:** TikTok TTS giọng Việt (tự nhiên, hợp viral), và FPT.AI.
- **Phụ đề động:** highlight theo từng từ (word-level), 5 style (Ali / Marker / MrBeast / Typewriter / Affiliate).
- **Video nền tự động:** Pexels hoặc ảnh AI (Pollinations), tự ghép nhiều clip, không lặp lại.
- **Render tăng tốc bằng iGPU:** tự dùng VAAPI/QuickSync nếu máy hỗ trợ, fallback libx264.
- **Web dashboard:** React + Vite, editor kịch bản + thư viện video + preview.

---

## 🚀 Cài đặt & chạy

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Cấu hình .env:
#   GEMINI_API_KEY=...            (sinh kịch bản)
#   TIKTOK_SESSION_ID=...         (giọng TikTok TTS — lấy từ cookie sessionid khi đăng nhập tiktok.com)
#   PEXELS_API_KEY=...            (video nền)

# Web app:
python app.py            # → http://localhost:5000

# Hoặc CLI:
python main.py --script script.txt --voice tiktok_nu_1
```

### Lấy TIKTOK_SESSION_ID
Đăng nhập tiktok.com trên trình duyệt → F12 (DevTools) → Application → Cookies → copy giá trị `sessionid` → dán vào `.env`.

---

## 🎬 Cách làm một video (giai đoạn 1: mẹo vặt, faceless)

> Bạn KHÔNG cần tự quay hay tự tìm video nền. Hệ thống tự lo: Gemini đọc kịch bản → rút từ khóa → tải clip nền miễn phí bản quyền từ Pexels (tự ghép nhiều clip cho đủ độ dài), hoặc sinh ảnh AI (Pollinations). Vì video mẹo vặt không gắn giỏ hàng nên dùng nền stock là hợp lệ và an toàn chính sách.

### Bằng giao diện web
1. `python app.py` → mở http://localhost:5000 → vào **Studio Mẹo Vặt**.
2. Gõ ý tưởng (vd "mẹo bảo quản hành lá") → bấm AI sinh kịch bản (Gemini viết theo công thức hook → mẹo → kêu gọi lưu). Hoặc tự gõ kịch bản.
3. Chọn giọng (mặc định **TikTok Nữ**), phong cách phụ đề (**MrBeast** — chữ to, viền đậm, highlight vàng).
4. Bấm **Bắt đầu sản xuất** → chờ ~20-30 giây.
5. Video hiện ở thư viện (Bảng điều khiển) → xem trước / tải về.

### Bằng dòng lệnh
```bash
python main.py --script script.txt --voice tiktok_nu_1
# → file trong output/
```

### Sau khi có video — đăng TikTok thủ công
Hệ thống cố tình KHÔNG tự upload (an toàn chính sách). Tải video về rồi tự đăng, nhớ:
1. **Bật nhãn "Nội dung do AI tạo"** (vì dùng giọng AI) — bật rồi không bị bóp reach.
2. **Gắn nhạc đang trend ngay trong app TikTok** lúc đăng (nhạc nền trong video chỉ là nền nhỏ; trending sound mới giúp lên xu hướng).
3. **Caption + hashtag:** câu gợi tò mò + `#meovat #meobep #nhabep #xuhuong #fyp`.

### Nhịp đăng
1-2 video/ngày, khung giờ 11-13h hoặc 18-21h. Hook 2 giây đầu là quyết định. Kênh mới cần khối lượng để thuật toán tìm ra video trúng — đừng nản với 10-20 video đầu. Chi tiết chiến lược: [channel_strategy.md](channel_strategy.md).

---

## 🎙️ Giọng đọc

| Engine | Giọng | Ghi chú |
|---|---|---|
| **TikTok TTS** | tiktok_nu_1, tiktok_nu_2, tiktok_nam_1, tiktok_nam_2 | Giọng Việt tự nhiên, hợp viral — cần `TIKTOK_SESSION_ID` |
| **FPT.AI** | banmai, thuminh, leminh, myan, giahuy, lannhi, linhsan | Giọng Việt tự nhiên, đa vùng miền, phát triển thương hiệu tốt |

---

## 📁 Kiến trúc

```
app.py                  # Web server + API
main.py                 # CLI tạo video từ kịch bản
core/
├── engines/
│   ├── tts.py          # TTS đa engine + sinh SRT/word-timing
│   ├── tiktok_tts.py   # TikTok TTS (giọng Việt)
│   ├── video_maker.py  # Render engine (PIL + FFmpeg, HW encode)
│   ├── bg_finder.py    # Tìm video nền Pexels theo nội dung
│   ├── ai_visuals.py   # Sinh ảnh AI (Pollinations)
│   └── music_finder.py # Chọn nhạc nền
├── data/               # Models + SQLite jobs
└── utils/              # Logger
frontend/               # React + Vite SPA
```
