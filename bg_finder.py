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
from dotenv import load_dotenv

# Tải biến môi trường từ file .env
load_dotenv()

# Cấu hình Video Nền Thôi Miên (Satisfying Loops) dành riêng cho Kênh kể truyện
# Thay vì lấy cảnh văn phòng nhàm chán, hệ thống sẽ ưu tiên trích xuất Lofi chill
KEYWORD_MAP = {
    r"\bsợ\b": "creepy dark forest",
    r"\bma\b": "scary dark",
    r"\bác\b": "spooky dark background",
    r"\bđêm\b": "driving night city rain",
    r"\bbuồn\b": "rainy window aesthetic",
    r"\bkhóc\b": "rain drops window",
    r"\bcô đơn\b": "night sky clouds",
    r"\btình yêu\b": "romantic sunset aesthetic",
    r"\bchill\b": "lofi aesthetic",
    r"\bmưa\b": "heavy rain cinematic",
}

# Fallback: Ưu tiên video Lofi như user yêu cầu
FALLBACK_KEYWORDS = [
    "lofi aesthetic",
    "lofi chilling anime",
    "relaxing lofi background",
    "cozy lofi room aesthetic",
    "vaporwave aesthetic loop",
]


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


def find_and_download_background(script_text: str, output_dir: str = "backgrounds", max_downloads: int = 2):
    """
    Hàm chính: Đọc kịch bản → Trích từ khoá → Tìm trên Pexels → Tải video nền.

    Args:
        script_text: Nội dung kịch bản tiếng Việt
        output_dir: Thư mục lưu video nền
        max_downloads: Số video tải về tối đa mỗi lần

    Returns:
        List đường dẫn các file đã tải
    """
    api_key = get_api_key()
    if not api_key:
        return []

    # Trích xuất từ khoá
    keywords = extract_keywords(script_text)
    print(f"  [Pexels] Keywords extracted: {keywords}")

    downloaded = []
    for keyword in keywords:
        print(f"  [Pexels] Searching for: '{keyword}'...")
        videos = search_pexels_videos(keyword, api_key)

        if not videos:
            print(f"  [Pexels] No results for '{keyword}'")
            continue

        # Tải video đầu tiên tìm được
        for video in videos[:max_downloads]:
            path = download_video(video, output_dir)
            if path:
                downloaded.append(path)
                if len(downloaded) >= max_downloads:
                    break

        if len(downloaded) >= max_downloads:
            break

    if downloaded:
        print(f"\n  [Pexels] ✅ Tổng cộng tải {len(downloaded)} video nền mới.")
    else:
        print(f"\n  [Pexels] ⚠️  Không tải được video. Sẽ dùng video có sẵn trong '{output_dir}/'.")

    return downloaded


if __name__ == "__main__":
    # Test
    test_script = "Chào bạn, nếu bạn muốn kiếm tiền từ bán áo thun affiliate thì đây là bí quyết"
    find_and_download_background(test_script)
