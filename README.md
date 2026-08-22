# 🎬 VideoMaker — Tạo video TikTok faceless

Công cụ tạo video dọc 1080x1920 cho TikTok từ kịch bản: AI sinh kịch bản → giọng đọc AI → video nền (clip Google Flow/Veo bạn tự tạo) → render phụ đề động.

**Định hướng kênh:** ngách Sự Thật Thú Vị & Tâm Lý Cuộc Sống, faceless, xây follower rồi làm affiliate TikTok Shop. Chi tiết: [channel_strategy.md](channel_strategy.md), [RULES.md](RULES.md).

> Không có chức năng tự động upload — đăng thủ công để an toàn với chính sách TikTok (xem RULES.md).

---

## ✨ Tính năng

- **AI sinh kịch bản (Gemini, tự chuyển Groq khi hết quota):** 2 chế độ — Sự thật/Tâm lý (kéo view/follow) và Affiliate (bán hàng, giai đoạn sau).
- **Ngân hàng ý tưởng:** gợi ý ý tưởng theo định dạng viral (listicle, before/after, myth-busting...), lưu lại chống trùng.
- **Giọng đọc AI:** TikTok TTS giọng Việt (tự nhiên, hợp viral), và FPT.AI.
- **Phụ đề động:** highlight theo từng từ (word-level), 5 style (MrBeast / Ali / Marker / Typewriter / Aesthetic).
- **Trợ lý Hoạt hình Veo (thủ công):** sinh sẵn prompt tiếng Anh nhất quán cho từng cảnh, mở Google Flow để bạn tự tạo video bằng Veo, rồi upload lại theo đúng thứ tự cảnh.
- **Render tăng tốc bằng iGPU:** tự dùng VAAPI/QuickSync/VideoToolbox nếu máy hỗ trợ, fallback libx264.
- **Web dashboard:** React + Vite, editor kịch bản + thư viện video + preview.

---

## 🚀 Cài đặt & chạy

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 -m playwright install chromium   # cần cho engine render GSAP + đăng nhập TikTok TTS

# Cấu hình .env:
#   GEMINI_API_KEY=...            (sinh kịch bản/ý tưởng — free tier chỉ 20 request/ngày)
#   GROQ_API_KEY=...              (dự phòng khi Gemini hết quota — free ~14.400 request/ngày,
#                                  đăng ký tại console.groq.com, không bắt buộc nhưng khuyến nghị)
#   TIKTOK_SESSION_ID=...         (giọng TikTok TTS — lấy từ cookie sessionid khi đăng nhập tiktok.com)

# Web app — dùng run.sh để khỏi phải nhớ activate venv mỗi lần mở terminal mới:
./run.sh                 # → http://localhost:5000

# Hoặc thủ công (phải activate venv trước, mỗi terminal mới đều cần):
source venv/bin/activate && python app.py

# Hoặc CLI:
source venv/bin/activate && python main.py --script script.txt --voice tiktok_nu_1
```

> ⚠️ Nếu `python app.py` báo lỗi `ModuleNotFoundError` — venv chưa được activate cho terminal hiện tại (activate không tự động giữ qua các session mới). Dùng `./run.sh` để khỏi lo việc này.

### Lấy TIKTOK_SESSION_ID
Đăng nhập tiktok.com trên trình duyệt → F12 (DevTools) → Application → Cookies → copy giá trị `sessionid` → dán vào `.env`.

---

## 🎬 Cách làm một video (giai đoạn 1: sự thật/tâm lý, faceless)

> Video nền lấy từ clip bạn tự tạo bằng **Google Flow/Veo** (dùng credit gói Gemini Pro nếu có) — hệ thống chỉ hỗ trợ sinh sẵn kịch bản + prompt từng cảnh, phần tạo/tải clip vẫn thao tác tay để tránh rủi ro tự động hoá vi phạm điều khoản Google.

### Bằng giao diện web
1. `python app.py` → mở http://localhost:5000 → vào **Studio Sự Thật**.
2. Gõ ý tưởng (vd "vì sao ta hay trì hoãn") hoặc bấm **Gợi ý ý tưởng** → bấm AI sinh kịch bản (Gemini/Groq viết theo công thức hook → sự thật/lý giải → kêu gọi lưu).
3. Ở khối **"Trợ lý Hoạt hình Veo (thủ công)"**: bấm **Sinh prompt từng cảnh** (đã kèm sẵn câu chỉ định độ dài) → copy từng prompt, bấm **Mở Google Flow** → dán prompt tạo video. Audio bật/tắt trong Flow tuỳ bạn, không ảnh hưởng credit (đã kiểm chứng thực tế với cả Omni Flash lẫn Veo 3.1) — app chỉ lấy hình từ clip, không dùng tiếng gốc (âm thanh cuối luôn là giọng TTS + nhạc nền riêng).
4. Tải các clip Flow về, đặt tên bắt đầu bằng số thứ tự cảnh (`1_...`, `2_...`), upload vào **Media Nền**.
5. Chọn giọng (mặc định **TikTok Nữ**), phong cách phụ đề (**MrBeast** — chữ to, viền đậm, highlight vàng).
6. Bấm **Xuất video ngay** → video hiện ở thư viện (Bảng điều khiển) → xem trước / tải về.

### Bằng dòng lệnh
```bash
# Đặt clip Flow đã tải (1_....mp4, 2_....mp4, ...) vào uploaded_images/ trước
python main.py --script script.txt --voice tiktok_nu_1
# → file trong output/
```

### Sau khi có video — đăng TikTok thủ công
Hệ thống cố tình KHÔNG tự upload (an toàn chính sách), nhưng đã dọn sẵn mọi thứ cho bước đăng.

**Trong web app:** render xong, khối **"Đăng lên TikTok"** hiện ngay dưới video preview với 3 bước bấm là xong:
1. **Tải video về máy** (TikTok web chỉ nhận file từ máy, không nhận URL).
2. **Copy caption + hashtag** — AI tự sinh sẵn ngay khi render xong: caption bám đúng nội dung kịch bản, kết bằng câu hỏi để kéo bình luận, kèm hashtag ngách + 2-3 hashtag riêng theo chủ đề video. Bấm 🔄 để sinh caption khác nếu chưa ưng.
3. **Mở TikTok để đăng** — mở thẳng trang upload TikTok Studio ở tab mới.

Khối này cũng hiện sẵn checklist cài đặt bắt buộc khi đăng:
- **Bật nhãn "Nội dung do AI tạo"** (vì dùng giọng AI) — bật rồi không bị bóp reach, giấu = vi phạm chính sách.
- **Vị trí:** Hà Nội hoặc TP.HCM. **Khung giờ:** 11-13h hoặc 18-21h.
- Cho phép **bình luận / duet / stitch**.

Một việc app không làm thay được: **gắn nhạc đang trend ngay trong app TikTok** lúc đăng (nhạc nền trong video chỉ là nền nhỏ; trending sound mới giúp lên xu hướng).

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
│   ├── tts.py             # TTS đa engine + sinh SRT/word-timing
│   ├── tiktok_tts.py      # TikTok TTS (giọng Việt)
│   ├── video_maker.py     # Render engine (PIL + FFmpeg, HW encode)
│   ├── html_video_maker.py # Render engine GSAP + Playwright (chữ động mượt)
│   ├── bg_finder.py       # Gọi Gemini/Groq: sinh kịch bản/ý tưởng/prompt cảnh cho Veo
│   └── music_finder.py    # Chọn nhạc nền
├── data/               # Models + SQLite jobs + ngân hàng ý tưởng
└── utils/              # Logger
frontend/               # React + Vite SPA
```
