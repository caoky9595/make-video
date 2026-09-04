"""
app.py - Flask Web Server cho VideoMaker Pro
=============================================
Cung cấp giao diện web và API endpoints cho pipeline tạo video.

Chạy:
    python app.py
    → Mở http://localhost:5000
"""

import json
import os
import re
import threading
import time
import glob
import random

from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

load_dotenv()

import uuid
from concurrent.futures import ThreadPoolExecutor
from core.data.models import AudioConfig, SubtitleConfig
from core.data.jobs_db import init_db, create_job, update_job_status, get_job, get_latest_job
from core.data.ideas_db import (
    create_idea, list_ideas, update_idea_status, delete_idea, get_recent_idea_texts,
)

init_db()
executor = ThreadPoolExecutor(max_workers=2)
cancelled_jobs = set()
active_jobs = set()  # job_id của các pipeline đang chạy — dùng để tránh dọn tài nguyên job khác đang dùng

app = Flask(__name__, static_folder="frontend/dist", static_url_path="")
CORS(app)

UPLOADED_IMAGE_DIR = "uploaded_images"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".webm")
STUDIO_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS
MUSIC_DIR = "audio_bg"
MUSIC_EXTENSIONS = (".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac", ".webm")
QUOTA_FILE = "temp/quota_stats.json"
_quota_lock = threading.Lock()  # 2 request song song không được mất lượt đếm

def _read_ai_usage_unlocked():
    today = time.strftime("%Y-%m-%d")
    default_limit = 10 # Mặc định 10 lượt
    os.makedirs("temp", exist_ok=True)
    if not os.path.exists(QUOTA_FILE):
        return {"date": today, "used": 0, "limit": default_limit}

    try:
        with open(QUOTA_FILE, "r") as f:
            data = json.load(f)
            if data.get("date") != today:
                data["date"] = today
                data["used"] = 0
            if "limit" not in data:
                data["limit"] = default_limit
            return data
    except Exception:
        return {"date": today, "used": 0, "limit": default_limit}

def get_ai_usage():
    """Lấy số lượt đã dùng AI trong ngày và hạn mức."""
    with _quota_lock:
        return _read_ai_usage_unlocked()

def update_ai_limit(limit):
    """Cập nhật hạn mức AI tối đa."""
    with _quota_lock:
        data = _read_ai_usage_unlocked()
        data["limit"] = int(limit)
        with open(QUOTA_FILE, "w") as f:
            json.dump(data, f)
        return data

def increment_ai_usage():
    """Tăng số lượt đã dùng AI (read-modify-write nguyên tử)."""
    with _quota_lock:
        data = _read_ai_usage_unlocked()
        data["used"] += 1
        with open(QUOTA_FILE, "w") as f:
            json.dump(data, f)
        return data["used"]

# Trạng thái pipeline
pipeline_status = {
    "running": False,
    "step": "",
    "progress": 0,
    "message": "",
    "output_file": None,
    "error": None,
}


# ============================================================
# PAGES
# ============================================================

@app.route("/")
def index():
    """Index."""
    return send_from_directory("frontend/dist", "index.html")


# ============================================================
# API ENDPOINTS
# ============================================================

def _list_media(directory: str, supported_ext: tuple):
    os.makedirs(directory, exist_ok=True)
    files = [f for f in os.listdir(directory) if f.lower().endswith(supported_ext)]
    result = []
    for f in sorted(files):
        file_path = os.path.join(directory, f)
        result.append({
            "name": f,
            "path": file_path,
            "size_mb": round(os.path.getsize(file_path) / 1024 / 1024, 2),
        })
    return result


def _next_available_filename(directory: str, filename: str):
    name, ext = os.path.splitext(filename)
    candidate = filename
    i = 1
    while os.path.exists(os.path.join(directory, candidate)):
        candidate = f"{name}_{i}{ext}"
        i += 1
    return candidate


def _parse_time_offset_to_seconds(value):
    """Parse thời gian nhạc từ số giây hoặc chuỗi mm:ss / hh:mm:ss."""
    if value is None:
        return 0.0

    if isinstance(value, (int, float)):
        return max(0.0, float(value))

    raw = str(value).strip()
    if not raw:
        return 0.0

    # Plain seconds
    try:
        return max(0.0, float(raw))
    except ValueError:
        pass

    # mm:ss or hh:mm:ss
    parts = raw.split(":")
    if len(parts) not in (2, 3):
        raise ValueError("Thời gian nhạc không hợp lệ. Dùng mm:ss hoặc hh:mm:ss")
    if any((not p.isdigit()) for p in parts):
        raise ValueError("Thời gian nhạc không hợp lệ. Dùng mm:ss hoặc hh:mm:ss")

    nums = [int(p) for p in parts]
    if len(nums) == 2:
        mm, ss = nums
        if ss >= 60:
            raise ValueError("Giây phải nhỏ hơn 60")
        return float(mm * 60 + ss)

    hh, mm, ss = nums
    if mm >= 60 or ss >= 60:
        raise ValueError("Phút/giây phải nhỏ hơn 60")
    return float(hh * 3600 + mm * 60 + ss)


def _parse_music_volume(value, default=0.22):
    """Parse âm lượng nhạc nền trong khoảng [0.0, 1.0]."""
    if value is None:
        return float(default)
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float(default)
    return max(0.0, min(1.0, parsed))


_SCRIPT_LABEL_LINE_RE = re.compile(
    r'(?im)^\s*\*{0,2}(hook|th[aâ]n b[aà]i|k[eê]t th[uú]c|cta|ch[oố]t)\s*:\s*\*{0,2}\s*$\n?'
)
_SCRIPT_LABEL_INLINE_RE = re.compile(
    r'(?i)\*{1,2}\s*(hook|th[aâ]n b[aà]i|k[eê]t th[uú]c|cta|ch[oố]t)\s*:\s*\*{0,2}\s*'
)


def _clean_generated_script(text: str) -> str:
    """Dọn output AI sinh kịch bản: bỏ nhãn cấu trúc ("Hook:", "Thân bài:", "Kết thúc:"...) và
    markdown (**bold**) mà AI đôi khi tự chèn vào dù prompt đã dặn "chỉ trả về lời thoại thuần"
    — nếu để sót, TTS sẽ đọc/hiện luôn nhãn đó ra thành tiếng/phụ đề."""
    text = _SCRIPT_LABEL_LINE_RE.sub("", text)
    text = _SCRIPT_LABEL_INLINE_RE.sub("", text)
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

@app.route("/api/voices", methods=["GET"])
def api_voices():
    """Trả về danh sách tất cả giọng đọc."""
    from core.engines.tts import EDGE_VOICES, FPT_VOICES, TIKTOK_VOICES
    voices = []
    # TikTok TTS (giọng Việt tự nhiên, hợp viral) — ưu tiên hiển thị đầu danh sách
    tiktok_session_ready = bool(
        os.getenv("TIKTOK_SESSION_ID")
        or os.path.exists(os.path.join("core", "engines", "tiktok_session.txt"))
    )
    for key, info in TIKTOK_VOICES.items():
        voices.append({
            "id": key,
            "name": key.replace("tiktok_", "TikTok ").title(),
            "gender": info["gender"],
            "region": "VN",
            "engine": "TikTok TTS",
            "desc": info["desc"],
            "free": True,
            "needs_session": True,
            "ready": tiktok_session_ready,
        })
    for key, voice_id in EDGE_VOICES.items():
        gender = "Nữ" if "HoaiMy" in voice_id else "Nam"
        region = "Bắc"
        voices.append({
            "id": key,
            "name": key.title(),
            "gender": gender,
            "region": region,
            "engine": "Edge-TTS",
            "desc": f"{gender} {region}",
            "free": True,
        })
    for key, info in FPT_VOICES.items():
        voices.append({
            "id": key,
            "name": key.title(),
            "gender": info["gender"],
            "region": info["region"],
            "engine": "FPT.AI",
            "desc": info["desc"],
            "free": True,
        })
    return jsonify(voices)


