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
import threading
import time
import glob
import random

from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import asyncio

load_dotenv()

import uuid
from concurrent.futures import ThreadPoolExecutor
from core.data.models import AudioConfig, SubtitleConfig, RenderConfig, VideoJobPayload
from core.data.jobs_db import init_db, create_job, update_job_status, get_job, get_latest_job

init_db()
executor = ThreadPoolExecutor(max_workers=2)

app = Flask(__name__, static_folder="frontend/dist", static_url_path="")
CORS(app)

UPLOADED_IMAGE_DIR = "uploaded_images"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".webm")
STUDIO_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS
MUSIC_DIR = "audio_bg"
MUSIC_EXTENSIONS = (".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac", ".webm")
QUOTA_FILE = "temp/quota_stats.json"

def get_ai_usage():
    """Lấy số lượt đã dùng AI trong ngày và hạn mức."""
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

def update_ai_limit(limit):
    """Cập nhật hạn mức AI tối đa."""
    data = get_ai_usage()
    data["limit"] = int(limit)
    with open(QUOTA_FILE, "w") as f:
        json.dump(data, f)
    return data

def increment_ai_usage():
    """Tăng số lượt đã dùng AI."""
    data = get_ai_usage()
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

import uuid


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
    rate = data.get("rate", "+20%")

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
    """Lưu kịch bản vào file."""
    data = request.json
    text = data.get("text", "")
    filename = data.get("filename", "script.txt")

    with open(filename, "w", encoding="utf-8") as f:
        f.write(text)

    char_count = len(text)
    return jsonify({"success": True, "chars": char_count, "filename": filename})


