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

app = Flask(__name__, static_folder="webapp", template_folder="webapp")
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
    except:
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

affiliate_status = {
    "running": False,
    "task": "",
    "message": "",
    "progress": 0,
    "error": None
}


# ============================================================
# PAGES
# ============================================================

@app.route("/")
def index():
    return send_from_directory("webapp", "index.html")


@app.route("/webapp/<path:filename>")
def serve_static(filename):
    return send_from_directory("webapp", filename)


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
    from tts import EDGE_VOICES, FPT_VOICES
    voices = []
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
        from tts import run_tts
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
    idea = data.get("idea", "")
    if not idea:
        return jsonify({"error": "Vui lòng nhập ý tưởng!"}), 400
        
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return jsonify({"error": "Chưa cấu hình GEMINI_API_KEY trong file .env"}), 400

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
    mode = data.get("mode", "affiliate")
    
    if mode == "viral":
        prompt = f"""Bạn là một Chuyên gia Sáng tạo Nội dung Viral trên TikTok.
        Nhiệm vụ: Biến ý tưởng "{idea}" thành một video giá trị cao, thu hút triệu view.
        
        Quy tắc Chế độ VIRAL (CHỈ NỘI DUNG):
        1. **KHÔNG bán hàng**, không nhắc đến sản phẩm, không gắn link.
        2. Tập trung 100% vào việc mang lại kiến thức, sự tò mò hoặc cảm xúc mạnh.
        3. Dùng kỹ thuật "Pattern Interrupt" ở 3 giây đầu để gây sốc.
        4. Kết thúc bằng một câu hỏi để tăng bình luận.
        
        Cấu trúc: Hook mạnh -> Nội dung giá trị -> Câu hỏi tương tác.
        Quy tắc: NGẮN, GẮT, THẤM. CHỈ TRẢ VỀ lời thoại.
        """
    else:
        prompt = f"""Bạn là một Chuyên gia Tâm lý hành vi và Chiến lược gia TikTok triệu view. 
        Nhiệm vụ: Biến ý tưởng "{idea}" thành kịch bản video thôi miên người xem và lồng ghép sản phẩm Affiliate.
        
        Quy tắc Chế độ AFFILIATE (BÁN HÀNG):
        1. **80% Giá trị:** Nêu ra nỗi đau hoặc sự thật thú vị.
        2. **20% Giải pháp:** Lồng ghép sản phẩm như một bí mật hoặc lối thoát duy nhất.
        3. Hook phải là một "gáo nước lạnh" khiến người xem dừng lại.
        4. CTA tinh tế ở cuối video.
        
        Cấu trúc: Hook -> Body giá trị -> Affiliate Close.
        Quy tắc: NGẮN, GẮT, THẤM. CHỈ TRẢ VỀ lời thoại.
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
    prompt = """Bạn là một chuyên gia săn trend TikTok. Hãy đề xuất 5 ý tưởng video ngắn (dưới 60s) đang cực kỳ dễ viral. 
    Yêu cầu:
    1. Mỗi ý tưởng phải thuộc một ngách khác nhau (Sự thật bí ẩn, Triết lý phũ, Soft Life, Tech...).
    2. Gợi ý luôn sản phẩm Affiliate phù hợp cho mỗi ý tưởng.
    3. Định dạng trả về: Một danh sách các chuỗi ngắn gọn theo kiểu: "[Ngách] Ý tưởng... (Gợi ý bán: Sản phẩm X)"
    4. CHỈ TRẢ VỀ JSON array: ["ý tưởng 1", "ý tưởng 2", ...]
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
            print(f"Error deleting {name}: {e}")

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