@app.route("/api/tts/preview", methods=["POST"])
def api_tts_preview():
    """Tạo audio preview cho một đoạn text ngắn."""
    data = request.json
    text = data.get("text", "Xin chào, đây là giọng đọc mẫu.")
    voice = data.get("voice", "hoaimy")
    rate = data.get("rate", "+50%")

    # Tạo file preview tạm
    os.makedirs("temp", exist_ok=True)
    preview_path = f"temp/preview_{voice}.mp3"
    preview_script = f"temp/preview_{voice}.txt"

    with open(preview_script, "w", encoding="utf-8") as f:
        f.write(text)

    try:
        from core.engines.tts import run_tts
        run_tts(preview_script, preview_path, f"temp/preview_{voice}.srt", rate=rate, voice=voice)
        return send_file(preview_path, mimetype="audio/mpeg")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/script/save", methods=["POST"])
def api_script_save():
    """Lưu kịch bản vào file (chỉ cho phép file .txt ngay trong thư mục project)."""
    data = request.json
    text = data.get("text", "")
    filename = os.path.basename(data.get("filename", "script.txt"))
    if not filename.endswith(".txt"):
        return jsonify({"error": "Chỉ cho phép lưu file .txt"}), 400

    with open(filename, "w", encoding="utf-8") as f:
        f.write(text)

    char_count = len(text)
    return jsonify({"success": True, "chars": char_count, "filename": filename})


# Trần số từ mặc định cho 1 kịch bản. ~20 ký tự/giây khi đọc (CHARS_PER_SECOND_ESTIMATE ở
# bg_finder), tiếng Việt ~5 ký tự/từ kể cả dấu cách -> 65 từ ≈ 16 giây, 45 từ ≈ 11 giây.
# Hạ từ 90 xuống 65 (22/08/2026): thuật toán TikTok 2026 đòi ~70% người xem HẾT video mới đẩy
# tiếp (2024 chỉ ~50%). Video 21s phải giữ chân 14,5s, còn 14s chỉ cần 10s — dễ hơn hẳn.
# Người dùng chỉnh được trong UI (gửi kèm `word_cap`), đây chỉ là giá trị mặc định.
# Kể chuyện cần dài hơn nêu-sự-thật: phải dựng bối cảnh, thả chi tiết lạ tăng dần, rồi mới bỏ ngỏ.
# Đo lại với giọng mặc định mới (12 ký tự/giây): 75 từ ~ 31 giây. Ngách bí ẩn giữ chân được lâu vì có vòng lặp mở, nên video dài không bất lợi
# như format cũ (nêu đáp án ngay đầu, xem xong tiêu đề là hết lý do ở lại).
DEFAULT_SCRIPT_WORD_CAP = 75
SCRIPT_WORD_CAP_MIN = 25
SCRIPT_WORD_CAP_MAX = 200


