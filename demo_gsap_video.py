import os
import subprocess
import time
import imageio_ffmpeg
from playwright.sync_api import sync_playwright
from core.utils.logger_config import logger

def make_demo_gsap_video(
    html_path: str,
    bg_video_path: str,
    output_path: str,
    duration: float = 3.8,
    fps: int = 30
) -> None:
    """Tạo video demo bằng cách chụp frame từ Playwright (GSAP) và pipe vào FFmpeg.
    
    Args:
        html_path: Đường dẫn tuyệt đối đến file HTML template.
        bg_video_path: Đường dẫn đến video nền.
        output_path: Đường dẫn xuất video MP4.
        duration: Độ dài video (giây).
        fps: Khung hình trên giây.
    """
    logger.info("🚀 Bắt đầu render video bằng GSAP...")
    
    # Lấy đường dẫn FFmpeg từ thư viện imageio_ffmpeg đi kèm
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Lệnh FFmpeg nhận frame ảnh thô (image2pipe) qua stdin và encode thành mp4
    cmd = [
        ffmpeg_exe,
        "-y",
        "-f", "image2pipe",
        "-vcodec", "png",
        "-r", str(fps),
        "-i", "-",  # Nhận input từ stdin
        "-vcodec", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        output_path
    ]
    
    logger.info("🎬 Khởi tạo Playwright browser ẩn danh...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--enable-gpu", "--use-angle=metal"] if os.name != "nt" else ["--enable-gpu"]
        )
        # Thiết lập viewport kích thước 1080x1920 (chuẩn dọc TikTok)
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        
        # Mở file HTML template
        file_url = f"file://{os.path.abspath(html_path)}"
        logger.info(f"🌐 Mở template: {file_url}")
        page.goto(file_url)
        
        # Thiết lập video nền tuyệt đối
        abs_bg_video_path = os.path.abspath(bg_video_path)
        logger.info(f"🎞️ Áp dụng video nền: {abs_bg_video_path}")
        page.evaluate(f"window.setBackgroundVideo('file://{abs_bg_video_path}')")
        
        # Đợi video nền được tải và sẵn sàng render
        time.sleep(1.5)
        
        # Mở tiến trình FFmpeg
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        
        total_frames = int(duration * fps)
        logger.info(f"📹 Đang tiến hành chụp và render {total_frames} frames...")
        
        try:
            for frame_idx in range(total_frames):
                seconds = frame_idx / fps
                
                # Đồng bộ GSAP timeline đến giây mong muốn
                page.evaluate(f"window.seekTo({seconds})")
                
                # Chụp ảnh screenshot màn hình dạng binary PNG
                screenshot_bytes = page.screenshot(type="png")
                
                # Ghi bytes trực tiếp vào stdin của FFmpeg
                proc.stdin.write(screenshot_bytes)
                
                if frame_idx % 15 == 0 or frame_idx == total_frames - 1:
                    percent = int((frame_idx + 1) / total_frames * 100)
                    logger.info(f"   [Render Progress] Frame {frame_idx + 1}/{total_frames} ({percent}%)")
        except Exception as e:
            logger.error(f"❌ Lỗi trong lúc ghi frame: {e}")
        finally:
            # Đóng stdin để FFmpeg hoàn tất tiến trình lưu file
            if proc.stdin:
                proc.stdin.close()
            proc.wait()
        
        browser.close()
        
    logger.info(f"✅ Đã xuất video demo thành công tại: {output_path}")

if __name__ == "__main__":
    html_file = "demo_gsap_template.html"
    
    # Tìm file video nền để test
    bg_video = "backgrounds/pexels_9667674.mp4"
    if not os.path.exists(bg_video):
        # Fallback sang file video nền khác trong thư mục backgrounds nếu có
        files = [os.path.join("backgrounds", f) for f in os.listdir("backgrounds") if f.endswith(".mp4")]
        if files:
            bg_video = files[0]
            
    output_video = "output/demo_gsap_output.mp4"
    
    make_demo_gsap_video(html_file, bg_video, output_video)