@app.route("/api/pipeline/start", methods=["POST"])
def api_pipeline_start():
    """Bắt đầu pipeline tạo video (chạy nền)."""
    global pipeline_status

    if pipeline_status["running"]:
        return jsonify({"error": "Pipeline đang chạy!"}), 400

    data = request.json
    voice = data.get("voice", "hoaimy")
    rate = data.get("rate", "+20%")
    style = data.get("style", 1)
    position = data.get("position", "bottom")
    visual_mode = data.get("visual_mode", "pexels")
    uploaded_images = data.get("uploaded_images", [])
    music_file = data.get("music_file")
    music_offset_sec = data.get("music_offset_sec", 0)
    music_volume = data.get("music_volume", 0.22)
    music_mode = data.get("music_mode", "manual")
    video_mode = data.get("video_mode", "realistic") # choices: realistic, veo
    script_file = data.get("script", "script.txt")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_file = data.get("output", f"output/video_{timestamp}.mp4")

    if visual_mode not in ("pexels", "mix", "uploaded"):
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

    def run_pipeline():
        global pipeline_status
        pipeline_status = {
            "running": True,
            "step": "tts",
            "progress": 10,
            "message": "Đang tạo giọng đọc...",
            "output_file": None,
            "error": None,
        }

        try:
            with open(script_file, "r", encoding="utf-8") as f:
                script_text = f.read().strip()

            # Bước 1: TTS
            from tts import run_tts
            audio_path = "temp/audio.mp3"
            srt_path = "temp/subtitles.srt"
            os.makedirs("temp", exist_ok=True)
            os.makedirs("output", exist_ok=True)

            run_tts(script_file, audio_path, srt_path, rate=rate, voice=voice)
            pipeline_status.update({"step": "bg", "progress": 30, "message": "Đang chuẩn bị video nền..."})

            # Bước 2: Tìm BG nếu cần
            bg_dir = "backgrounds"
            image_dir = UPLOADED_IMAGE_DIR
            os.makedirs(bg_dir, exist_ok=True)
            os.makedirs(image_dir, exist_ok=True)
            supported = (".mp4", ".mov", ".avi", ".mkv", ".webm")
            bg_videos = []
            studio_images = []
            
            # Bước 2: Chuẩn bị tài nguyên hình ảnh/video bằng AI Visual Engine
            bg_dir = "backgrounds"
            image_dir = UPLOADED_IMAGE_DIR
            os.makedirs(bg_dir, exist_ok=True)
            os.makedirs(image_dir, exist_ok=True)
            supported = (".mp4", ".mov", ".avi", ".mkv", ".webm")

            # Nâng cấp: Xóa tài nguyên cũ để đảm bảo video luôn mới
            if os.path.exists(bg_dir):
                for f in os.listdir(bg_dir):
                    if f.startswith("ai_image_") or f.startswith("pexels_") or f.startswith("pixabay_"):
                        try: os.remove(os.path.join(bg_dir, f))
                        except: pass

            from bg_finder import find_and_download_background
            pipeline_status.update({"step": "bg", "progress": 30, "message": "Đang tự vẽ bối cảnh bằng AI..."})
            new_assets = find_and_download_background(script_text, output_dir=bg_dir)
            
            # Chỉ lấy những file vừa tải/vẽ xong
            bg_videos = [os.path.basename(f) for f in new_assets]
            downloaded_bg_assets = new_assets
            studio_images = [f for f in os.listdir(image_dir) if f.lower().endswith(IMAGE_EXTENSIONS)]

            if visual_mode == "uploaded" and not studio_images:
                raise FileNotFoundError("Bạn đã chọn 'Chỉ dùng ảnh upload' nhưng chưa có ảnh nào.")

                if visual_mode == "mix" and not (bg_videos or studio_images):
                    raise FileNotFoundError("Không tìm thấy ảnh upload hoặc video Pexels/background để render.")

            pipeline_status.update({"step": "render", "progress": 50, "message": "Đang render video..."})

            # Bước 3: Render
            from video_maker import make_video
            bgm_dir = MUSIC_DIR
            os.makedirs(bgm_dir, exist_ok=True)
            bgm_files = [f for f in os.listdir(bgm_dir) if f.lower().endswith(MUSIC_EXTENSIONS)]
            bgm_path = None

            if music_mode == "manual":
                if music_file:
                    requested_path = os.path.join(bgm_dir, music_file)
                    if os.path.exists(requested_path):
                        bgm_path = requested_path
                if bgm_path is None and bgm_files:
                    bgm_path = os.path.join(bgm_dir, random.choice(bgm_files))

            elif music_mode == "ai_local":
                from music_finder import pick_local_music_for_script
                bgm_path = pick_local_music_for_script(script_text, bgm_dir)
                if bgm_path is None and bgm_files:
                    bgm_path = os.path.join(bgm_dir, random.choice(bgm_files))

            if bgm_path:
                pipeline_status.update({
                    "step": "render",
                    "progress": 50,
                    "message": f"Đang render video... (BGM: {os.path.basename(bgm_path)})",
                })
            else:
                pipeline_status.update({
                    "step": "render",
                    "progress": 50,
                    "message": "Đang render video... (không có BGM)",
                })

            final_video = make_video(
                audio_path=audio_path,
                srt_path=srt_path,
                bg_dir=bg_dir,
                output_path=output_file,
                style=style,
                position=position,
                bgm_path=bgm_path,
                bgm_start_sec=music_offset_sec,
                bgm_volume=music_volume,
                image_dir=image_dir,
                visual_mode=visual_mode,
                uploaded_images=uploaded_images if not downloaded_bg_assets else downloaded_bg_assets,
                video_mode=video_mode,
            )

            pipeline_status.update({
                "running": False,
                "step": "done",
                "progress": 100,
                "message": f"✅ Hoàn tất! Video: {final_video}",
                "output_file": final_video,
            })

        except Exception as e:
            pipeline_status.update({
                "running": False,
                "step": "error",
                "progress": 0,
                "message": f"❌ Lỗi: {str(e)}",
                "error": str(e),
            })

    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()
    return jsonify({"success": True, "message": "Pipeline đã bắt đầu!"})