@app.route("/api/script/generate", methods=["POST"])
def api_script_generate():
    """Tạo kịch bản bằng AI Gemini từ ý tưởng."""
    data = request.json
    idea = data.get("idea", "").strip()
    idea_id = data.get("idea_id")
    if not idea:
        idea = "Một vụ mất tích hoặc hiện tượng có thật đến nay vẫn chưa có lời giải (Random)"

    if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GROQ_API_KEY"):
        return jsonify({"error": "Chưa cấu hình GEMINI_API_KEY hoặc GROQ_API_KEY trong file .env"}), 400

    mode = data.get("mode", "viral")

    # Trần độ dài do người dùng chọn trong UI; kẹp trong khoảng an toàn để 1 giá trị vô lý
    # (0, âm, hay 10000) không làm hỏng prompt.
    try:
        SCRIPT_WORD_CAP = int(data.get("word_cap") or DEFAULT_SCRIPT_WORD_CAP)
    except (TypeError, ValueError):
        SCRIPT_WORD_CAP = DEFAULT_SCRIPT_WORD_CAP
    SCRIPT_WORD_CAP = max(SCRIPT_WORD_CAP_MIN, min(SCRIPT_WORD_CAP_MAX, SCRIPT_WORD_CAP))
    # Khoảng "mục tiêu" phải co giãn theo trần, không được ghi cứng — nếu ghi cứng thì kéo
    # thanh trượt lên cao vẫn ra kịch bản ngắn y hệt, người dùng tưởng nút hỏng.
    # Khoảng từ MỤC TIÊU, tính từ trần người dùng đặt. Trước đây lấy 0.55-0.78 lần trần nên
    # kịch bản chỉ dùng ~2/3 thời lượng: đặt trần 65 từ (UI ghi "16s") nhưng AI viết 35-50 từ,
    # video ra 8-9s — hụt ~40% so với cái người dùng chọn. Tệ hơn, câu "(video ra khoảng N giây)"
    # trong prompt lại tính từ TRẦN chứ không phải từ khoảng mục tiêu, nên prompt tự mâu thuẫn:
    # bảo AI viết 35-50 từ mà lại nói video sẽ dài 16 giây.
    # Nay để 0.80-0.95 lần trần, và TARGET_SEC tính từ chính giữa khoảng mục tiêu.
    TARGET_LO = int(SCRIPT_WORD_CAP * 0.80)
    TARGET_HI = int(SCRIPT_WORD_CAP * 0.95)
    TARGET_SEC = round((TARGET_LO + TARGET_HI) / 2 * 5 / 20)

    if mode == "viral":
        prompt = f"""Bạn là người kể chuyện TikTok ngách Bí Ẩn & Vụ Án Có Thật, kéo VIEW và FOLLOW cho kênh mới.
        Nhiệm vụ: Biến ý tưởng "{idea}" thành kịch bản KỂ CHUYỆN, tối ưu để người xem phải xem HẾT mới biết kết.

        Quy tắc Chế độ KỂ CHUYỆN BÍ ẨN:
        1. **TUYỆT ĐỐI KHÔNG tiết lộ đáp án ở đầu — đây là quy tắc quan trọng nhất.**
           Kênh trước của người dùng thất bại vì đúng lỗi này: mở bằng "90% trì hoãn không phải vì
           lười" tức nói luôn điều thú vị nhất ngay câu đầu, xem xong tiêu đề là hết lý do ở lại
           -> người xem rời ở giây 0:01, chỉ 4,8% xem hết.
           Kể chuyện phải TẠO CÂU HỎI rồi giữ nó mở, không phải đưa kết luận rồi giải thích.
        2. **Câu đầu: thả người xem vào GIỮA sự việc, có mốc thời gian/địa điểm/con số cụ thể.**
           - ĐÚNG: "Năm 1959, chín người leo núi bỏ chạy khỏi lều giữa đêm âm 30 độ. Lều bị rạch từ BÊN TRONG."
           - ĐÚNG: "Con tàu chở 42 thuyền viên cập cảng đúng lịch. Trên boong không còn một ai."
           - SAI (nêu kết luận trước): "Vụ mất tích này thực ra là do khí độc rò rỉ."
           - SAI (rào đón): "Hôm nay mình kể các bạn nghe một vụ án bí ẩn."
        3. **Thân bài: mỗi câu thêm MỘT chi tiết lạ, tăng dần độ khó hiểu.** Chi tiết phải cụ thể
           (con số, vật chứng, lời khai) — không nói chung chung. Càng kể càng khó hiểu, không được
           giải thích sớm.
        4. **Kết: chốt bằng giả thuyết BỎ NGỎ, không khép lại.** Nói rõ đến nay vẫn chưa có lời
           giải, hoặc nêu 2 giả thuyết trái ngược. KHÔNG kết luận dứt khoát.
        5. **Sự việc phải CÓ THẬT, kể đúng sự thật.** Không bịa vụ án, không bịa số liệu, không
           thêm chi tiết rùng rợn không có thật. Nếu chỉ là truyền thuyết/tin đồn thì phải nói rõ
           là chưa kiểm chứng. Bịa chuyện có thật là vi phạm chính sách tin sai lệch.
        6. **Tránh cảnh máu me, tử thi, bạo lực chi tiết** — vừa bị hạn chế phân phối, vừa không
           cần thiết. Sự bí ẩn mới giữ người xem, không phải sự ghê rợn.
        7. Độ dài lời thoại: mục tiêu ~{TARGET_LO}-{TARGET_HI} từ (video khoảng {TARGET_SEC} giây).
           GIỚI HẠN CỨNG: không vượt quá {SCRIPT_WORD_CAP} từ.
        8. **Kết thúc bằng CÂU HỎI cho người xem trả lời**, dạng chọn 1 trong 2 hoặc đoán giả thuyết:
           "Bạn nghiêng về giả thuyết nào — tai nạn hay có người thứ ba?", "Bạn nghĩ họ còn sống không?"

        Cấu trúc: Thả vào giữa sự việc -> chi tiết lạ tăng dần -> bỏ ngỏ + câu hỏi.
        Quy tắc: văn nói tự nhiên, kể như đang thì thầm với bạn. CHỈ TRẢ VỀ lời thoại thuần —
        KHÔNG nhãn cấu trúc, KHÔNG markdown, KHÔNG mô tả cảnh quay hay timestamp.
        """
    elif mode == "digital_aff":
        prompt = f"""Bạn là Chuyên gia Affiliate sản phẩm số (app/dịch vụ) ngách Tâm Lý & Phát Triển Bản Thân, quảng bá qua link ngoài (AccessTrade...), KHÔNG qua giỏ hàng TikTok Shop.
        Nhiệm vụ: Biến ý tưởng "{idea}" thành kịch bản video 15-20 giây giới thiệu 1 app/dịch vụ số giải quyết vấn đề tâm lý/thói quen/cuộc sống cá nhân.
        Bối cảnh: video dùng hình ảnh hoạt hình AI (Google Flow/Veo), KHÔNG cần footage thật vì đây là sản phẩm số — không bị ràng buộc quy tắc "phải quay thật" của giỏ hàng TikTok Shop.

        Quy tắc Chế độ AFFILIATE SẢN PHẨM SỐ:
        1. **Hook 2-3 giây:** nêu đúng MỘT nỗi đau tâm lý/thói quen cụ thể mà app/dịch vụ giải quyết (vd mất ngủ vì suy nghĩ nhiều, hay trì hoãn, khó kiểm soát cảm xúc, khó tập trung).
        2. **Thân 10-14 giây:** mô tả app/dịch vụ giải quyết nỗi đau đó như thế nào, tính năng cụ thể dễ hình dung. Chỉ nói công dụng THẬT — TUYỆT ĐỐI không phóng đại hay bịa tính năng.
        3. **CTA 2-3 giây cuối:** điều hướng LINK (không phải giỏ hàng), ví dụ "Link tải app ở phần mô tả/bio nha", "Xem chi tiết ở link mình để dưới bio".
        4. Giọng văn tự nhiên như đang nói chuyện với bạn, không như đọc quảng cáo.
        5. Tổng độ dài lời thoại: NGẮN — mục tiêu ~{TARGET_LO}-{TARGET_HI} từ (video ra khoảng {TARGET_SEC} giây). GIỚI HẠN CỨNG: KHÔNG BAO GIỜ vượt quá {SCRIPT_WORD_CAP} từ — trước khi trả lời, tự đếm số từ bản nháp trong đầu; nếu vượt thì lược bớt cho tới khi dưới {SCRIPT_WORD_CAP} từ rồi mới trả lời.

        Cấu trúc: Hook nỗi đau -> Demo giải pháp (app/dịch vụ) -> CTA link.
        Quy tắc: NGẮN, GẮT, THẤM. CHỈ TRẢ VỀ lời thoại thuần, viết liền mạch tự nhiên như đang nói — KHÔNG chèn nhãn cấu trúc ("Hook:", "Thân bài:", "CTA:"...), KHÔNG dùng markdown (**, __), không kèm mô tả cảnh quay hay timestamp.
        """
    else:
        prompt = f"""Bạn là một Chuyên gia bán hàng Affiliate TikTok Shop ngách Phát Triển Bản Thân & Đời Sống Tinh Thần (sổ tay lên kế hoạch, đồ hỗ trợ thói quen tốt, dụng cụ thư giãn...).
        Nhiệm vụ: Biến ý tưởng "{idea}" thành kịch bản video 15-20 giây bán hàng qua giỏ hàng TikTok Shop.
        Bối cảnh: video sẽ ghép với FOOTAGE THẬT quay sản phẩm bằng điện thoại (tay thao tác + sản phẩm, không lộ mặt), nên lời thoại phải bám sát thao tác demo được bằng tay.

        Quy tắc Chế độ AFFILIATE (BÁN HÀNG):
        1. **Hook 2-3 giây:** nêu đúng MỘT nỗi đau cụ thể về thói quen/tinh thần mà sản phẩm giải quyết (vd quên việc cần làm, khó duy trì thói quen tốt, khó tập trung).
        2. **Thân 10-14 giây:** mô tả sản phẩm đang được demo giải quyết nỗi đau đó như thế nào. Chỉ nói công dụng THẬT, kiểm chứng được — TUYỆT ĐỐI không phóng đại hay bịa tính năng (vi phạm = đóng băng hoa hồng).
        3. **CTA 2-3 giây cuối:** điều hướng giỏ hàng, ví dụ "Giỏ hàng góc trái màn hình nha".
        4. Giọng văn tự nhiên như đang nói chuyện với bạn, không như đọc quảng cáo.
        5. Tổng độ dài lời thoại: NGẮN — mục tiêu ~{TARGET_LO}-{TARGET_HI} từ (video ra khoảng {TARGET_SEC} giây). GIỚI HẠN CỨNG: KHÔNG BAO GIỜ vượt quá {SCRIPT_WORD_CAP} từ — trước khi trả lời, tự đếm số từ bản nháp trong đầu; nếu vượt thì lược bớt cho tới khi dưới {SCRIPT_WORD_CAP} từ rồi mới trả lời.

        Cấu trúc: Hook nỗi đau -> Demo giải pháp -> CTA giỏ hàng.
        Quy tắc: NGẮN, GẮT, THẤM. CHỈ TRẢ VỀ lời thoại thuần, viết liền mạch tự nhiên như đang nói — KHÔNG chèn nhãn cấu trúc ("Hook:", "Thân bài:", "CTA:"...), KHÔNG dùng markdown (**, __), không kèm mô tả cảnh quay hay timestamp.
        """
    
    from core.engines.bg_finder import call_llm_with_fallback

    try:
        text = call_llm_with_fallback(prompt, json_mode=False)
        increment_ai_usage()
        # AI đôi khi phá luôn giới hạn dù đã dặn trong prompt — chỉ dựa vào lời dặn là chưa đủ
        # tin cậy, nên nếu vượt xa trần (hơn ~15%) thì bắt viết lại ngắn hơn 1 lần.
        word_count = len(text.split())
        if word_count > SCRIPT_WORD_CAP * 1.15:
            retry_prompt = (
                prompt
                + f"\n\nLƯU Ý: bản nháp trước có khoảng {word_count} từ, VƯỢT giới hạn {SCRIPT_WORD_CAP} từ."
                  f" Viết lại NGẮN HƠN, dưới {SCRIPT_WORD_CAP} từ, vẫn giữ đủ hook + ý chính + câu chốt."
            )
            text = call_llm_with_fallback(retry_prompt, json_mode=False)
            increment_ai_usage()
        if idea_id:
            update_idea_status(idea_id, "used")
        return jsonify({"text": _clean_generated_script(text)})
    except Exception as e:
        return jsonify({"error": f"Lỗi gọi AI: {str(e)}"}), 500

# Các định dạng video viral (xem docs/content_ideas_bank.md) dùng để định hướng Gemini sinh ý tưởng.
IDEA_FORMATS = {
    "listicle": "Listicle đếm số (\"X sự thật/lý do trong Y giây\") — liệt kê rõ số lượng, mỗi ý 1 sự thật ngắn gọn.",
    "before_after": "Trước/Sau nhận thức — mở đầu bằng suy nghĩ/thói quen sai phổ biến, kết bằng góc nhìn hoặc cách làm đúng.",
    "myth_busting": "Myth-busting / Sai lầm phổ biến — chỉ ra 1 điều đa số đang hiểu sai (pattern interrupt) rồi đưa sự thật đúng.",
    "countdown_hook": "Đếm ngược giữ chân — liệt kê vài sự thật nhưng hứa hẹn sự thật cuối là sốc/hay nhất để giữ chân người xem tới cuối.",
    "relatable_moment": "Khoảnh khắc đồng cảm — 1 tình huống đời thường ai cũng từng trải qua, chốt lại bằng lý giải tâm lý đằng sau.",
    "reply_comment": "Reply-to-comment — mở đầu bằng \"Bạn X hỏi...\" rồi trả lời bằng 1 sự thật/lý giải cụ thể.",
}