@app.route("/api/script/generate", methods=["POST"])
def api_script_generate():
    """Tạo kịch bản bằng AI Gemini từ ý tưởng."""
    data = request.json
    idea = data.get("idea", "").strip()
    if not idea:
        idea = "Một mẹo vặt nhà bếp hữu ích bất ngờ mà ít người biết (bảo quản thực phẩm, khử mùi, dọn dẹp nhanh) (Random)"
        
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return jsonify({"error": "Chưa cấu hình GEMINI_API_KEY trong file .env"}), 400

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
    mode = data.get("mode", "affiliate")
    
    if mode == "viral":
        prompt = f"""Bạn là Chuyên gia Nội dung TikTok ngách Mẹo Vặt Nhà Bếp & Gia Đình, chuyên kéo VIEW và FOLLOW cho kênh mới (giai đoạn xây kênh, chưa bán hàng).
        Nhiệm vụ: Biến ý tưởng "{idea}" thành kịch bản video mẹo vặt thuần giá trị, tối ưu để người xem LƯU lại và BẤM FOLLOW.

        Quy tắc Chế độ GIÁ TRỊ (XÂY FOLLOW — KHÔNG BÁN HÀNG):
        1. **KHÔNG bán hàng**, không nhắc sản phẩm/thương hiệu cụ thể, không CTA giỏ hàng.
        2. Mẹo phải THỰC SỰ hữu ích, bất ngờ, làm theo được ngay. Không bịa, không phóng đại (tránh vi phạm chính sách misleading).
        3. **Hook 2-3 giây đầu là quan trọng nhất**: dùng "pattern interrupt" — chỉ ra một lỗi sai hầu hết mọi người mắc, hoặc một kết quả bất ngờ ("99% mọi người cất hành tỏi sai cách...", "Đừng vứt vỏ chuối, vì...").
        4. Thân bài: nói thẳng vào mẹo, từng bước rõ ràng, không lan man.
        5. **Kết thúc bằng 1 câu chốt kéo tương tác**: ưu tiên kêu gọi LƯU video ("Lưu lại kẻo lúc cần không tìm thấy nha") hoặc gợi mở series để FOLLOW ("Theo dõi để xem mẹo bếp mỗi ngày", "Mai mình chỉ tiếp mẹo khử mùi tủ lạnh").
        6. Độ dài lời thoại: đọc trong 15-22 giây (khoảng 45-70 từ). NGẮN luôn tốt hơn DÀI cho retention.

        Cấu trúc: Hook gây sốc/lỗi sai -> Mẹo cụ thể từng bước -> Câu chốt kêu gọi Lưu/Follow.
        Quy tắc: NGẮN, GẮT, THẤM, văn nói tự nhiên. CHỈ TRẢ VỀ lời thoại, không kèm mô tả cảnh quay hay timestamp.
        """
    else:
        prompt = f"""Bạn là một Chuyên gia bán hàng Affiliate TikTok Shop ngách Đồ Gia Dụng & Nhà Bếp Thông Minh.
        Nhiệm vụ: Biến ý tưởng "{idea}" thành kịch bản video 15-20 giây bán hàng qua giỏ hàng TikTok Shop.
        Bối cảnh: video sẽ ghép với FOOTAGE THẬT quay sản phẩm bằng điện thoại (tay thao tác + sản phẩm, không lộ mặt), nên lời thoại phải bám sát thao tác demo được bằng tay.

        Quy tắc Chế độ AFFILIATE (BÁN HÀNG):
        1. **Hook 2-3 giây:** nêu đúng MỘT nỗi đau cụ thể khi nấu ăn/dọn dẹp mà sản phẩm giải quyết.
        2. **Thân 10-14 giây:** mô tả sản phẩm đang được demo giải quyết nỗi đau đó như thế nào. Chỉ nói công dụng THẬT, kiểm chứng được — TUYỆT ĐỐI không phóng đại hay bịa tính năng (vi phạm = đóng băng hoa hồng).
        3. **CTA 2-3 giây cuối:** điều hướng giỏ hàng, ví dụ "Giỏ hàng góc trái màn hình nha".
        4. Giọng văn tự nhiên như đang nói chuyện với bạn, không như đọc quảng cáo.
        5. Tổng độ dài lời thoại: 50-70 từ (đọc trong 15-20 giây).

        Cấu trúc: Hook nỗi đau -> Demo giải pháp -> CTA giỏ hàng.
        Quy tắc: NGẮN, GẮT, THẤM. CHỈ TRẢ VỀ lời thoại, không kèm mô tả cảnh quay hay timestamp.
        """
    
    import urllib.request
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.8}}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            return jsonify({"text": text.strip()})
    except Exception as e:
        return jsonify({"error": f"Lỗi gọi Gemini AI: {str(e)}"}), 500

