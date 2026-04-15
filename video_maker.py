"""
video_maker.py - TikTok Video Render Engine
=============================================
Ghép video nền + audio + subtitle thành video dọc 1080x1920 cho TikTok.
Hỗ trợ Mac, Windows, Linux (cross-platform).

NOTE: Dùng Pillow để render text (không cần ImageMagick).
"""

# === Pillow compatibility patch (Pillow 10+ removed ANTIALIAS) ===
import PIL.Image
if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
# =================================================================

import os
import re
import random
import platform
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    CompositeVideoClip,
    ColorClip,
    VideoClip,
    concatenate_videoclips,
)

# ============================================================
# CẤU HÌNH VIDEO (Chỉnh sửa tại đây nếu muốn)
# ============================================================
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30

# Cấu hình Subtitle
FONT_SIZE = 60
FONT_COLOR = (255, 255, 255)  # Trắng
STROKE_COLOR = (0, 0, 0)  # Đen viền
STROKE_WIDTH = 4

# Overlay tối nền để chữ nổi bật hơn
OVERLAY_OPACITY = 0.35


def _get_font(size: int = FONT_SIZE):
    """Tìm font phù hợp tùy theo hệ điều hành (Cross-platform) và trả về ImageFont."""
    system = platform.system()

    if system == "Darwin":  # macOS
        candidates = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    elif system == "Windows":
        candidates = [
            "C:\\Windows\\Fonts\\arialbd.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
            "C:\\Windows\\Fonts\\segoeui.ttf",
        ]
    else:  # Linux
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        ]

    for font_path in candidates:
        if os.path.exists(font_path):
            print(f"  [Font] Using: {font_path}")
            return ImageFont.truetype(font_path, size)

    print("  [Font] No preferred font found, using Pillow default.")
    return ImageFont.load_default()