@app.route("/api/ideas/generate", methods=["GET", "POST"])
def api_ideas_generate():
    """Gợi ý 5 ý tưởng video theo mode (viral/affiliate/digital_aff) đang chọn ở Studio, lưu
    vào ngân hàng ý tưởng cùng mode đó (để khớp với chế độ kịch bản sẽ dùng sau) và tránh lặp
    lại ý tưởng cũ."""
    if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GROQ_API_KEY"):
        return jsonify({"error": "Chưa cấu hình GEMINI_API_KEY hoặc GROQ_API_KEY"}), 400

    data = request.json if request.method == "POST" else request.args
    mode = (data.get("mode") or "viral").strip()
    if mode not in ("viral", "affiliate", "digital_aff"):
        mode = "viral"

    # Định dạng viral (listicle/before_after/...) chỉ có ý nghĩa cho mode viral.
    format_key = (data.get("format") or "").strip() if mode == "viral" else ""
    format_hint = IDEA_FORMATS.get(format_key)
    if not format_hint:
        format_key = ""

    recent_texts = get_recent_idea_texts(limit=30)
    avoid_block = ""
    if recent_texts:
        avoid_list = "\n".join(f"- {t}" for t in recent_texts)
        avoid_block = f"\n\nKHÔNG lặp lại (hoặc quá giống) các ý tưởng đã có sau đây:\n{avoid_list}\n"

    if mode == "digital_aff":
        prompt = f"""Bạn là chuyên gia Affiliate sản phẩm số (app/dịch vụ) ngách Tâm Lý & Phát Triển Bản Thân tại Việt Nam, quảng bá qua link ngoài (AccessTrade...), KHÔNG qua giỏ hàng TikTok Shop, KHÔNG cần quay footage thật (dùng hình ảnh hoạt hình AI qua Google Flow/Veo).
        Hãy đề xuất 5 ý tưởng video ngắn (15-20s), mỗi ý tưởng xoay quanh 1 NỖI ĐAU cụ thể về tâm lý/thói quen/cuộc sống cá nhân mà 1 LOẠI app/dịch vụ số có thể giải quyết (vd: mất ngủ vì suy nghĩ nhiều, hay trì hoãn công việc, khó kiểm soát chi tiêu theo cảm xúc, khó tập trung học/làm việc, muốn thiền nhưng không biết bắt đầu từ đâu...).
        Yêu cầu:
        1. Mỗi ý tưởng nêu rõ NỖI ĐAU cụ thể + LOẠI app/dịch vụ giải quyết (mô tả loại hình, không cần tên app thật).
        2. Không bịa tính năng phi thực tế — chỉ mô tả công dụng hợp lý một app/dịch vụ dạng đó thường có.
        3. Định dạng: "[Nỗi đau cụ thể] -> [loại app/dịch vụ giải quyết]".
        4. CHỈ TRẢ VỀ JSON array: ["ý tưởng 1", "ý tưởng 2", ...]
        {avoid_block}"""
    elif mode == "affiliate":
        prompt = f"""Bạn là chuyên gia Affiliate TikTok Shop ngách Phát Triển Bản Thân & Đời Sống Tinh Thần tại Việt Nam (giai đoạn 2 — đã đủ follower, có mẫu sản phẩm, quay footage thật bằng điện thoại, không lộ mặt).
        Hãy đề xuất 5 ý tưởng video ngắn (15-20s) bán hàng qua giỏ hàng TikTok Shop, mỗi ý tưởng xoay quanh 1 NỖI ĐAU cụ thể về thói quen/tinh thần mà 1 LOẠI sản phẩm cụ thể giải quyết (vd: sổ tay lên kế hoạch, bảng theo dõi thói quen, đèn ngủ hỗ trợ thư giãn, đồng hồ nhắc uống nước/nghỉ ngơi...).
        Yêu cầu:
        1. Mỗi ý tưởng nêu rõ NỖI ĐAU cụ thể + LOẠI sản phẩm giải quyết (mô tả loại sản phẩm, không cần thương hiệu thật).
        2. Không bịa công dụng phi thực tế — chỉ nêu công dụng hợp lý, kiểm chứng được (vi phạm = đóng băng hoa hồng theo chính sách TikTok Shop).
        3. Định dạng: "[Nỗi đau cụ thể] -> [loại sản phẩm giải quyết]".
        4. CHỈ TRẢ VỀ JSON array: ["ý tưởng 1", "ý tưởng 2", ...]
        {avoid_block}"""
    else:
        format_instruction = (
            f"5. Mọi ý tưởng PHẢI theo định dạng: {format_hint}"
            if format_hint else
            "5. Chọn định dạng phù hợp cho từng ý tưởng: listicle đếm số, trước/sau nhận thức, myth-busting, đếm ngược giữ chân, hoặc khoảnh khắc đồng cảm."
        )
        prompt = f"""Bạn là người tìm đề tài cho kênh TikTok ngách Bí Ẩn & Vụ Án Có Thật tại Việt Nam (kênh faceless, hình dựng bằng AI + giọng đọc AI).
        Hãy đề xuất 5 ý tưởng video KỂ CHUYỆN, mỗi ý tưởng là một sự việc CÓ THẬT còn bỏ ngỏ.
        Yêu cầu:
        1. Sự việc phải CÓ THẬT và kiểm chứng được (vụ mất tích, hiện tượng chưa lời giải, khảo cổ
           kỳ lạ, tàu/máy bay biến mất, công trình cổ khó lý giải...). KHÔNG bịa vụ án.
           Nếu là truyền thuyết/tin đồn chưa kiểm chứng thì phải ghi rõ trong ý tưởng.
        2. **Mỗi ý tưởng phải có một CHI TIẾT LẠ cụ thể làm điểm neo** — con số, vật chứng, tình
           tiết khó hiểu. Đây là thứ tạo tò mò, không phải chủ đề chung chung.
           - SAI (chung chung): "Vụ mất tích bí ẩn ở Nga"
           - ĐÚNG (có chi tiết neo): "9 người leo núi Dyatlov bỏ chạy khỏi lều giữa đêm âm 30 độ, lều bị rạch từ BÊN TRONG"
        3. Ưu tiên sự việc **chưa có kết luận chính thức** — còn bỏ ngỏ mới kể được thành chuyện.
           Sự việc đã có đáp án rõ ràng thì hết bí ẩn.
        4. TRÁNH đề tài máu me/tử thi/bạo lực chi tiết — bị hạn chế phân phối. Ưu tiên cái KHÓ HIỂU
           hơn cái GHÊ RỢN.
        5. Đa dạng: đừng cho cả 5 cùng một loại (đừng 5 vụ mất tích liền). Trộn giữa mất tích,
           khảo cổ, hiện tượng tự nhiên, công trình cổ, sự kiện lịch sử khó lý giải.
        6. Định dạng mỗi ý tưởng: "[Loại] Bối cảnh + chi tiết lạ cụ thể".
        {format_instruction}
        7. CHỈ TRẢ VỀ JSON array: ["ý tưởng 1", "ý tưởng 2", ...]
        {avoid_block}"""

    from core.engines.bg_finder import call_llm_with_fallback

    try:
        content = call_llm_with_fallback(prompt, json_mode=True)
        increment_ai_usage()
        ideas = json.loads(content)
        saved = []
        for text in ideas:
            new_id = create_idea(text=text, format=format_key or None, mode=mode)
            saved.append({"id": new_id, "text": text})
        return jsonify({"ideas": saved})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ideas", methods=["GET", "POST"])
def api_ideas():
    """Ngân hàng ý tưởng: liệt kê (GET) hoặc thêm tay (POST)."""
    if request.method == "GET":
        status = request.args.get("status")
        category = request.args.get("category")
        mode = request.args.get("mode")
        return jsonify({"ideas": list_ideas(status=status, category=category, mode=mode)})

    data = request.json or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Thiếu nội dung ý tưởng"}), 400
    new_id = create_idea(text=text, category=data.get("category"), format=data.get("format"), mode=data.get("mode", "viral"))
    if new_id is None:
        return jsonify({"error": "Không thể lưu ý tưởng"}), 500
    return jsonify({"id": new_id, "text": text})


