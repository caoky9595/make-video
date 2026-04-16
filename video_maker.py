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
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    CompositeVideoClip,
    CompositeAudioClip,
    ColorClip,
    VideoClip,
    concatenate_videoclips,
    afx
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
HIGHLIGHT_COLOR = (247, 194, 4)  # Vàng Hormozi mượt hơn (#F7C204)
STROKE_COLOR = (0, 0, 0)  # Đen viền
STROKE_WIDTH = 5

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


def _render_text_frame(text: str, font, width: int, height: int, active_idx: int = -1, style_mode: int = 2, position: str = "center"):
    """
    Render Subtitle according to style_mode.
    1: Ali (Normal case, soft shadow, blue/cyan active)
    2: Marker Box (UPPERCASE, green background box)
    3: MrBeast (UPPERCASE, thick stroke, jump, yellow active)
    4: Typewriter (Normal case, black translucent band, type word by word)
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    max_text_width = width - 100
    
    if style_mode in (2, 3):
        words = text.upper().split()
    else:
        words = text.split()
        
    try:
        space_width = int(draw.textlength(" ", font=font))
    except AttributeError:
        space_width = draw.textbbox((0,0), " A", font=font)[2] - draw.textbbox((0,0), "A", font=font)[2]

    # Layout words
    lines = []
    current_line_words = []
    current_width = 0
    
    for i, word in enumerate(words):
        try:
            w_width = int(draw.textlength(word, font=font))
        except AttributeError:
            w_bbox = draw.textbbox((0, 0), word, font=font)
            w_width = w_bbox[2] - w_bbox[0]
            
        line_w_increment = w_width + space_width if current_line_words else w_width
        if current_width + line_w_increment <= max_text_width:
            current_line_words.append((i, word, w_width))
            current_width += line_w_increment
        else:
            if current_line_words:
                lines.append((current_line_words, current_width))
            current_line_words = [(i, word, w_width)]
            current_width = w_width
            
    if current_line_words:
        lines.append((current_line_words, current_width))
        
    line_height = draw.textbbox((0, 0), "Ẩy", font=font)
    single_line_h = (line_height[3] - line_height[1]) + 10
    total_h = single_line_h * len(lines)
    
    if position == "bottom":
        # Cách đáy 400px để tránh đè lên UI Tiktok (caption, tim, share)
        y = height - total_h - 400 
    else:
        y = (height - total_h) // 2

    # Style 4 (Typewriter) Backdrop
    if style_mode == 4:
        draw.rectangle([0, y - 50, width, y + total_h + 50], fill=(0, 0, 0, 150))
        
    for line_words, line_w in lines:
        x = (width - line_w) // 2
        for i, word, w_width in line_words:
            # Skip words outside typewriter view
            if style_mode == 4 and i > active_idx:
                break
                
            current_y = y
            fill_color = (255, 255, 255, 255)
            
            if style_mode == 1:
                # Ali Abdaal style
                fill_color = (135, 206, 250, 255) if i == active_idx else (230, 230, 230, 255)
                draw.text((x+3, y+3), word, font=font, fill=(0,0,0,150))
                draw.text((x, y), word, font=font, fill=fill_color)
                
            elif style_mode == 2:
                # Marker Box
                if i == active_idx:
                    draw.rectangle([x-10, y-5, x+w_width+10, y+(single_line_h-10)], fill=(57, 255, 20, 255))
                    fill_color = (0, 0, 0, 255)
                else:
                    draw.text((x+4, y+4), word, font=font, fill=(0,0,0,255))
                draw.text((x, y), word, font=font, fill=fill_color)
                
            elif style_mode == 3:
                # MrBeast
                f_font = font
                stroke_w = STROKE_WIDTH
                if i == active_idx:
                    fill_color = HIGHLIGHT_COLOR + (255,)
                    current_y = y - 10
                    stroke_w = STROKE_WIDTH + 1
                    
                for dx in range(-stroke_w, stroke_w + 1):
                    for dy in range(-stroke_w, stroke_w + 1):
                        if dx * dx + dy * dy <= stroke_w * stroke_w:
                            draw.text((x + dx, current_y + dy), word, font=f_font, fill=STROKE_COLOR + (255,))
                draw.text((x, current_y), word, font=f_font, fill=fill_color)
                
            elif style_mode == 4:
                # Typewriter
                draw.text((x, y), word, font=font, fill=(255,255,255,255))
                
            x += w_width + space_width
            
        y += single_line_h
        
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


def _parse_words(srt_path: str):
    words_path = srt_path.replace(".srt", "_words.json")
    if os.path.exists(words_path):
        with open(words_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


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
    style: int = 1,
    position: str = "bottom",
    bgm_path: str = None,
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
    
    # MIX AUDIO BACKGROUND (BGM)
    if bgm_path and os.path.exists(bgm_path):
        print(f"  [Audio] Mixing BGM: {os.path.basename(bgm_path)}")
        try:
            bgm_clip = AudioFileClip(bgm_path)
            
            # Loop BGM if it's shorter than TTS duration, then trim
            bgm_clip = afx.audio_loop(bgm_clip, duration=duration)
            
            # Reduce BGM volume to 10% so it acts as background
            bgm_clip = bgm_clip.volumex(0.1)
            
            audio = CompositeAudioClip([bgm_clip, audio])
        except Exception as e:
            print(f"  [Audio] ⚠️ Failed to mix BGM: {e}")

    # 2. Chuẩn bị video nền
    bg_path = _pick_background(bg_dir)
    bg_clip = _prepare_background(bg_path, duration)

    # 3. Parse subtitles từ SRT
    subs = _parse_srt(srt_path)
    words_data = _parse_words(srt_path)
    font = _get_font()

    # 3.5 Tạo Thumbnail tự động (Ảnh bìa)
    print("  [Thumbnail] Generating video cover...")
    try:
        first_frame = bg_clip.get_frame(0.1).astype(np.uint8)
        img = Image.fromarray(first_frame).convert("RGBA")
        img = img.filter(ImageFilter.GaussianBlur(10))
        img = ImageEnhance.Brightness(img).enhance(0.4)
        
        # Render câu Hook đầu tiên thành text 3D mập mạp bự gấp đôi ở giữa màn hình
        thumb_font = _get_font(FONT_SIZE * 2)
        title_text = subs[0]["text"] if subs else "TIKTOK"
        
        # Dùng phong cách MrBeast (style_mode=3) để chữ nổi bần bật với từ khoá đầu màu Vàng.
        text_layer_np = _render_text_frame(title_text, thumb_font, VIDEO_WIDTH, VIDEO_HEIGHT, active_idx=0, style_mode=3, position="center")
        text_layer_img = Image.fromarray(text_layer_np, "RGBA")
        
        # Dán lớp chữ lên nền mờ
        img.paste(text_layer_img, (0, 0), text_layer_img)
        
        thumb_path = output_path.rsplit(".", 1)[0] + "_cover.jpg"
        img.convert("RGB").save(thumb_path)
        print(f"  [Thumbnail] ✅ Saved cover to: {thumb_path}")
    except Exception as e:
         print(f"  [Thumbnail] ⚠️ Thumbnail generation failed: {e}")

    # Ghép words vào subs
    for sub in subs:
        sub["words"] = []
        for w in words_data:
            w_mid = (w["start"] + w["end"]) / 2
            if sub["start"] - 0.2 <= w_mid <= sub["end"] + 0.2:
                sub["words"].append(w)

    # 4. Pre-render text frames caching
    print(f"  [Subtitles] Rendering dynamic text frames cache (Style {style}, Position {position})...")
    frame_cache = {}
    
    def get_text_frame(sub_index, active_idx):
        key = (sub_index, active_idx)
        if key not in frame_cache:
            frame_cache[key] = _render_text_frame(subs[sub_index]["text"], font, VIDEO_WIDTH, VIDEO_HEIGHT, active_idx, style_mode=style, position=position)
        return frame_cache[key]

    # 5. Tạo clip kết hợp: background + overlay tối + subtitle
    def make_combined_frame(get_frame, t):
        bg_frame = get_frame(t).astype(np.float32)
        # Phủ overlay tối
        bg_frame = bg_frame * (1 - OVERLAY_OPACITY)
        
        # Tìm subtitle phù hợp với thời điểm t
        sub_rgba = None
        for i, sub in enumerate(subs):
            if sub["start"] <= t <= sub["end"]:
                active_word_index = -1
                for w_idx, w in enumerate(sub["words"]):
                    if w["start"] <= t <= w["end"]:
                        active_word_index = w_idx
                        break
                sub_rgba = get_text_frame(i, active_word_index)
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