@app.route("/api/ideas/generate", methods=["GET"])
def api_ideas_generate():
    """Gợi ý 5 ý tưởng viral và sản phẩm affiliate phù hợp."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return jsonify({"error": "Chưa cấu hình API Key"}), 400
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
    prompt = """Bạn là chuyên gia nội dung TikTok ngách Mẹo Vặt Nhà Bếp & Gia Đình tại Việt Nam, đang giúp một kênh MỚI xây follower (giai đoạn 1, chưa bán hàng).
    Hãy đề xuất 5 ý tưởng video mẹo vặt ngắn (15-22s) cho kênh faceless (stock/AI visual + giọng đọc AI), tối ưu để kéo VIEW và FOLLOW.
    Yêu cầu:
    1. TẤT CẢ là mẹo vặt thuần giá trị, KHÔNG bán hàng, không nhắc sản phẩm cụ thể.
    2. Mỗi mẹo phải hữu ích bất ngờ, ai cũng làm được tại nhà, dễ khiến người xem muốn LƯU lại.
    3. Mỗi ý tưởng nêu rõ HOOK gây tò mò ở câu đầu (chỉ ra lỗi sai phổ biến hoặc kết quả bất ngờ).
    4. Định dạng: "[Mẹo bếp/Mẹo dọn dẹp/Mẹo bảo quản] Hook... -> nội dung mẹo ngắn".
    5. CHỈ TRẢ VỀ JSON array: ["ý tưởng 1", "ý tưởng 2", ...]
    """
    
    import urllib.request
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"response_mime_type": "application/json"}}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            content = result["candidates"][0]["content"]["parts"][0]["text"]
            ideas = json.loads(content)
            return jsonify({"ideas": ideas})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/script/load", methods=["GET"])
def api_script_load():
    """Đọc nội dung kịch bản hiện tại."""
    filename = request.args.get("filename", "script.txt")
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            text = f.read()
        return jsonify({"text": text, "chars": len(text)})
    return jsonify({"text": "", "chars": 0})


@app.route("/api/backgrounds", methods=["GET"])
def api_backgrounds():
    """Trả về danh sách video nền có sẵn."""
    bg_dir = "backgrounds"
    os.makedirs(bg_dir, exist_ok=True)
    supported = (".mp4", ".mov", ".avi", ".mkv", ".webm")
    files = [f for f in os.listdir(bg_dir) if f.lower().endswith(supported)]
    return jsonify([{
        "name": f,
        "path": os.path.join(bg_dir, f),
        "size_mb": round(os.path.getsize(os.path.join(bg_dir, f)) / 1024 / 1024, 1),
    } for f in files])


@app.route("/api/images", methods=["GET"])
def api_images():
    """Trả về danh sách tài nguyên (ảnh/video) đã upload cho Studio."""
    return jsonify(_list_media(UPLOADED_IMAGE_DIR, STUDIO_EXTENSIONS))


@app.route("/api/images/upload", methods=["POST"])
def api_images_upload():
    """Upload một hoặc nhiều ảnh/video vào thư viện Studio."""
    files = request.files.getlist("images")
    if not files:
        return jsonify({"error": "Không có file nào được gửi lên!"}), 400

    os.makedirs(UPLOADED_IMAGE_DIR, exist_ok=True)
    uploaded = []
    rejected = []

    for f in files:
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
        uploaded.append(final_name)

    if not uploaded:
        return jsonify({
            "error": "Không có file hợp lệ. Hỗ trợ Ảnh (JPG/PNG/WEBP) và Video (MP4/MOV...).",
            "rejected": rejected,
        }), 400

    return jsonify({"success": True, "uploaded": uploaded, "rejected": rejected})


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


@app.route("/api/bgm", methods=["GET"])
def api_bgm():
    """Trả về danh sách nhạc nền có sẵn."""
    bgm_dir = "audio_bg"
    os.makedirs(bgm_dir, exist_ok=True)
    supported = MUSIC_EXTENSIONS
    files = [f for f in os.listdir(bgm_dir) if f.lower().endswith(supported)]
    return jsonify([{
        "name": f,
        "path": os.path.join(bgm_dir, f),
        "size_mb": round(os.path.getsize(os.path.join(bgm_dir, f)) / 1024 / 1024, 1),
    } for f in files])


@app.route("/api/outputs", methods=["GET"])
def api_outputs():
    """Trả về danh sách video đã xuất."""
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    files = glob.glob(os.path.join(output_dir, "*.mp4"))
    result = []
    for f in sorted(files, key=os.path.getmtime, reverse=True):
        stat = os.stat(f)
        name = os.path.basename(f)
        cover = f.rsplit(".", 1)[0] + "_cover.jpg"
        result.append({
            "name": name,
            "path": f,
            "cover": cover if os.path.exists(cover) else None,
            "size_mb": round(stat.st_size / 1024 / 1024, 1),
            "created": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)),
        })
    return jsonify(result)


@app.route("/api/outputs/delete", methods=["POST"])
def api_outputs_delete():
    """Xóa một hoặc nhiều video."""
    data = request.json
    filenames = data.get("filenames", [])
    if not filenames:
        return jsonify({"error": "Không có file nào được chọn!"}), 400

    deleted = []
    for name in filenames:
        video_path = os.path.join("output", name)
        cover_path = video_path.rsplit(".", 1)[0] + "_cover.jpg"
        
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
            if os.path.exists(cover_path):
                os.remove(cover_path)
            deleted.append(name)
        except Exception as e:
            logger.info(f"Error deleting {name}: {e}")

    return jsonify({"success": True, "deleted": deleted})


@app.route("/api/outputs/delete_all", methods=["POST"])
def api_outputs_delete_all():
    """Xóa toàn bộ video trong thư mục output."""
    output_dir = "output"
    try:
        files = glob.glob(os.path.join(output_dir, "*"))
        for f in files:
            os.remove(f)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def run_pipeline(
    job_id: str,
    script_file: str,
    visual_mode: str,
    uploaded_images: list,
    music_mode: str,
    audio_cfg: AudioConfig,
    sub_cfg: SubtitleConfig,
    render_cfg: RenderConfig,
    output_file: str
):
    """Tiến trình tạo video chạy nền."""
    update_job_status(job_id, "processing", 10, "Đang tạo giọng đọc...")
    
    try:
        # Nếu script_file chứa nội dung kịch bản (không phải tên file)
        if len(script_file) > 50 or not script_file.endswith('.txt'):
            script_text = script_file
            with open("temp/script.txt", "w", encoding="utf-8") as f:
                f.write(script_text)
            script_path = "temp/script.txt"
        else:
            script_path = script_file
            if os.path.exists(script_path):
                with open(script_path, "r", encoding="utf-8") as f:
                    script_text = f.read().strip()
            else:
                script_text = ""

        # Bước 1: TTS
        from core.engines.tts import run_tts
        audio_path = "temp/audio.mp3"
        srt_path = "temp/subtitles.srt"
        os.makedirs("temp", exist_ok=True)
        os.makedirs("output", exist_ok=True)

        run_tts(script_path, audio_path, srt_path, rate=audio_cfg.rate, voice=audio_cfg.voice)
        update_job_status(job_id, "processing", 30, "Đang chuẩn bị video nền...")

        # Bước 2: Chuẩn bị tài nguyên hình ảnh/video bằng AI Visual Engine
        bg_dir = "backgrounds"
        image_dir = UPLOADED_IMAGE_DIR
        os.makedirs(bg_dir, exist_ok=True)
        os.makedirs(image_dir, exist_ok=True)

        # Nâng cấp: Xóa tài nguyên cũ để đảm bảo video luôn mới
        if os.path.exists(bg_dir):
            for f in os.listdir(bg_dir):
                if f.startswith("ai_image_") or f.startswith("pexels_") or f.startswith("pixabay_"):
                    try: os.remove(os.path.join(bg_dir, f))
                    except Exception: pass

        from core.engines.bg_finder import find_and_download_background
        update_job_status(job_id, "processing", 30, "Đang tự vẽ bối cảnh bằng AI...")
        new_assets = find_and_download_background(script_text, output_dir=bg_dir)
        
        # Chỉ lấy những file vừa tải/vẽ xong
        bg_videos = [os.path.basename(f) for f in new_assets]
        downloaded_bg_assets = new_assets
        studio_images = [f for f in os.listdir(image_dir) if f.lower().endswith(IMAGE_EXTENSIONS)]

        if visual_mode == "uploaded" and not studio_images:
            raise FileNotFoundError("Bạn đã chọn 'Chỉ dùng ảnh upload' nhưng chưa có ảnh nào.")

        if visual_mode == "mix" and not (bg_videos or studio_images):
            raise FileNotFoundError("Không tìm thấy ảnh upload hoặc video Pexels/background để render.")

        update_job_status(job_id, "processing", 50, "Đang render video...")

        # Bước 3: Render
        from core.engines.video_maker import make_video
        bgm_dir = MUSIC_DIR
        os.makedirs(bgm_dir, exist_ok=True)
        # Dọn dẹp các nhạc nền tải tự động cũ (có tiền tố auto_)
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

        final_video = make_video(
            audio_path=audio_path,
            srt_path=srt_path,
            bg_dir=bg_dir,
            output_path=output_file,
            style=sub_cfg.style,
            position=sub_cfg.position,
            bgm_path=bgm_path,
            bgm_start_sec=audio_cfg.bgm_start_sec,
            bgm_volume=audio_cfg.bgm_volume,
            image_dir=image_dir,
            visual_mode=visual_mode,
            uploaded_images=uploaded_images if not downloaded_bg_assets else downloaded_bg_assets,
        )

        update_job_status(job_id, "completed", 100, f"✅ Hoàn tất! Video: {final_video}", output_file=final_video)

    except Exception as e:
        import traceback
        traceback.print_exc()
        update_job_status(job_id, "failed", 0, f"❌ Lỗi: {str(e)}", error=str(e))


@app.route("/api/pipeline/start", methods=["POST"])
def api_pipeline_start():
    """Bắt đầu pipeline tạo video (chạy nền)."""
    data = request.json or {}
    voice = data.get("voice", "vi-VN-HoaiMyNeural")
    rate = data.get("rate", "+0%")
    style = data.get("style", 1)
    position = data.get("position", "bottom")
    visual_mode = data.get("visual_mode", "pexels")
    uploaded_images = data.get("uploaded_images", [])
    music_file = data.get("music_file")
    music_offset_sec = data.get("music_offset_sec", 0)
    music_volume = data.get("music_volume", 0.22)
    music_mode = data.get("music_mode", "manual")
    script_file = data.get("script", "script.txt")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_file = data.get("output", f"output/video_{timestamp}.mp4")

    if visual_mode not in ("pexels", "mix", "uploaded", "ai"):
        visual_mode = "pexels"

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
    render_cfg = RenderConfig()

    job_id = str(uuid.uuid4())
    create_job(job_id, "queued", "Đang chờ...")

    # Gửi công việc vào ThreadPoolExecutor
    executor.submit(
        run_pipeline,
        job_id,
        script_file,
        visual_mode,
        uploaded_images,
        music_mode,
        audio_cfg,
        sub_cfg,
        render_cfg,
        output_file
    )

    return jsonify({"success": True, "job_id": job_id, "message": "Pipeline đã bắt đầu chạy nền!"})


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
    return jsonify({
        "videos_created": len(videos),
        "total_size_mb": round(total_size / 1024 / 1024, 1),
        "fpt_chars_used": 503,  # TODO: track in persistent storage
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
    """Serve bất kỳ file nào từ project."""
    if os.path.exists(filepath):
        return send_file(filepath)
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
        for p in paths:
            if os.path.exists(p):
                _remove_with_cover(p)
        return jsonify({"success": True})

    return jsonify({"error": "Không có file nào được chọn"}), 400

@app.route("/media/<folder>/<filename>")
def serve_media(folder, filename):
    """Serve media."""
    if folder != "output":
        return jsonify({"error": "Thư mục không hợp lệ"}), 400
    return send_from_directory(folder, filename)

@app.route("/api/background/fetch", methods=["POST"])
def api_background_fetch():
    """Api background fetch."""
    data = request.json
    url = data.get("url")
    if not url:
        return jsonify({"error": "Thiếu URL YouTube"}), 400
    
    from core.engines import bg_fetcher
    bg_fetcher.start_download_thread(url)
    return jsonify({"success": True, "message": "Đang tải video nền..."})


if __name__ == "__main__":
    os.makedirs("frontend/dist", exist_ok=True)
    os.makedirs("temp", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    os.makedirs("backgrounds", exist_ok=True)
    os.makedirs("audio_bg", exist_ok=True)
    os.makedirs(UPLOADED_IMAGE_DIR, exist_ok=True)

    from core.data.jobs_db import init_db, clean_stuck_jobs
    init_db()
    clean_stuck_jobs()

    logger.info("🎬 VideoMaker Pro - Web Server")
    logger.info("=" * 40)
    logger.info("🌐 Mở trình duyệt tại: http://localhost:5000")
    logger.info("=" * 40)
    
    import subprocess
    import sys
    # Chỉ khởi chạy trình watch frontend khi chạy thực sự (không phải lần init đầu của reloader)
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
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