@app.route("/api/ideas/<int:idea_id>/status", methods=["POST"])
def api_idea_update_status(idea_id):
    """Cập nhật trạng thái 1 ý tưởng (new/used/skipped)."""
    data = request.json or {}
    status = data.get("status")
    if not update_idea_status(idea_id, status):
        return jsonify({"error": "Cập nhật thất bại (status không hợp lệ hoặc lỗi DB)"}), 400
    return jsonify({"ok": True})


@app.route("/api/ideas/<int:idea_id>", methods=["DELETE"])
def api_idea_delete(idea_id):
    """Xoá 1 ý tưởng khỏi ngân hàng."""
    if not delete_idea(idea_id):
        return jsonify({"error": "Xoá thất bại"}), 500
    return jsonify({"ok": True})

@app.route("/api/script/load", methods=["GET"])
def api_script_load():
    """Đọc nội dung kịch bản hiện tại (chỉ file .txt trong thư mục project)."""
    filename = os.path.basename(request.args.get("filename", "script.txt"))
    if not filename.endswith(".txt"):
        return jsonify({"error": "Chỉ cho phép đọc file .txt"}), 400
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            text = f.read()
        return jsonify({"text": text, "chars": len(text)})
    return jsonify({"text": "", "chars": 0})


@app.route("/api/scene-prompts/generate", methods=["POST"])
def api_scene_prompts_generate():
    """Tách kịch bản thành từng cảnh + sinh prompt tiếng Anh nhất quán cho mỗi cảnh.

    Phục vụ trợ lý "Hoạt hình Veo thủ công": người dùng copy từng prompt dán vào
    Google Flow/Gemini, tải video về, rồi upload theo đúng thứ tự cảnh vào Media Nền.
    """
    data = request.json or {}
    script = (data.get("script") or "").strip()
    if not script:
        return jsonify({"error": "Thiếu nội dung kịch bản"}), 400

    from core.engines.bg_finder import (
        estimate_scenes_and_duration, group_script_into_scenes, generate_scene_prompts_with_gemini,
    )

    scene_count, duration_sec = estimate_scenes_and_duration(script)
    sentences = group_script_into_scenes(script, max_scenes=scene_count)
    if not sentences:
        return jsonify({"error": "Không tách được câu nào từ kịch bản"}), 400

    prompts = generate_scene_prompts_with_gemini(script, sentences, scene_duration_sec=duration_sec)
    increment_ai_usage()
    # Nhét sẵn yêu cầu độ dài vào cuối prompt (câu riêng, tách bạch khỏi mô tả hình ảnh) — vì
    # đây là hội thoại (agent tự parse câu chữ, không có dropdown chọn giây), ghép sẵn vào đây
    # để người dùng chỉ cần copy-dán 1 lần, khỏi phải nhớ nói thêm câu riêng trong chat.
    def _with_duration(prompt: str) -> str:
        text = prompt.rstrip()
        if text and text[-1] not in ".!?":
            text += "."
        return f"{text} Video duration: {duration_sec} seconds."

    scenes = [
        {"index": i + 1, "sentence": sentence, "prompt": _with_duration(prompt)}
        for i, (sentence, prompt) in enumerate(zip(sentences, prompts))
    ]
    return jsonify({"scenes": scenes, "recommended_duration_sec": duration_sec})


# Hashtag cố định của ngách (RULES.md mục 3) — luôn có mặt để thuật toán hiểu đúng ngách kênh.
# Giữ ít và đúng ngách thay vì nhồi chục hashtag chung chung (làm loãng tín hiệu phân phối).
NICHE_HASHTAGS = ["#suthat", "#tamly", "#tamlyhoc", "#xuhuong", "#fyp"]


def _strip_vietnamese_accents(text: str) -> str:
    """Bỏ dấu tiếng Việt, giữ nguyên chữ cái gốc ("ghi nhớ" -> "ghi nho").

    Cần thiết vì AI đôi khi vẫn trả hashtag CÓ DẤU dù đã dặn không dấu. Nếu chỉ xoá thẳng ký tự
    không phải ASCII, chữ có dấu bị mất luôn khiến hashtag hỏng nghĩa (vd "#ghinhớ" -> "#ghinh"),
    thành tag chết không ai search. Chuẩn hoá NFD tách chữ khỏi dấu rồi bỏ riêng phần dấu; chữ
    đ/Đ không tách được bằng NFD nên map tay.
    """
    import unicodedata

    text = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


@app.route("/api/publish-kit/generate", methods=["POST"])
def api_publish_kit_generate():
    """Sinh caption + hashtag sẵn sàng dán lên TikTok từ kịch bản của video vừa render.

    Caption theo đúng playbook kênh (channel_strategy.md mục 9): câu gợi tò mò/đặt câu hỏi để
    kéo bình luận, KHÔNG giật tít sai sự thật (RULES.md mục 3).
    """
    data = request.json or {}
    script = (data.get("script") or "").strip()
    if not script:
        return jsonify({"error": "Thiếu nội dung kịch bản"}), 400

    from core.engines.bg_finder import call_llm_with_fallback

    prompt = f"""Viết caption TikTok tiếng Việt cho video thuộc ngách "Sự Thật Thú Vị & Tâm Lý Cuộc Sống".

Kịch bản video: {script[:1000]}

Yêu cầu caption:
- 1-2 câu NGẮN (tối đa 150 ký tự), đúng nội dung kịch bản, TUYỆT ĐỐI không giật tít sai sự thật hay hứa hẹn quá lời.
- Kết bằng 1 CÂU HỎI mở để kéo bình luận (vd "Bạn có bị vậy không?", "Bạn nghĩ sao?").
- Giọng thân mật, tự nhiên như người thật viết, không sáo rỗng, không dùng emoji quá 2 cái.
- KHÔNG kèm hashtag (hệ thống tự thêm sau).

CHỈ TRẢ VỀ JSON: {{"caption": "...", "extra_hashtags": ["#tag1", "#tag2"]}}
Trong đó extra_hashtags là 2-3 hashtag tiếng Việt KHÔNG DẤU bám sát chủ đề riêng của video này
(vd video về trí nhớ thì #trinho, #ghinho) — không lặp lại các tag đã có: {' '.join(NICHE_HASHTAGS)}"""

    caption = ""
    extra = []
    try:
        import json as _json
        result = _json.loads(call_llm_with_fallback(prompt, json_mode=True))
        caption = (result.get("caption") or "").strip()
        extra = [str(t).strip() for t in (result.get("extra_hashtags") or []) if str(t).strip()]
        increment_ai_usage()
    except Exception as e:
        logger.info(f"  [Publish Kit] AI lỗi ({e}), dùng caption fallback từ câu đầu kịch bản.")

    if not caption:
        # Fallback không cần AI: lấy câu đầu (thường là hook) làm caption.
        first_sentence = re.split(r"[.!?\n]", script.strip())[0].strip()
        caption = f"{first_sentence}. Bạn thấy đúng không?" if first_sentence else "Bạn thấy đúng không?"

    # Chuẩn hoá hashtag AI trả về: bỏ dấu #, ký tự lạ rồi gắn lại — tránh tag hỏng dạng "# tag"
    # hay "#tag!" khiến TikTok cắt sai.
    cleaned_extra = []
    for tag in extra:
        slug = re.sub(r"[^0-9a-zA-Z_]", "", _strip_vietnamese_accents(tag.lstrip("#")))
        if slug and f"#{slug.lower()}" not in [t.lower() for t in NICHE_HASHTAGS + cleaned_extra]:
            cleaned_extra.append(f"#{slug}")

    hashtags = NICHE_HASHTAGS + cleaned_extra[:3]
    return jsonify({
        "caption": caption,
        "hashtags": hashtags,
        "full_caption": f"{caption}\n\n{' '.join(hashtags)}",
    })