def _render_text_frame(text: str, font, width: int, height: int):
    """
    Dùng Pillow để render text lên một frame RGBA trong suốt.
    Trả về numpy array (H, W, 4) - RGBA.
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Tính kích thước text để căn giữa
    max_text_width = width - 100  # padding 2 bên

    # Word wrap
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        tw = bbox[2] - bbox[0]
        if tw <= max_text_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)

    # Tính tổng chiều cao
    line_height = draw.textbbox((0, 0), "Ẩy", font=font)  # Dùng chữ cao nhất
    single_line_h = (line_height[3] - line_height[1]) + 10  # +10 spacing
    total_h = single_line_h * len(lines)

    # Vẽ text căn giữa màn hình
    y_start = (height - total_h) // 2
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (width - tw) // 2
        y = y_start + i * single_line_h

        # Vẽ viền đen (stroke)
        for dx in range(-STROKE_WIDTH, STROKE_WIDTH + 1):
            for dy in range(-STROKE_WIDTH, STROKE_WIDTH + 1):
                if dx * dx + dy * dy <= STROKE_WIDTH * STROKE_WIDTH:
                    draw.text((x + dx, y + dy), line, font=font, fill=STROKE_COLOR + (255,))

        # Vẽ chữ trắng
        draw.text((x, y), line, font=font, fill=FONT_COLOR + (255,))

    return np.array(img)


def _parse_srt(srt_path: str):
    """
    Đọc file SRT và trả về danh sách subtitle chunks.
    Mỗi chunk chứa: start (giây), end (giây), text.
    """
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()

    # SRT format:
    # 1
    # 00:00:00,100 --> 00:00:01,537
    # Xin chào bạn
    pattern = re.compile(
        r"\d+\s*\n"
        r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*\n"
        r"(.*?)(?:\n\n|\Z)",
        re.DOTALL,
    )

    subs = []
    for match in pattern.finditer(content):
        h1, m1, s1, ms1 = int(match[1]), int(match[2]), int(match[3]), int(match[4])
        h2, m2, s2, ms2 = int(match[5]), int(match[6]), int(match[7]), int(match[8])
        start = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0
        end = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0
        text = match[9].strip().replace("\n", " ")
        if text:
            subs.append({"start": start, "end": end, "text": text})

    if not subs:
        print("  [WARNING] No subtitles found in SRT file!")
    else:
        print(f"  [Subtitles] Parsed {len(subs)} subtitle blocks from SRT.")

    return subs


def _pick_background(bg_dir: str):
    """Chọn ngẫu nhiên 1 file video nền từ thư mục backgrounds."""
    supported = (".mp4", ".mov", ".avi", ".mkv", ".webm")
    videos = [
        os.path.join(bg_dir, f)
        for f in os.listdir(bg_dir)
        if f.lower().endswith(supported)
    ]
    if not videos:
        raise FileNotFoundError(
            f"Không tìm thấy video nền trong '{bg_dir}/'.\n"
            f"Hãy tải video dọc (9:16) từ Pexels.com và bỏ vào thư mục '{bg_dir}/'."
        )
    chosen = random.choice(videos)
    print(f"  [Background] Selected: {os.path.basename(chosen)}")
    return chosen


def _prepare_background(bg_path: str, duration: float):
    """
    Chuẩn bị video nền: crop/resize về 1080x1920 và loop nếu ngắn hơn audio.
    """
    clip = VideoFileClip(bg_path)

    # Resize giữ tỉ lệ sao cho phủ kín khung 1080x1920
    clip_ratio = clip.w / clip.h
    target_ratio = VIDEO_WIDTH / VIDEO_HEIGHT

    if clip_ratio > target_ratio:
        # Video quá rộng -> resize theo chiều cao, crop ngang
        clip = clip.resize(height=VIDEO_HEIGHT)
        x_center = clip.w / 2
        clip = clip.crop(
            x1=x_center - VIDEO_WIDTH / 2,
            x2=x_center + VIDEO_WIDTH / 2,
            y1=0,
            y2=VIDEO_HEIGHT,
        )
    else:
        # Video quá cao -> resize theo chiều rộng, crop dọc
        clip = clip.resize(width=VIDEO_WIDTH)
        y_center = clip.h / 2
        clip = clip.crop(
            x1=0,
            x2=VIDEO_WIDTH,
            y1=y_center - VIDEO_HEIGHT / 2,
            y2=y_center + VIDEO_HEIGHT / 2,
        )

    # Loop video nền nếu ngắn hơn audio
    if clip.duration < duration:
        n_loops = int(duration / clip.duration) + 1
        clip = concatenate_videoclips([clip] * n_loops)

    clip = clip.subclip(0, duration)
    return clip


def make_video(
    audio_path: str,
    srt_path: str,
    bg_dir: str = "backgrounds",
    output_path: str = "output/final_video.mp4",
):
    """
    Hàm chính: Ghép audio + video nền + subtitle thành video TikTok hoàn chỉnh.

    Args:
        audio_path: Đường dẫn file audio (.mp3)
        srt_path: Đường dẫn file subtitle (.srt)
        bg_dir: Thư mục chứa video nền
        output_path: Đường dẫn file video đầu ra
    """
    print("\n🎬 Bắt đầu tạo video...")

    # 1. Load audio
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    audio = AudioFileClip(audio_path)
    duration = audio.duration
    print(f"  [Audio] Duration: {duration:.1f}s")

    # 2. Chuẩn bị video nền
    bg_path = _pick_background(bg_dir)
    bg_clip = _prepare_background(bg_path, duration)

    # 3. Parse subtitles từ SRT
    subs = _parse_srt(srt_path)
    font = _get_font()

    # 4. Pre-render tất cả text frames bằng Pillow (RGBA)
    print("  [Subtitles] Pre-rendering text frames...")
    sub_frames = {}
    for i, sub in enumerate(subs):
        frame_rgba = _render_text_frame(sub["text"], font, VIDEO_WIDTH, VIDEO_HEIGHT)
        sub_frames[i] = frame_rgba

    # 5. Tạo clip kết hợp: background + overlay tối + subtitle
    def make_combined_frame(get_frame, t):
        bg_frame = get_frame(t).astype(np.float32)
        # Phủ overlay tối
        bg_frame = bg_frame * (1 - OVERLAY_OPACITY)
        # Tìm subtitle phù hợp với thời điểm t
        sub_rgba = None
        for i, sub in enumerate(subs):
            if sub["start"] <= t < sub["end"]:
                sub_rgba = sub_frames[i]
                break
        if sub_rgba is not None:
            alpha = sub_rgba[:, :, 3:4].astype(np.float32) / 255.0
            sub_rgb = sub_rgba[:, :, :3].astype(np.float32)
            bg_frame = bg_frame * (1 - alpha) + sub_rgb * alpha
        return bg_frame.clip(0, 255).astype(np.uint8)

    combined_clip = bg_clip.fl(make_combined_frame).set_duration(duration)
    final = combined_clip.set_audio(audio)

    # 6. Render ra file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    print(f"\n  [Render] Rendering video to {output_path}...")
    final.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
        logger="bar",
    )

    # Dọn dẹp bộ nhớ
    final.close()
    audio.close()
    bg_clip.close()

    print(f"\n✅ Video created successfully: {output_path}")
    return output_path


if __name__ == "__main__":
    make_video("temp/audio.mp3", "temp/subtitles.srt")
