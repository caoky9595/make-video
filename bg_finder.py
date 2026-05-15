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
    """Sử dụng Gemini để tạo danh sách từ khóa hình ảnh chuyên nghiệp."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return ["cinematic background"]
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
    prompt = f"""Phân tích kịch bản sau và đề xuất 5 cụm từ tìm kiếm video/hình ảnh (bằng tiếng Anh) để làm nền cho video TikTok.
    Mục tiêu: Tạo ra hình ảnh mãn nhãn, sang trọng, có tính thẩm mỹ cao (Aesthetic) để bán hàng Affiliate.

    Yêu cầu:
    1. Các từ khóa phải tập trung vào không gian (vibe), ánh sáng và cảm xúc (ví dụ: 'soft morning sunlight in a minimal bedroom', 'sleek desk setup with warm desk lamp').
    2. Nếu kịch bản về triết lý, hãy dùng phong cách u tối, cổ điển (ví dụ: 'ancient greek statue in dramatic shadows', 'dark library with candle light').
    3. Trả về dưới dạng JSON array: ["keyword1", "keyword2", ...]
    
    Kịch bản: {script_text[:1000]}
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
        print(f"  [AI Keywords] Error: {e}")
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
    
    print(f"  [AI Image] Generating: {filename} for '{prompt}'...")
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(resp.content)
        print(f"  [AI Image] ✅ Saved: {filename}")
        return filepath
    except Exception as e:
        print(f"  [AI Image] Error: {e}")
        return None


def get_api_key():
    """Lấy Pexels API key từ biến môi trường (.env)."""
    api_key = os.getenv("PEXELS_API_KEY", "")

    if not api_key:
        print("\n🔑 Cần Pexels API Key (miễn phí) để tự động tìm video nền.")
        print("   Đăng ký tại: https://www.pexels.com/api/")
        print("   Vui lòng thêm PEXELS_API_KEY vào file .env của bạn.\n")
        print("   ⚠️  Không có API Key. Sẽ dùng video nền có sẵn trong backgrounds/")
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
    except:
        return []

def search_pexels_videos(query: str, api_key: str, orientation: str = "portrait", per_page: int = 5):
    """
    Tìm video trên Pexels API.

    Args:
        query: Từ khoá tìm kiếm (tiếng Anh)
        api_key: Pexels API Key
        orientation: "portrait" (dọc) cho TikTok
        per_page: Số lượng kết quả

    Returns:
        List các video object từ Pexels API
    """
    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": api_key}
    params = {
        "query": query,
        "orientation": orientation,
        "per_page": per_page,
        "size": "medium",
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("videos", [])
    except Exception as e:
        print(f"  [Pexels] Error searching: {e}")
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
    except:
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

    # Tìm file video chất lượng phù hợp (HD, không quá nặng)
    video_files = video_data.get("video_files", [])

    # Ưu tiên: HD (720p-1080p), định dạng mp4
    best_file = None
    for vf in video_files:
        w = vf.get("width", 0)
        h = vf.get("height", 0)
        quality = vf.get("quality", "")

        # Chọn video dọc (h > w) hoặc video HD
        if quality in ("hd", "sd") and vf.get("file_type") == "video/mp4":
            if best_file is None:
                best_file = vf
            elif h > w and h >= 720:  # Ưu tiên video dọc
                best_file = vf
                break

    if not best_file:
        # Fallback: lấy file mp4 đầu tiên
        for vf in video_files:
            if vf.get("file_type") == "video/mp4":
                best_file = vf
                break

    if not best_file:
        print("  [Pexels] No suitable video file found.")
        return None

    video_url = best_file["link"]
    video_id = video_data.get("id", "unknown")
    filename = f"pexels_{video_id}.mp4"
    filepath = os.path.join(output_dir, filename)

    # Không tải lại nếu đã có
    if os.path.exists(filepath):
        print(f"  [Pexels] Already downloaded: {filename}")
        return filepath

    print(f"  [Pexels] Downloading: {filename} ({best_file.get('width')}x{best_file.get('height')})...")

    try:
        resp = requests.get(video_url, stream=True, timeout=60)
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        print(f"  [Pexels] ✅ Downloaded: {filename} ({size_mb:.1f} MB)")
        return filepath
    except Exception as e:
        print(f"  [Pexels] Download failed: {e}")
        return None


def find_and_download_background(script_text: str, output_dir: str = "backgrounds", max_downloads: int = 5):
    """
    Hàm chính nâng cấp: Gemini Keywords -> Pexels Video -> Pollinations AI Image (Fallback/Mix).
    """
    api_key = get_api_key()
    
    # 1. Dùng Gemini để tạo từ khóa xịn
    print("  [AI Visual] Đang phân tích kịch bản bằng Gemini...")
    keywords = generate_visual_keywords_with_gemini(script_text)
    print(f"  [AI Visual] Từ khóa đề xuất: {keywords}")

    downloaded = []
    
    # 2. Thử tìm Video trên Pexels trước
    if api_key:
        for keyword in keywords[:3]: # Thử 3 từ khóa đầu cho video
            print(f"  [Pexels] Đang tìm video cho: '{keyword}'...")
            videos = search_pexels_videos(keyword, api_key, per_page=3)
            
            for video in videos:
                path = download_video(video, output_dir)
                if path:
                    downloaded.append(path)
                    if len(downloaded) >= 3: # Lấy tối đa 3 video thực tế
                        break
            if len(downloaded) >= 3:
                break

    # 3. Luôn tạo thêm 2-3 Ảnh AI để đảm bảo tính độc nhất và không bị lặp
    print("  [AI Image] Đang tạo thêm ảnh AI để video không bị nhàm chán...")
    for keyword in keywords[-3:]: # Dùng các từ khóa còn lại cho ảnh AI
        path = download_ai_image(keyword, output_dir)
        if path:
            downloaded.append(path)
        if len(downloaded) >= max_downloads:
            break

    if downloaded:
        print(f"\n  [Visual Engine] ✅ Đã chuẩn bị {len(downloaded)} tài nguyên (Video thực tế + Ảnh AI).")
    else:
        print(f"\n  [Visual Engine] ⚠️ Cảnh báo: Không tải được tài nguyên mới.")

    return downloaded


if __name__ == "__main__":
    # Test
    test_script = "Chào bạn, nếu bạn muốn kiếm tiền từ bán áo thun affiliate thì đây là bí quyết"
    find_and_download_background(test_script)