@app.route("/api/images", methods=["GET"])
def api_images():
    """Trả về danh sách tài nguyên (ảnh/video) Studio, ĐÚNG THỨ TỰ CẢNH mà engine render sẽ dùng.

    Phải dùng chung `_collect_visual_sources` với engine render, không sort tên A-Z riêng ở đây —
    nếu danh sách hiển thị khác thứ tự render thật thì người dùng không thể phát hiện cảnh bị
    xếp sai trước khi xuất video (đúng lỗi đã gặp: UI liệt kê A-Z, engine lại xếp theo mtime).
    """
    from core.engines.video_maker import _collect_visual_sources

    ordered_paths = _collect_visual_sources(UPLOADED_IMAGE_DIR)
    return jsonify([
        {
            "name": os.path.basename(p),
            "path": p,
            "size_mb": round(os.path.getsize(p) / 1024 / 1024, 2),
            "scene_index": i + 1,
        }
        for i, p in enumerate(ordered_paths)
    ])


@app.route("/api/images/upload", methods=["POST"])
def api_images_upload():
    """Upload một hoặc nhiều ảnh/video vào thư viện Studio."""
    files = request.files.getlist("images")
    if not files:
        return jsonify({"error": "Không có file nào được gửi lên!"}), 400

    # Thời điểm sửa file GỐC trên máy người dùng (File.lastModified của trình duyệt, đơn vị ms) —
    # tức lúc tải clip từ Flow về. Cần giữ lại vì `f.save()` ghi file mới trên server nên mtime
    # thành GIỜ UPLOAD (mọi file cách nhau vài mili giây, xếp theo thứ tự trình duyệt gửi = A-Z),
    # làm hỏng cách sắp cảnh theo thời gian tải về.
    raw_ts = request.form.getlist("last_modified")

    os.makedirs(UPLOADED_IMAGE_DIR, exist_ok=True)
    uploaded = []
    rejected = []

    for idx, f in enumerate(files):
        original_name = (f.filename or "").strip()
        if not original_name:
            continue

        safe_name = secure_filename(original_name)
        ext = os.path.splitext(safe_name)[1].lower()
        if ext not in STUDIO_EXTENSIONS:
            rejected.append(original_name)
            continue

        final_name = _next_available_filename(UPLOADED_IMAGE_DIR, safe_name)
        save_path = os.path.join(UPLOADED_IMAGE_DIR, final_name)
        f.save(save_path)

        if idx < len(raw_ts):
            try:
                ts = float(raw_ts[idx]) / 1000.0
                if ts > 0:
                    os.utime(save_path, (ts, ts))
            except (TypeError, ValueError, OSError):
                pass  # không đặt được thì giữ mtime mặc định, vẫn dùng được

        uploaded.append(final_name)

    if not uploaded:
        return jsonify({
            "error": "Không có file hợp lệ. Hỗ trợ Ảnh (JPG/PNG/WEBP) và Video (MP4/MOV...).",
            "rejected": rejected,
        }), 400

    return jsonify({"success": True, "uploaded": uploaded, "rejected": rejected})


@app.route("/api/images/reorder", methods=["POST"])
def api_images_reorder():
    """Chốt cứng thứ tự cảnh bằng cách đổi tên file thành `1_`, `2_`, `3_`...

    Tên file có số thứ tự là tín hiệu đáng tin nhất (engine render ưu tiên nó trước mtime), nên
    sau khi người dùng sắp xong thì ghi thẳng vào tên file — không phụ thuộc mtime nữa.
    """
    data = request.json or {}
    order = data.get("order") or []
    if not isinstance(order, list) or not order:
        return jsonify({"error": "Thiếu danh sách thứ tự"}), 400

    existing = {
        f for f in os.listdir(UPLOADED_IMAGE_DIR)
        if f.lower().endswith(STUDIO_EXTENSIONS)
    } if os.path.isdir(UPLOADED_IMAGE_DIR) else set()

    names = [os.path.basename(str(n)) for n in order]
    if any(n not in existing for n in names):
        return jsonify({"error": "Danh sách chứa file không tồn tại"}), 400

    # Đổi tên 2 bước qua tên tạm — đổi thẳng có thể đè lên file khác đang chờ đổi tên
    # (vd đang có sẵn "1_a.mp4" mà file khác cũng sắp thành "1_...").
    temp_paths = []
    for i, name in enumerate(names):
        src = os.path.join(UPLOADED_IMAGE_DIR, name)
        tmp = os.path.join(UPLOADED_IMAGE_DIR, f".reorder_tmp_{i}_{name}")
        os.rename(src, tmp)
        temp_paths.append((tmp, name))

    renamed = []
    for i, (tmp, name) in enumerate(temp_paths):
        # Bỏ tiền tố số cũ (nếu có) để không bị chồng "1_2_tên.mp4" sau nhiều lần sắp lại.
        base = re.sub(r"^\d+_", "", name)
        final_name = f"{i + 1}_{base}"
        os.rename(tmp, os.path.join(UPLOADED_IMAGE_DIR, final_name))
        renamed.append(final_name)

    return jsonify({"success": True, "files": renamed})


@app.route("/api/images/delete", methods=["POST"])
def api_images_delete():
    """Xóa một hoặc nhiều ảnh đã upload."""
    data = request.json or {}
    filenames = data.get("filenames", [])
    if not filenames:
        return jsonify({"error": "Không có ảnh nào được chọn!"}), 400

    deleted = []
    for name in filenames:
        if not isinstance(name, str):
            continue
        safe_name = os.path.basename(name)
        ext = os.path.splitext(safe_name)[1].lower()
        if ext not in STUDIO_EXTENSIONS:
            continue

        img_path = os.path.join(UPLOADED_IMAGE_DIR, safe_name)
        if os.path.exists(img_path):
            os.remove(img_path)
            deleted.append(safe_name)

    return jsonify({"success": True, "deleted": deleted})


@app.route("/api/music", methods=["GET"])
def api_music():
    """Trả về danh sách nhạc nền trong thư viện."""
    return jsonify(_list_media(MUSIC_DIR, MUSIC_EXTENSIONS))


@app.route("/api/music/upload", methods=["POST"])
def api_music_upload():
    """Upload một hoặc nhiều file nhạc vào thư viện."""
    files = request.files.getlist("tracks")
    if not files:
        return jsonify({"error": "Không có file nhạc nào được gửi lên!"}), 400

    os.makedirs(MUSIC_DIR, exist_ok=True)
    uploaded = []
    rejected = []

    for f in files:
        original_name = (f.filename or "").strip()
        if not original_name:
            continue

        safe_name = secure_filename(original_name)
        ext = os.path.splitext(safe_name)[1].lower()
        if ext not in MUSIC_EXTENSIONS:
            rejected.append(original_name)
            continue

        final_name = _next_available_filename(MUSIC_DIR, safe_name)
        save_path = os.path.join(MUSIC_DIR, final_name)
        f.save(save_path)
        uploaded.append(final_name)

    if not uploaded:
        return jsonify({
            "error": "Không có file nhạc hợp lệ.",
            "rejected": rejected,
        }), 400

    return jsonify({"success": True, "uploaded": uploaded, "rejected": rejected})


@app.route("/api/music/delete", methods=["POST"])
def api_music_delete():
    """Xóa một hoặc nhiều file nhạc khỏi thư viện."""
    data = request.json or {}
    filenames = data.get("filenames", [])
    if not filenames:
        return jsonify({"error": "Không có file nhạc nào được chọn!"}), 400

    deleted = []
    for name in filenames:
        if not isinstance(name, str):
            continue
        safe_name = os.path.basename(name)
        ext = os.path.splitext(safe_name)[1].lower()
        if ext not in MUSIC_EXTENSIONS:
            continue

        music_path = os.path.join(MUSIC_DIR, safe_name)
        if os.path.exists(music_path):
            os.remove(music_path)
            deleted.append(safe_name)

    return jsonify({"success": True, "deleted": deleted})


