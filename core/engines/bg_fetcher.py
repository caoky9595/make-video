import os
import subprocess
import threading
from core.utils.logger_config import logger

def download_youtube_background(url: str, output_dir: str = "backgrounds"):
    """
    Sử dụng yt-dlp để tải video YouTube.
    Tải chất lượng tốt nhất không có tiếng, hoặc tải bình thường và tắt tiếng.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # yt-dlp command để tải video MP4 tốt nhất
    # -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]"
    # Nhưng vì là video nền, ta chỉ cần video, không cần audio.
    # -f "bestvideo[ext=mp4]"
    
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[ext=mp4]/best[ext=mp4]",
        "--no-audio",
        "-o", f"{output_dir}/%(id)s_%(title).50s.%(ext)s",
        url
    ]
    
    try:
        logger.info(f"[AutoBg] Đang tải video từ YouTube: {url}")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        for line in process.stdout:
            logger.info(f"[yt-dlp] {line.strip()}")
            
        process.wait()
        if process.returncode == 0:
            logger.info("[AutoBg] Tải video thành công!")
            return True
        else:
            logger.info(f"[AutoBg] Lỗi tải video! Return code: {process.returncode}")
            return False
            
    except Exception as e:
        logger.info(f"[AutoBg] Lỗi Exception: {e}")
        return False

def start_download_thread(url: str):
    """Start download thread."""
    threading.Thread(target=download_youtube_background, args=(url,), daemon=True).start()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        download_youtube_background(sys.argv[1])
    else:
        logger.info("Sử dụng: python bg_fetcher.py <youtube_url>")
