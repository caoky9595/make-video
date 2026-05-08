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

load_dotenv()

app = Flask(__name__, static_folder="webapp", template_folder="webapp")
CORS(app)

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
    return send_from_directory("webapp", "index.html")


@app.route("/webapp/<path:filename>")
def serve_static(filename):
    return send_from_directory("webapp", filename)


# ============================================================
# API ENDPOINTS
# ============================================================

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
    prompt = f"""Bạn là một chuyên gia sáng tạo nội dung TikTok. Hãy viết một kịch bản video ngắn (khoảng 30-45 giây) dựa trên ý tưởng sau: "{idea}".
    
    Yêu cầu:
    - Bắt đầu bằng một Hook gây sự chú ý cực mạnh trong 3 giây đầu.
    - Lời thoại phải tự nhiên, cực kỳ lôi cuốn, hợp với Gen Z.
    - Kết thúc bằng một Call to Action (CTA) kêu gọi follow/comment.
    - CHỈ TRẢ VỀ nội dung lời thoại (không bao gồm mô tả cảnh quay, góc máy, nhạc...). Văn bản dùng để đọc bằng AI Voice nên hãy trình bày liền mạch, xuống dòng cho mỗi câu.
    """
    
    import urllib.request
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.7}}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            return jsonify({"text": text.strip()})
    except Exception as e:
        return jsonify({"error": f"Lỗi gọi Gemini AI: {str(e)}"}), 500

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


@app.route("/api/bgm", methods=["GET"])
def api_bgm():
    """Trả về danh sách nhạc nền có sẵn."""
    bgm_dir = "audio_bg"
    os.makedirs(bgm_dir, exist_ok=True)
    supported = (".mp3", ".wav", ".ogg")
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
    script_file = data.get("script", "script.txt")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_file = data.get("output", f"output/video_{timestamp}.mp4")

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
            os.makedirs(bg_dir, exist_ok=True)
            supported = (".mp4", ".mov", ".avi", ".mkv", ".webm")
            bg_videos = [f for f in os.listdir(bg_dir) if f.lower().endswith(supported)]

            if not bg_videos:
                with open(script_file, "r", encoding="utf-8") as f:
                    script_text = f.read()
                from bg_finder import find_and_download_background
                find_and_download_background(script_text, output_dir=bg_dir)

            pipeline_status.update({"step": "render", "progress": 50, "message": "Đang render video..."})

            # Bước 3: Render
            from video_maker import make_video
            bgm_dir = "audio_bg"
            os.makedirs(bgm_dir, exist_ok=True)
            bgm_files = [f for f in os.listdir(bgm_dir) if f.lower().endswith((".mp3", ".wav", ".ogg"))]
            bgm_path = os.path.join(bgm_dir, random.choice(bgm_files)) if bgm_files else None

            final_video = make_video(
                audio_path=audio_path,
                srt_path=srt_path,
                bg_dir=bg_dir,
                output_path=output_file,
                style=style,
                position=position,
                bgm_path=bgm_path,
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

    return jsonify({
        "videos_created": len(videos),
        "total_size_mb": round(total_size / 1024 / 1024, 1),
        "fpt_chars_used": 503,  # TODO: track in persistent storage
        "fpt_chars_limit": 100000,
    })


@app.route("/api/file/<path:filepath>")
def serve_file(filepath):
    """Serve bất kỳ file nào từ project."""
    if os.path.exists(filepath):
        return send_file(filepath)
    return jsonify({"error": "File not found"}), 404


if __name__ == "__main__":
    os.makedirs("webapp", exist_ok=True)
    os.makedirs("temp", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    os.makedirs("backgrounds", exist_ok=True)
    os.makedirs("audio_bg", exist_ok=True)

    print("🎬 VideoMaker Pro - Web Server")
    print("=" * 40)
    print("🌐 Mở trình duyệt tại: http://localhost:5000")
    print("=" * 40)
    app.run(debug=True, host="0.0.0.0", port=5000)