def run_pipeline(
    job_id: str,
    script_file: str,
    uploaded_images: list,
    music_mode: str,
    audio_cfg: AudioConfig,
    sub_cfg: SubtitleConfig,
    output_file: str,
    text_only: bool = False,
):
    """Tiến trình tạo video chạy nền."""
    update_job_status(job_id, "processing", 10, "Đang tạo giọng đọc...")

    # Mỗi job có thư mục temp riêng — 2 job chạy song song không ghi đè file của nhau
    job_temp = os.path.join("temp", job_id)
    active_jobs.add(job_id)

    try:
        if job_id in cancelled_jobs:
            raise Exception("Job cancelled by user")

        os.makedirs(job_temp, exist_ok=True)
        os.makedirs("output", exist_ok=True)

        # Nếu script_file chứa nội dung kịch bản (không phải tên file)
        if len(script_file) > 50 or not script_file.endswith('.txt'):
            script_text = script_file
            script_path = os.path.join(job_temp, "script.txt")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_text)
        else:
            script_path = script_file
            if os.path.exists(script_path):
                with open(script_path, "r", encoding="utf-8") as f:
                    script_text = f.read().strip()
            else:
                script_text = ""

        if job_id in cancelled_jobs:
            raise Exception("Job cancelled by user")

        # Bước 1: TTS
        from core.engines.tts import run_tts
        audio_path = os.path.join(job_temp, "audio.mp3")
        srt_path = os.path.join(job_temp, "subtitles.srt")

        used_voice = run_tts(script_path, audio_path, srt_path, rate=audio_cfg.rate, voice=audio_cfg.voice)
        # Báo rõ nếu giọng bị đổi so với lựa chọn — nếu im lặng thì người dùng tưởng 2 giọng
        # khác nhau lại nghe y hệt (đã gặp: FPT 429 nên leminh âm thầm thành namminh).
        if used_voice and used_voice != audio_cfg.voice:
            update_job_status(job_id, "processing", 28,
                              f"⚠️ Giọng '{audio_cfg.voice}' không dùng được, đã thay bằng '{used_voice}'")
        update_job_status(job_id, "processing", 30, "Đang chuẩn bị video nền...")

        if job_id in cancelled_jobs:
            raise Exception("Job cancelled by user")

        # Bước 2: Kiểm tra ảnh/video đã upload (vd clip Google Flow) có sẵn để render
        image_dir = UPLOADED_IMAGE_DIR
        os.makedirs(image_dir, exist_ok=True)

        if job_id in cancelled_jobs:
            raise Exception("Job cancelled by user")

        # Chế độ chữ động dựng nền bằng gradient nên KHÔNG cần clip nào — bỏ qua kiểm tra này,
        # nếu không thì bật chế độ đó mà Media Nền trống là bị chặn oan ngay từ đầu.
        studio_media = [f for f in os.listdir(image_dir) if f.lower().endswith(STUDIO_EXTENSIONS)]
        if not studio_media and not text_only:
            raise FileNotFoundError(
                "Chưa có ảnh/video nào trong Media Nền. Dùng trợ lý 'Hoạt hình Veo thủ công' để "
                "sinh prompt, tạo clip bằng Google Flow rồi upload vào."
            )

        update_job_status(job_id, "processing", 50, "Đang render video...")

        # Bước 3: Render
        bgm_dir = MUSIC_DIR
        os.makedirs(bgm_dir, exist_ok=True)
        # Dọn nhạc auto_ cũ — chỉ khi không có job nào khác đang chạy (tránh xoá nhạc job kia đang dùng)
        if len(active_jobs) <= 1:
            for f in os.listdir(bgm_dir):
                if f.startswith("auto_"):
                    try: os.remove(os.path.join(bgm_dir, f))
                    except Exception: pass
        bgm_files = [f for f in os.listdir(bgm_dir) if f.lower().endswith(MUSIC_EXTENSIONS)]
        bgm_path = None

        if music_mode == "manual":
            if audio_cfg.bgm_path:
                requested_path = os.path.join(bgm_dir, audio_cfg.bgm_path)
                if os.path.exists(requested_path):
                    bgm_path = requested_path
            if bgm_path is None and bgm_files:
                bgm_path = os.path.join(bgm_dir, random.choice(bgm_files))

        elif music_mode == "ai_local":
            from core.engines.music_finder import pick_local_music_for_script
            bgm_path = pick_local_music_for_script(script_text, bgm_dir)
            if bgm_path is None and bgm_files:
                bgm_path = os.path.join(bgm_dir, random.choice(bgm_files))

        if bgm_path:
            update_job_status(job_id, "processing", 50, f"Đang render video... (BGM: {os.path.basename(bgm_path)})")
        else:
            update_job_status(job_id, "processing", 50, "Đang render video... (không có BGM)")

        def progress_cb(pct, msg):
            if job_id in cancelled_jobs:
                raise Exception("Job cancelled by user")
            update_job_status(job_id, "processing", pct, msg)

        from core.engines.html_video_maker import make_video_gsap
        final_video = make_video_gsap(
            audio_path=audio_path,
            srt_path=srt_path,
            output_path=output_file,
            style=sub_cfg.style,
            position=sub_cfg.position,
            bgm_path=bgm_path,
            bgm_start_sec=audio_cfg.bgm_start_sec,
            bgm_volume=audio_cfg.bgm_volume,
            image_dir=image_dir,
            uploaded_images=uploaded_images,
            progress_callback=progress_cb,
            text_only=text_only,
        )

        if job_id in cancelled_jobs:
            raise Exception("Job cancelled by user")
        update_job_status(job_id, "completed", 100, f"✅ Hoàn tất! Video: {final_video}", output_file=final_video)
        try: cancelled_jobs.remove(job_id)
        except KeyError: pass

    except Exception as e:
        import traceback
        traceback.print_exc()
        if job_id in cancelled_jobs:
            update_job_status(job_id, "failed", 0, "❌ Đã dừng tạo video theo yêu cầu.", error="Cancelled by user")
            try: cancelled_jobs.remove(job_id)
            except KeyError: pass
        else:
            update_job_status(job_id, "failed", 0, f"❌ Lỗi: {str(e)}", error=str(e))
    finally:
        active_jobs.discard(job_id)
        # Dọn toàn bộ temp riêng của job (script, audio, srt, backgrounds đã tải)
        import shutil
        if os.path.isdir(job_temp):
            try:
                shutil.rmtree(job_temp)
            except OSError as e:
                logger.info(f"⚠️ Không dọn được {job_temp}: {e}")


@app.route("/api/pipeline/start", methods=["POST"])
def api_pipeline_start():
    """Bắt đầu pipeline tạo video (chạy nền)."""
    data = request.json or {}
    voice = data.get("voice", "vi-VN-HoaiMyNeural")
    rate = data.get("rate", "+50%")
    style = data.get("style", 1)
    position = data.get("position", "bottom")
    uploaded_images = data.get("uploaded_images", [])
    music_file = data.get("music_file")
    music_offset_sec = data.get("music_offset_sec", 0)
    music_volume = data.get("music_volume", 0.22)
    music_mode = data.get("music_mode", "manual")
    script_file = data.get("script", "script.txt")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    # Thêm hậu tố ngẫu nhiên để 2 job start cùng giây không ghi đè file nhau
    output_file = data.get("output", f"output/video_{timestamp}_{uuid.uuid4().hex[:6]}.mp4")

    if not isinstance(uploaded_images, list):
        uploaded_images = []

    if music_mode not in ("manual", "ai_local"):
        music_mode = "manual"

    try:
        music_offset_sec = _parse_time_offset_to_seconds(music_offset_sec)
    except (TypeError, ValueError):
        return jsonify({"error": "Thời gian bắt đầu nhạc không hợp lệ. Dùng mm:ss hoặc hh:mm:ss"}), 400

    music_volume = _parse_music_volume(music_volume, default=0.22)

    if isinstance(music_file, str):
        music_file = os.path.basename(music_file)
    else:
        music_file = None

    # Chỉ giữ tên file an toàn để tránh path traversal.
    uploaded_images = [os.path.basename(str(x)) for x in uploaded_images if str(x).strip()]

    # Khởi tạo Config Objects
    audio_cfg = AudioConfig(
        voice=voice,
        rate=rate,
        bgm_path=music_file,
        bgm_volume=music_volume,
        bgm_start_sec=music_offset_sec
    )
    sub_cfg = SubtitleConfig(
        style=int(style) if str(style).isdigit() else 1,
        position=position,
        overlay_opacity=0.35
    )

    # Chế độ chữ động: nền gradient + chữ to, không cần clip Veo tạo tay.
    text_only = bool(data.get("text_only"))

    job_id = str(uuid.uuid4())
    create_job(job_id, "queued", "Đang chờ...")

    # Gửi công việc vào ThreadPoolExecutor
    executor.submit(
        run_pipeline,
        job_id,
        script_file,
        uploaded_images,
        music_mode,
        audio_cfg,
        sub_cfg,
        output_file,
        text_only,
    )

    return jsonify({"success": True, "job_id": job_id, "message": "Pipeline đã bắt đầu chạy nền!"})


