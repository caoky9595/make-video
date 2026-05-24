"""
bg_finder.py - Auto Background Video Finder (Pexels API)
=========================================================
Tự động tìm và tải video nền phù hợp với nội dung kịch bản từ Pexels.
API Key miễn phí, không giới hạn, không watermark.

Đăng ký API Key tại: https://www.pexels.com/api/
"""

import os
import re
import requests
import random
import urllib.parse
from dotenv import load_dotenv
from core.utils.logger_config import logger

# Tải biến môi trường từ file .env
load_dotenv()

PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")

# Cấu hình Video Nền Thôi Miên (Satisfying Loops) dành riêng cho Kênh kể truyện
# Thay vì lấy cảnh văn phòng nhàm chán, hệ thống sẽ ưu tiên trích xuất Lofi chill
# Fallback: Ưu tiên video Cinematic nếu Gemini lỗi
FALLBACK_KEYWORDS = [
    "cinematic landscape 4k",
    "abstract colorful motion",
    "calm nature 4k vertical",
    "cyberpunk city aesthetic",
    "minimalist clean background",
]

def generate_visual_keywords_with_gemini(script_text):
    """Sử dụng Gemini để phân tích kịch bản và sinh từ khóa Pexels theo 3 ngách thịnh hành."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return ["cinematic background"]
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
    prompt = f"""Bạn là một chuyên gia thiết kế hình ảnh TikTok triệu view.
    Hãy phân tích kịch bản sau đây và tự động xếp nó vào 1 trong 3 nhóm (niche) sau:
    1. STORYTELLING ASMR: Kịch bản kể chuyện đời sống, tâm sự. Từ khóa đề xuất phải là video ASMR cuốn hút mắt (ví dụ: 'oddly satisfying kinetic sand cutting vertical', 'satisfying ASMR cleaning vertical', 'soap slicing vertical').
    2. LOFI PHILOSOPHY/STOIC: Kịch bản về triết lý, sự thật tâm lý học. Từ khóa phải có chiều sâu, lofi, hoài cổ (ví dụ: 'ancient greek statue dynamic shadow vertical', 'moody warm desk lamp aesthetic vertical', 'rainy window cozy lofi desk vertical').
    3. BUSINESS & MOTIVATION: Kịch bản về tiền bạc, thành công, affiliate. Từ khóa phải sang trọng, tạo động lực (ví dụ: 'luxury workspace setup vertical', 'typing on mechanical keyboard aesthetic vertical', 'cinematic city lights night timelapse vertical').

    Yêu cầu:
    - Đề xuất 5 cụm từ tìm kiếm video (bằng tiếng Anh) chi tiết, mang tính thẩm mỹ cao.
    - Luôn thêm từ khóa phụ trợ như 'vertical' hoặc 'portrait' vào từ khóa để tìm video dọc.
    - Trả về kết quả dưới dạng JSON array duy nhất: ["keyword1", "keyword2", ...]

    Kịch bản: {script_text[:1200]}
    """
    
    import urllib.request
    import json
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"response_mime_type": "application/json"}}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            content = result["candidates"][0]["content"]["parts"][0]["text"]
            keywords = json.loads(content)
            return keywords if isinstance(keywords, list) else ["cinematic background"]
    except Exception as e:
        logger.info(f"  [AI Keywords] Error: {e}")
        return ["cinematic background"]

def download_ai_image(prompt, output_dir="backgrounds"):
    """Tạo và tải ảnh AI từ Pollinations.ai (Miễn phí, không giới hạn)."""
    os.makedirs(output_dir, exist_ok=True)
    import random
    import urllib.parse
    
    # Làm cho prompt đa dạng và sang trọng hơn cho Affiliate
    seed = random.randint(1, 999999)
    # Thêm các modifier để ảnh trông "đắt tiền" và "sạch sẽ" hơn
    aesthetic_modifiers = "high-end photography, soft lighting, minimalist, clean composition, 8k resolution, cinematic color grading, vertical 9:16"
    safe_prompt = urllib.parse.quote(f"{prompt}, {aesthetic_modifiers}")
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1080&height=1920&seed={seed}&nologo=true"
    
    filename = f"ai_image_{seed}.jpg"
    filepath = os.path.join(output_dir, filename)
    
    logger.info(f"  [AI Image] Generating: {filename} for '{prompt}'...")
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(resp.content)
        logger.info(f"  [AI Image] ✅ Saved: {filename}")
        return filepath
    except Exception as e:
        logger.info(f"  [AI Image] Error: {e}")
        return None


def get_api_key():
    """Lấy Pexels API key từ biến môi trường (.env)."""
    api_key = os.getenv("PEXELS_API_KEY", "")

    if not api_key:
        logger.info("\n🔑 Cần Pexels API Key (miễn phí) để tự động tìm video nền.")
        logger.info("   Đăng ký tại: https://www.pexels.com/api/")
        logger.info("   Vui lòng thêm PEXELS_API_KEY vào file .env của bạn.\n")
        logger.info("   ⚠️  Không có API Key. Sẽ dùng video nền có sẵn trong backgrounds/")
        return None

    return api_key


def extract_keywords(script_text: str, max_keywords: int = 3):
    """
    Trích xuất từ khoá tiếng Anh từ kịch bản tiếng Việt để search trên Pexels.
    """
    script_lower = script_text.lower()
    matched = []

    # Tìm từ khoá mapping (Dùng regex để tránh bắt chữ chứa bên trong, VD: 'mạng' -> 'ma')
    import re
    for vn_regex, en_word in KEYWORD_MAP.items():
        if re.search(vn_regex, script_lower):
            matched.append(en_word)
            if len(matched) >= max_keywords:
                break

    if not matched:
        # Fallback: dùng lofi mặc định
        import random
        matched = [random.choice(FALLBACK_KEYWORDS)]

    return matched


def search_pixabay_videos(query: str, api_key: str, per_page: int = 5):
    """Tìm video trên Pixabay API."""
    if not api_key: return []
    url = "https://pixabay.com/api/videos/"
    params = {
        "key": api_key,
        "q": query,
        "video_type": "all",
        "per_page": per_page
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        return data.get("hits", [])
    except Exception:
        return []

def search_pexels_videos(query: str, api_key: str, orientation: str = "portrait", per_page: int = 5, exclude_ids=None):
    """
    Tìm video trên Pexels API và loại trừ các video đã sử dụng.
    """
    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": api_key}
    
    # Nếu có exclude_ids, yêu cầu nhiều kết quả hơn để sau khi lọc vẫn đủ dùng
    query_limit = 15 if exclude_ids else per_page
    params = {
        "query": query,
        "orientation": orientation,
        "per_page": query_limit,
        "size": "medium",
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        videos = data.get("videos", [])
        if exclude_ids:
            videos = [v for v in videos if v.get("id") not in exclude_ids]
        return videos[:per_page]
    except Exception as e:
        logger.info(f"  [Pexels] Error searching: {e}")
        return []


def download_pixabay_video(video_data: dict, output_dir: str = "backgrounds"):
    """Tải video từ Pixabay."""
    videos = video_data.get("videos", {})
    # Ưu tiên bản medium hoặc small mp4
    best_v = videos.get("medium") or videos.get("small") or videos.get("tiny")
    if not best_v: return None
    
    video_url = best_v["url"]
    filename = f"pixabay_{video_data['id']}.mp4"
    filepath = os.path.join(output_dir, filename)
    
    if os.path.exists(filepath): return filepath
    
    try:
        resp = requests.get(video_url, stream=True, timeout=60)
        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return filepath
    except Exception:
        return None

def download_video(video_data: dict, output_dir: str = "backgrounds"):
    """
    Tải video từ Pexels về thư mục backgrounds.

    Args:
        video_data: Video object từ Pexels API
        output_dir: Thư mục lưu video

    Returns:
        Đường dẫn file đã tải, hoặc None nếu thất bại
    """
    os.makedirs(output_dir, exist_ok=True)

    # Tìm file video chất lượng dọc cao cấp
    video_files = video_data.get("video_files", [])
    best_file = None

    # Lần 1: Tìm video dọc Full HD trở lên (h > w và h >= 1080)
    for vf in video_files:
        w = vf.get("width", 0)
        h = vf.get("height", 0)
        if vf.get("file_type") == "video/mp4" and h > w and h >= 1080:
            best_file = vf
            break

    # Lần 2: Tìm video dọc HD (h > w và h >= 720)
    if not best_file:
        for vf in video_files:
            w = vf.get("width", 0)
            h = vf.get("height", 0)
            if vf.get("file_type") == "video/mp4" and h > w and h >= 720:
                best_file = vf
                break

    # Lần 3: Tìm video dọc bất kỳ
    if not best_file:
        for vf in video_files:
            w = vf.get("width", 0)
            h = vf.get("height", 0)
            if vf.get("file_type") == "video/mp4" and h > w:
                best_file = vf
                break

    # Lần 4: Fallback lấy file mp4 đầu tiên
    if not best_file:
        for vf in video_files:
            if vf.get("file_type") == "video/mp4":
                best_file = vf
                break

    if not best_file:
        logger.info("  [Pexels] No suitable video file found.")
        return None

    video_url = best_file["link"]
    video_id = video_data.get("id", "unknown")
    filename = f"pexels_{video_id}.mp4"
    filepath = os.path.join(output_dir, filename)

    # Không tải lại nếu đã có
    if os.path.exists(filepath):
        logger.info(f"  [Pexels] Already downloaded: {filename}")
        return filepath

    logger.info(f"  [Pexels] Downloading: {filename} ({best_file.get('width')}x{best_file.get('height')})...")

    try:
        resp = requests.get(video_url, stream=True, timeout=60)
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        logger.info(f"  [Pexels] ✅ Downloaded: {filename} ({size_mb:.1f} MB)")
        return filepath
    except Exception as e:
        logger.info(f"  [Pexels] Download failed: {e}")
        return None


def find_and_download_background(script_text: str, output_dir: str = "backgrounds", max_downloads: int = 5):
    """
    Hàm chính nâng cấp: Nạp used_backgrounds.json -> Gemini Keywords -> Pexels Video (Lọc trùng) -> Pollinations AI Image (Fallback/Mix).
    """
    api_key = get_api_key()
    
    # Nạp danh sách IDs đã sử dụng từ used_backgrounds.json
    used_ids = []
    used_bg_file = "used_backgrounds.json"
    if os.path.exists(used_bg_file):
        try:
            import json
            with open(used_bg_file, "r") as f:
                used_ids = json.load(f)
                if not isinstance(used_ids, list):
                    used_ids = []
            logger.info(f"  [Visual Engine] Đã nạp {len(used_ids)} video IDs đã dùng để loại trừ.")
        except Exception as e:
            logger.info(f"  [Visual Engine] ⚠️ Không thể nạp used_backgrounds.json: {e}")
    
    # 1. Dùng Gemini để tạo từ khóa xịn
    logger.info("  [AI Visual] Đang phân tích kịch bản bằng Gemini...")
    keywords = generate_visual_keywords_with_gemini(script_text)
    logger.info(f"  [AI Visual] Từ khóa đề xuất: {keywords}")

    downloaded = []
    
    # 2. Thử tìm Video trên Pexels trước (truyền exclude_ids=used_ids)
    if api_key:
        for keyword in keywords[:3]: # Thử 3 từ khóa đầu cho video
            logger.info(f"  [Pexels] Đang tìm video cho: '{keyword}'...")
            videos = search_pexels_videos(keyword, api_key, per_page=3, exclude_ids=used_ids)
            
            for video in videos:
                path = download_video(video, output_dir)
                if path:
                    downloaded.append(path)
                    if len(downloaded) >= 3: # Lấy tối đa 3 video thực tế
                        break
            if len(downloaded) >= 3:
                break

    # 3. Luôn tạo thêm 2-3 Ảnh AI để đảm bảo tính độc nhất và không bị lặp
    logger.info("  [AI Image] Đang tạo thêm ảnh AI để video không bị nhàm chán...")
    for keyword in keywords[-3:]: # Dùng các từ khóa còn lại cho ảnh AI
        path = download_ai_image(keyword, output_dir)
        if path:
            downloaded.append(path)
        if len(downloaded) >= max_downloads:
            break

    if downloaded:
        logger.info(f"\n  [Visual Engine] ✅ Đã chuẩn bị {len(downloaded)} tài nguyên (Video thực tế + Ảnh AI).")
    else:
        logger.info(f"\n  [Visual Engine] ⚠️ Cảnh báo: Không tải được tài nguyên mới.")

    return downloaded


if __name__ == "__main__":
    # Test
    test_script = "Chào bạn, nếu bạn muốn kiếm tiền từ bán áo thun affiliate thì đây là bí quyết"
    find_and_download_background(test_script)