@app.route("/api/pipeline/status", methods=["GET"])
def api_pipeline_status():
    """Trả về trạng thái hiện tại của pipeline."""
    return jsonify(pipeline_status)


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
# AFFILIATE API (Nicks, Processing, Upload)
# ============================================================

import nick_manager

@app.route("/api/nicks", methods=["GET"])
def api_nicks_get():
    nicks = nick_manager.list_nicks()
    return jsonify(nicks)

@app.route("/api/nicks/add", methods=["POST"])
def api_nicks_add():
    data = request.json
    try:
        nick = nick_manager.add_nick(data.get("name"), data.get("username", ""), data.get("proxy", ""))
        return jsonify({"success": True, "nick": nick})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/nicks/login", methods=["POST"])
def api_nicks_login():
    data = request.json
    nick_name = data.get("name")
    if not nick_name:
        return jsonify({"error": "Thiếu tên nick"}), 400
    
    def run_login():
        try:
            import uploader
            uploader.login_tiktok(nick_name)
        except Exception as e:
            print(f"❌ Lỗi login: {e}")

    threading.Thread(target=run_login, daemon=True).start()
    return jsonify({"success": True, "message": "Đang mở trình duyệt..."})

@app.route("/api/nicks/remove", methods=["POST"])
def api_nicks_remove():
    data = request.json
    try:
        nick_manager.remove_nick(data.get("name"))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/affiliate/videos", methods=["GET"])
def api_affiliate_videos():
    proc_dir = "processed"
    os.makedirs(proc_dir, exist_ok=True)
    files = glob.glob(os.path.join(proc_dir, "*.mp4"))
    res = []
    for f in sorted(files, key=os.path.getmtime, reverse=True):
        res.append({
            "name": os.path.basename(f),
            "path": f,
            "size_mb": round(os.path.getsize(f) / 1024 / 1024, 1),
            "created": time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(f)))
        })
    return jsonify(res)

@app.route("/api/affiliate/process", methods=["POST"])
def api_affiliate_process():
    global affiliate_status
    if affiliate_status["running"]:
        return jsonify({"error": "Đang có task chạy nền!"}), 400

    data = request.json
    url = data.get("url")
    file_path = data.get("file")
    hook = data.get("hook")
    cta = data.get("cta")
    bg_music = data.get("bg_music")

    def run_proc():
        global affiliate_status
        affiliate_status = {"running": True, "task": "process", "progress": 10, "message": "Đang tải video..." if url else "Đang xử lý...", "error": None}
        try:
            from video_processor import download_video, process_video, process_local_video
            if url:
                raw = download_video(url)
                if not raw:
                    raise Exception("Tải video thất bại")
                affiliate_status["message"] = "Đang áp dụng biến đổi (FFmpeg)..."
                affiliate_status["progress"] = 50
                processed = process_video(raw, hook_text=hook, cta_text=cta, bg_music=bg_music)
            elif file_path:
                affiliate_status["message"] = "Đang áp dụng biến đổi video local..."
                affiliate_status["progress"] = 50
                processed = process_local_video(file_path, hook_text=hook, cta_text=cta, bg_music=bg_music)
            else:
                raise Exception("Thiếu URL hoặc File")

            if not processed:
                raise Exception("Xử lý video thất bại")

            affiliate_status.update({"running": False, "progress": 100, "message": f"✅ Xử lý xong!"})
        except Exception as e:
            affiliate_status.update({"running": False, "progress": 0, "message": f"❌ Lỗi: {str(e)}", "error": str(e)})

    threading.Thread(target=run_proc, daemon=True).start()
    return jsonify({"success": True, "message": "Bắt đầu xử lý..."})