@app.route("/api/pipeline/stop", methods=["POST"])
@app.route("/api/pipeline/stop/<job_id>", methods=["POST"])
def api_pipeline_stop(job_id=None):
    """Dừng một job đang tạo video."""
    if not job_id:
        job = get_latest_job()
        if not job or job.get("status") not in ("queued", "processing"):
            return jsonify({"error": "Không có tiến trình nào đang chạy"}), 400
        job_id = job.get("job_id")

    cancelled_jobs.add(job_id)
    # Cập nhật ngay lập tức trạng thái trong database
    update_job_status(job_id, "failed", 0, "❌ Đã yêu cầu dừng tạo video...", error="Cancelled by user")
    return jsonify({"success": True, "message": f"Đã dừng tiến trình {job_id}"})


@app.route("/api/pipeline/status", methods=["GET"])
@app.route("/api/pipeline/status/<job_id>", methods=["GET"])
def api_pipeline_status(job_id=None):
    """Trả về trạng thái của job được yêu cầu hoặc job mới nhất để đảm bảo tương thích ngược."""
    if job_id:
        job = get_job(job_id)
        if not job:
            return jsonify({"error": "Job không tồn tại"}), 404
    else:
        job = get_latest_job()
        if not job:
            return jsonify({
                "running": False,
                "step": "",
                "progress": 0,
                "message": "Chưa có tiến trình nào được tạo",
                "output_file": None,
                "error": None
            })

    # Định dạng kết quả tương thích với UI cũ mong đợi
    running = job["status"] in ("queued", "processing")
    return jsonify({
        "job_id": job["job_id"],
        "running": running,
        "step": job["status"],
        "progress": job["progress"],
        "message": job["message"],
        "output_file": job["output_file"],
        "error": job["error"]
    })


@app.route("/api/stats", methods=["GET"])
def api_stats():
    """Trả về thống kê tổng quan."""
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    videos = glob.glob(os.path.join(output_dir, "*.mp4"))

    total_size = sum(os.path.getsize(f) for f in videos) if videos else 0

    ai_data = get_ai_usage()
    from core.engines.tts import get_fpt_chars_used
    return jsonify({
        "videos_created": len(videos),
        "total_size_mb": round(total_size / 1024 / 1024, 1),
        "fpt_chars_used": get_fpt_chars_used(),
        "fpt_chars_limit": 100000,
        "ai_used_today": ai_data["used"],
        "ai_limit": ai_data["limit"]
    })


@app.route("/api/quota/update", methods=["POST"])
def api_quota_update():
    """Cập nhật hạn mức AI từ UI."""
    data = request.json
    limit = data.get("limit", 10)
    update_ai_limit(limit)
    return jsonify({"success": True})

@app.route("/api/file/<path:filepath>")
def serve_file(filepath):
    """Serve file media — chỉ cho phép trong output/ và temp/ (chặn đọc .env, db...)."""
    allowed_dirs = [os.path.abspath("output"), os.path.abspath("temp")]
    abspath = os.path.abspath(filepath)
    if not any(abspath.startswith(d + os.sep) or abspath == d for d in allowed_dirs):
        return jsonify({"error": "Đường dẫn không hợp lệ"}), 403
    if os.path.isfile(abspath):
        return send_file(abspath)
    return jsonify({"error": "File not found"}), 404


# ============================================================
# VIDEO LIBRARY API
# ============================================================

from core.utils.logger_config import logger

@app.route("/api/affiliate/videos", methods=["GET"])
def api_affiliate_videos():
    """Danh sách video đã tạo trong output/."""
    out_dir = "output"
    os.makedirs(out_dir, exist_ok=True)

    files = glob.glob(os.path.join(out_dir, "*.mp4"))
    res = []
    for f in sorted(files, key=os.path.getmtime, reverse=True):
        cover = os.path.splitext(f)[0] + "_cover.jpg"
        res.append({
            "name": os.path.basename(f),
            "path": f,
            "cover": os.path.relpath(cover) if os.path.exists(cover) else None,
            "size_mb": round(os.path.getsize(f) / 1024 / 1024, 1),
            "created": time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(f)))
        })
    return jsonify(res)

@app.route("/api/affiliate/videos", methods=["DELETE"])
def api_affiliate_videos_delete():
    """Xoá video trong output/ (kèm file _cover.jpg nếu có)."""
    data = request.json or {}

    def _remove_with_cover(f):
        try:
            os.remove(f)
        except Exception:
            pass
        cover = os.path.splitext(f)[0] + "_cover.jpg"
        if os.path.exists(cover):
            try: os.remove(cover)
            except Exception: pass

    if data.get("all"):
        if os.path.exists("output"):
            for f in glob.glob(os.path.join("output", "*.mp4")):
                _remove_with_cover(f)
        return jsonify({"success": True, "message": "Đã xoá tất cả video"})

    paths = data.get("paths", [])
    path = data.get("path")
    if path and path not in paths:
        paths.append(path)

    if paths:
        output_root = os.path.abspath("output")
        for p in paths:
            # Chỉ cho phép xoá .mp4 nằm trong output/ — chặn traversal
            abspath = os.path.abspath(str(p))
            if not abspath.startswith(output_root + os.sep):
                continue
            if not abspath.lower().endswith(".mp4"):
                continue
            if os.path.exists(abspath):
                _remove_with_cover(abspath)
        return jsonify({"success": True})

    return jsonify({"error": "Không có file nào được chọn"}), 400

@app.route("/media/<folder>/<filename>")
def serve_media(folder, filename):
    """Serve media."""
    if folder != "output":
        return jsonify({"error": "Thư mục không hợp lệ"}), 400
    return send_from_directory(folder, filename)

if __name__ == "__main__":
    os.makedirs("frontend/dist", exist_ok=True)
    os.makedirs("temp", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    os.makedirs("audio_bg", exist_ok=True)
    os.makedirs(UPLOADED_IMAGE_DIR, exist_ok=True)

    from core.data.jobs_db import init_db, clean_stuck_jobs
    from core.data.ideas_db import init_ideas_table
    init_db()
    clean_stuck_jobs()
    init_ideas_table()

    logger.info("🎬 VideoMaker Pro - Web Server")
    logger.info("=" * 40)
    logger.info("🌐 Mở trình duyệt tại: http://localhost:5000")
    logger.info("=" * 40)
    
    import subprocess
    # Chỉ khởi chạy trình watch frontend khi chạy thực sự (không phải lần init đầu của reloader)
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        # Mỗi lần reloader restart (sửa file .py) đều chạy tới đây — nếu không kiểm tra
        # trước, tiến trình "vite build --watch" cũ bị bỏ mồ côi và chồng chất dần, có thể
        # gây ghi đè lẫn nhau vào frontend/dist khi nhiều watcher cùng rebuild.
        vite_watch_running = False
        try:
            import psutil
            for p in psutil.process_iter(["cmdline"]):
                cmdline = " ".join(p.info.get("cmdline") or [])
                if "vite" in cmdline and "watch" in cmdline:
                    vite_watch_running = True
                    break
        except ImportError:
            pass

        if vite_watch_running:
            logger.info("  [Frontend Watch] Đã có tiến trình vite watch đang chạy, bỏ qua khởi động lại.")
        else:
            logger.info("🚀 Khởi động Frontend Auto-build (Vite Watch)...")
            try:
                # Chạy nền npm run build -- --watch
                subprocess.Popen(
                    ["npm", "run", "build", "--", "--watch"],
                    cwd=os.path.join(os.path.dirname(__file__), "frontend"),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception as e:
                logger.info(f"⚠️ Lỗi khởi chạy frontend auto-build: {e}")

    app.run(debug=True, host="0.0.0.0", port=5000)