@app.route("/api/affiliate/upload", methods=["POST"])
def api_affiliate_upload():
    global affiliate_status
    if affiliate_status["running"]:
        return jsonify({"error": "Đang có task chạy nền!"}), 400

    data = request.json
    video_path = data.get("video_path")
    nick_name = data.get("nick_name")
    title = data.get("title", "")
    tags = data.get("tags", "")

    def run_up():
        global affiliate_status
        affiliate_status = {"running": True, "task": "upload", "progress": 10, "message": f"Mở trình duyệt cho {nick_name}...", "error": None}
        try:
            from uploader import upload_video
            affiliate_status["progress"] = 30
            success = upload_video(video_path, title, tags, nick_name)
            if success:
                import nick_manager
                nick_manager.record_upload(nick_name, success=True)
                affiliate_status.update({"running": False, "progress": 100, "message": f"✅ Upload thành công cho {nick_name}!"})
            else:
                raise Exception("Upload thất bại. Có thể do popup bản quyền hoặc captcha.")
        except Exception as e:
            affiliate_status.update({"running": False, "progress": 0, "message": f"❌ Lỗi: {str(e)}", "error": str(e)})

    threading.Thread(target=run_up, daemon=True).start()
    return jsonify({"success": True, "message": "Bắt đầu upload..."})

@app.route("/api/affiliate/status", methods=["GET"])
def api_affiliate_status():
    return jsonify(affiliate_status)


@app.route("/api/affiliate/upload_queue", methods=["POST"])
def api_affiliate_upload_queue():
    global affiliate_status
    if affiliate_status["running"]:
        return jsonify({"error": "Đang có task chạy nền!"}), 400

    data = request.json
    jobs = data.get("jobs", [])
    if not jobs:
        return jsonify({"error": "Không có video nào trong hàng đợi!"}), 400

    def run_queue():
        global affiliate_status
        affiliate_status = {"running": True, "task": "upload_queue", "progress": 10, "message": f"Bắt đầu hàng đợi ({len(jobs)} video)...", "error": None}
        try:
            from uploader import upload_queue
            
            # Theo dõi process trong khi upload queue chạy. Để đơn giản upload_queue() chạy đồng bộ.
            results = upload_queue(jobs)
            
            # Ghi lại dữ liệu nick_manager
            import nick_manager
            for success_job in results.get("success", []):
                nick_manager.record_upload(success_job.get("nick_name"), success=True)
            for failed_job in results.get("failed", []):
                nick_manager.record_upload(failed_job.get("nick_name"), success=False)
                
            success_count = len(results.get("success", []))
            affiliate_status.update({
                "running": False, 
                "progress": 100, 
                "message": f"✅ Queue hoàn tất! Thành công {success_count}/{len(jobs)}"
            })
        except Exception as e:
            affiliate_status.update({"running": False, "progress": 0, "message": f"❌ Lỗi queue: {str(e)}", "error": str(e)})

    threading.Thread(target=run_queue, daemon=True).start()
    return jsonify({"success": True, "message": "Bắt đầu chạy upload queue..."})


@app.route("/api/affiliate/schedule", methods=["POST"])
def api_affiliate_schedule():
    """Lưu queue vào data/queue.json để scheduler.py chạy vào giờ vàng"""
    data = request.json
    jobs = data.get("jobs", [])
    if not jobs:
        return jsonify({"error": "Không có video nào trong hàng đợi!"}), 400

    queue_file = "data/queue.json"
    os.makedirs("data", exist_ok=True)
    
    current_queue = []
    if os.path.exists(queue_file):
        try:
            import json
            with open(queue_file, "r", encoding="utf-8") as f:
                current_queue = json.load(f)
        except Exception:
            pass
            
    current_queue.extend(jobs)
    
    import json
    with open(queue_file, "w", encoding="utf-8") as f:
        json.dump(current_queue, f, indent=4, ensure_ascii=False)
        
    return jsonify({"success": True, "message": f"Đã lên lịch {len(jobs)} video. Sẽ tự đăng vào giờ vàng!"})

if __name__ == "__main__":
    os.makedirs("webapp", exist_ok=True)
    os.makedirs("temp", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    os.makedirs("backgrounds", exist_ok=True)
    os.makedirs("audio_bg", exist_ok=True)
    os.makedirs(UPLOADED_IMAGE_DIR, exist_ok=True)
    os.makedirs("processed", exist_ok=True)
    os.makedirs("profiles", exist_ok=True)

    print("🎬 VideoMaker Pro - Web Server")
    print("=" * 40)
    print("🌐 Mở trình duyệt tại: http://localhost:5000")
    print("=" * 40)
    app.run(debug=True, host="0.0.0.0", port=5000)
