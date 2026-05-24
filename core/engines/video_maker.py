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
from core.utils.logger_config import logger
from moviepy.editor import (
    VideoFileClip,
    ImageClip,
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
BGM_VOLUME = 0.22


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
            logger.info(f"  [Font] Using: {font_path}")
            return ImageFont.truetype(font_path, size)

    logger.info("  [Font] No preferred font found, using Pillow default.")
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
                
            elif style_mode == 5:
                # Soft Aesthetic (Affiliate Style)
                # Smaller, elegant, with a very subtle shadow
                draw.text((x+2, y+2), word, font=font, fill=(0,0,0,80)) # Subtle shadow
                draw.text((x, y), word, font=font, fill=(255, 255, 255, 255)) # Pure white
                
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
        logger.info("  [WARNING] No subtitles found in SRT file!")
    else:
        logger.info(f"  [Subtitles] Parsed {len(subs)} subtitle blocks from SRT.")

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
    logger.info(f"  [Background] Selected: {os.path.basename(chosen)}")
    return chosen


def _collect_visual_sources(
    bg_dir: str,
    image_dir: str,
    visual_mode: str,
    uploaded_images=None,
):
    """Trả về danh sách nguồn visual theo mode: pexels | uploaded | mix."""
    video_ext = (".mp4", ".mov", ".avi", ".mkv", ".webm")
    image_ext = (".jpg", ".jpeg", ".png", ".webp")

    videos = []
    images = []

    if os.path.isdir(bg_dir):
        videos = [
            os.path.join(bg_dir, f)
            for f in os.listdir(bg_dir)
            if f.lower().endswith(video_ext)
        ]

    if os.path.isdir(image_dir):
        images = [
            os.path.join(image_dir, f)
            for f in os.listdir(image_dir)
            if f.lower().endswith(image_ext)
        ]

    if uploaded_images:
        allowed = {os.path.basename(x) for x in uploaded_images}
        images = [p for p in images if os.path.basename(p) in allowed]

    if visual_mode == "uploaded":
        return images
    if visual_mode == "mix":
        return videos + images
    return videos


def _prepare_image_background(image_path: str, duration: float):
    """Chuẩn bị nền từ ảnh tĩnh với hiệu ứng Cinematic Zoom (Ken Burns)."""
    # Load image with PIL to get size
    img = Image.open(image_path)
    img_w, img_h = img.size
    
    # Resize sao cho phủ kín 1080x1920 (crop trung tâm)
    target_ratio = VIDEO_WIDTH / VIDEO_HEIGHT
    img_ratio = img_w / img_h
    
    if img_ratio > target_ratio:
        new_h = VIDEO_HEIGHT
        new_w = int(new_h * img_ratio)
    else:
        new_w = VIDEO_WIDTH
        new_h = int(new_w / img_ratio)
        
    img = img.resize((new_w, new_h), Image.LANCZOS)
    
    # Hàm tạo frame với hiệu ứng zoom
    def make_frame(t):
        # Zoom từ 100% lên 115% trong suốt duration
        """Make frame."""
        zoom = 1.0 + (t / duration) * 0.15
        curr_w = int(new_w * zoom)
        curr_h = int(new_h * zoom)
        
        # Resize frame
        frame_img = img.resize((curr_w, curr_h), Image.LANCZOS)
        
        # Crop center
        left = (curr_w - VIDEO_WIDTH) // 2
        top = (curr_h - VIDEO_HEIGHT) // 2
        frame_img = frame_img.crop((left, top, left + VIDEO_WIDTH, top + VIDEO_HEIGHT))
        
        return np.array(frame_img.convert("RGB"))

    return VideoClip(make_frame, duration=duration)


def _prepare_visual_background(asset_path: str, duration: float, other_bg_paths=None):
    """Tự động xử lý background là video hoặc ảnh."""
    image_ext = (".jpg", ".jpeg", ".png", ".webp")
    if asset_path.lower().endswith(image_ext):
        return _prepare_image_background(asset_path, duration)
    return _prepare_non_loop_background(asset_path, duration, other_bg_paths)


def _prepare_non_loop_background(bg_path: str, duration: float, other_bg_paths=None):
    """
    Chuẩn bị video nền bằng cách ghép nối nhiều video khác nhau từ other_bg_paths nếu video hiện tại quá ngắn.
    Tránh lặp lại một video đơn lẻ.
    """
    clip = VideoFileClip(bg_path)
    
    # Căn chỉnh kích thước tỷ lệ khung hình 9:16
    def format_clip(c):
        """Format clip."""
        clip_ratio = c.w / c.h
        target_ratio = VIDEO_WIDTH / VIDEO_HEIGHT
        if clip_ratio > target_ratio:
            c = c.resize(height=VIDEO_HEIGHT)
            x_center = c.w / 2
            c = c.crop(x1=x_center - VIDEO_WIDTH / 2, x2=x_center + VIDEO_WIDTH / 2, y1=0, y2=VIDEO_HEIGHT)
        else:
            c = c.resize(width=VIDEO_WIDTH)
            y_center = c.h / 2
            c = c.crop(x1=0, x2=VIDEO_WIDTH, y1=y_center - VIDEO_HEIGHT / 2, y2=y_center + VIDEO_HEIGHT / 2)
        return c

    clip = format_clip(clip)

    if clip.duration >= duration:
        # Nếu đủ dài, lấy một đoạn ngẫu nhiên
        max_start = clip.duration - duration
        start_time = random.uniform(0, max_start)
        return clip.subclip(start_time, start_time + duration)

    # Nếu quá ngắn, thực hiện ghép nối (concatenate) với các clip khác
    logger.info(f"  [Video] Clip '{os.path.basename(bg_path)}' ({clip.duration:.1f}s) ngắn hơn scene ({duration:.1f}s). Đang ghép nối thêm video...")
    clips_to_concat = [clip]
    remaining = duration - clip.duration

    # Lọc các video khác từ list
    pool = []
    if other_bg_paths:
        image_ext = (".jpg", ".jpeg", ".png", ".webp")
        pool = [p for p in other_bg_paths if p != bg_path and not p.lower().endswith(image_ext)]
        random.shuffle(pool)

    # Nếu không có video khác trong pool, ta đành phải dùng lại chính video đó (fallback cuối cùng)
    if not pool:
        pool = [bg_path]

    pool_idx = 0
    while remaining > 0.01:
        next_path = pool[pool_idx % len(pool)]
        pool_idx += 1
        
        try:
            next_c = VideoFileClip(next_path)
            next_c = format_clip(next_c)
            
            if next_c.duration >= remaining:
                # Đủ bù thời lượng còn lại
                max_start = next_c.duration - remaining
                start_t = random.uniform(0, max_start)
                clips_to_concat.append(next_c.subclip(start_t, start_t + remaining))
                remaining = 0
            else:
                clips_to_concat.append(next_c)
                remaining -= next_c.duration
        except Exception as e:
            logger.info(f"  [Video] ⚠️ Lỗi load clip phụ '{next_path}': {e}")
            # Fallback nếu lỗi: dùng ColorClip đen tạm thời
            black_c = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(0, 0, 0), duration=remaining)
            clips_to_concat.append(black_c)
            remaining = 0

    # Ghép nối tất cả các clip
    final_clip = concatenate_videoclips(clips_to_concat)
    return final_clip


def record_used_backgrounds(used_paths, database_path="used_backgrounds.json"):
    """Trích xuất Pexels IDs từ tên file video đã dùng và lưu vào database."""
    import json
    import re
    ids = []
    for path in used_paths:
        filename = os.path.basename(path)
        match = re.search(r"pexels_(\d+)\.mp4", filename)
        if match:
            ids.append(int(match.group(1)))
            
    if not ids:
        return
        
    existing_ids = []
    if os.path.exists(database_path):
        try:
            with open(database_path, "r") as f:
                existing_ids = json.load(f)
                if not isinstance(existing_ids, list):
                    existing_ids = []
        except Exception as e:
            logger.info(f"  [Visual Logging] ⚠️ Lỗi đọc {database_path}: {e}")
            
    # Hợp nhất và loại trùng
    updated_ids = list(set(existing_ids + ids))
    
    try:
        with open(database_path, "w") as f:
            json.dump(updated_ids, f, indent=4)
        logger.info(f"  [Visual Logging] ✅ Đã lưu thêm {len(ids)} video IDs đã dùng vào {database_path}.")
    except Exception as e:
        logger.info(f"  [Visual Logging] ⚠️ Lỗi ghi {database_path}: {e}")


class LazyBackgroundClip:
    """Trình quản lý Lazy Load cho background video. Chỉ mở 1 video tại một thời điểm để tiết kiệm RAM."""
    def __init__(self, subs, duration, visual_sources, visual_mode, ai_images):
        self.subs = subs
        self.duration = duration
        self.visual_sources = visual_sources
        self.visual_mode = visual_mode
        self.ai_images = ai_images
        
        self.scenes = []
        self.actually_used = []
        
        for i, sub in enumerate(subs):
            start_t = sub["start"]
            end_t = subs[i+1]["start"] if i+1 < len(subs) else duration
            scene_duration = end_t - start_t
            
            if visual_mode == "ai":
                from core.engines import ai_visuals
                asset_p = ai_images[i] if i < len(ai_images) and ai_images[i] else ai_visuals.generate_pollinations_image("tiktok story background")
            else:
                if visual_sources:
                    asset_p = visual_sources[i % len(visual_sources)]
                else:
                    asset_p = None
                
            if asset_p:
                self.scenes.append({
                    "start": start_t,
                    "end": end_t,
                    "duration": scene_duration,
                    "asset": asset_p
                })
                self.actually_used.append(asset_p)
            
        self.current_idx = -1
        self.current_clip = None
        self.current_start_t = 0.0
        
    def get_frame(self, t):
        """Get frame."""
        if not self.scenes:
            return np.zeros((VIDEO_HEIGHT, VIDEO_WIDTH, 3), dtype=np.uint8)
            
        idx = 0
        for i, scene in enumerate(self.scenes):
            if scene["start"] <= t < scene["end"]:
                idx = i
                break
        else:
            if t >= self.scenes[-1]["end"]:
                idx = len(self.scenes) - 1
                
        if self.current_idx != idx:
            if self.current_clip is not None:
                try:
                    self.current_clip.close()
                except Exception:
                    pass
                self.current_clip = None
                
            scene = self.scenes[idx]
            try:
                self.current_clip = _prepare_visual_background(scene["asset"], scene["duration"], self.visual_sources)
            except Exception as e:
                logger.info(f"  [Video] ⚠️ Lỗi nạp asset {scene['asset']}: {e}")
                self.current_clip = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(30, 30, 30), duration=scene["duration"])
                
            self.current_idx = idx
            self.current_start_t = scene["start"]
            
        clip_t = t - self.current_start_t
        clip_t = max(0.0, min(clip_t, self.current_clip.duration - 0.001))
        return self.current_clip.get_frame(clip_t)
        
    def close(self):
        """Close."""
        if self.current_clip is not None:
            try:
                self.current_clip.close()
            except Exception:
                pass


def make_video(
    audio_path: str,
    srt_path: str,
    bg_dir: str = "backgrounds",
    image_dir: str = "uploaded_images",
    output_path: str = "output/final_video.mp4",
    style: int = 1,
    position: str = "bottom",
    bgm_path: str = None,
    bgm_start_sec: float = 0.0,
    bgm_volume: float = BGM_VOLUME,
    visual_mode: str = "pexels",
    uploaded_images=None,
    video_mode: str = "realistic",
):
    """
    Hàm chính: Ghép audio + video nền + subtitle thành video TikTok hoàn chỉnh.
    """
    logger.info("\n🎬 Bắt đầu tạo video...")

    # 1. Load audio
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    audio = AudioFileClip(audio_path)
    duration = audio.duration
    logger.info(f"  [Audio] Duration: {duration:.1f}s")
    
    # MIX AUDIO BACKGROUND (BGM)
    bgm_mix_clip = None
    bgm_volume = max(0.0, min(1.0, float(bgm_volume)))
    if bgm_path and os.path.exists(bgm_path):
        logger.info(f"  [Audio] Mixing BGM: {os.path.basename(bgm_path)}")
        try:
            bgm_clip = AudioFileClip(bgm_path)
            bgm_start_sec = max(0.0, float(bgm_start_sec or 0.0))
            if bgm_start_sec >= bgm_clip.duration:
                logger.info("  [Audio] ⚠️ BGM start vượt độ dài file, reset về 0s")
                bgm_start_sec = 0.0

            bgm_mix_clip = bgm_clip.subclip(bgm_start_sec, bgm_clip.duration)
            if bgm_mix_clip.duration <= 0.05:
                bgm_mix_clip = bgm_clip

            # Loop segment nhạc nếu ngắn hơn giọng đọc, rồi cắt vừa duration.
            bgm_mix_clip = afx.audio_loop(bgm_mix_clip, duration=duration)
            bgm_mix_clip = bgm_mix_clip.subclip(0, duration)

            # Keep BGM audible while still behind voice.
            bgm_mix_clip = bgm_mix_clip.volumex(bgm_volume)
            logger.info(f"  [Audio] BGM volume: {bgm_volume:.2f}")

            audio = CompositeAudioClip([bgm_mix_clip, audio])
        except Exception as e:
            logger.info(f"  [Audio] ⚠️ Failed to mix BGM: {e}")

    # 2. Chuẩn bị video nền (Multi-Scene)
    visual_sources = _collect_visual_sources(
        bg_dir=bg_dir,
        image_dir=image_dir,
        visual_mode=visual_mode,
        uploaded_images=uploaded_images,
    )
    # List theo dõi các visual assets thực tế sử dụng để lưu vết
    actually_used_assets = []

    if video_mode == "veo":
        # Veo mode vẫn dùng 1 file duy nhất do giá thành cao
        bg_path = os.path.join(bg_dir, "veo_generated.mp4")
        bg_clip = _prepare_visual_background(bg_path, duration)
        actually_used_assets = [bg_path]
    elif not visual_sources:
        bg_clip = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(30, 30, 30), duration=duration)
    else:
        # LOGIC MULTI-SCENE: Chia nhỏ thời lượng theo subtitle
        logger.info(f"  [Video] Multi-Scene mode: Đang ghép nối tài nguyên...")
        
        # Lấy danh sách sub để chia đoạn
        subs = _parse_srt(srt_path)
        if not subs:
            # Fallback nếu không có sub
            if visual_mode == "ai":
                from core.engines import ai_visuals
                bg_path = ai_visuals.generate_pollinations_image("tiktok story background")
                bg_clip = _prepare_visual_background(bg_path, duration)
                actually_used_assets = [bg_path]
            else:
                chosen_bg = random.choice(visual_sources)
                bg_clip = _prepare_visual_background(chosen_bg, duration, visual_sources)
                actually_used_assets = [chosen_bg]
        else:
            if visual_sources:
                random.shuffle(visual_sources) # Xáo trộn để tránh lặp lại
            
            # Sinh ảnh AI trực tiếp dựa trên nội dung thoại bằng Đa Luồng (Multithreading)
            if visual_mode == "ai":
                from core.engines import ai_visuals
                import concurrent.futures
                logger.info(f"  [Video] Đang sinh {len(subs)} ảnh AI bằng đa luồng...")
                
                def generate_ai_bg(sub_item):
                    """Generate ai bg."""
                    return ai_visuals.generate_pollinations_image(sub_item["text"])
                
                ai_images = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    ai_images = list(executor.map(generate_ai_bg, subs))
            else:
                ai_images = []
            
            # Dùng Lazy Loader để tránh OOM
            bg_clip = LazyBackgroundClip(subs, duration, visual_sources, visual_mode, ai_images)
            actually_used_assets = bg_clip.actually_used


    # 3. Parse subtitles từ SRT
    subs = _parse_srt(srt_path)
    words_data = _parse_words(srt_path)
    font = _get_font()

    # 3.5 Tạo Thumbnail tự động (Ảnh bìa)
    logger.info("  [Thumbnail] Generating video cover...")
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
        logger.info(f"  [Thumbnail] ✅ Saved cover to: {thumb_path}")
    except Exception as e:
         logger.info(f"  [Thumbnail] ⚠️ Thumbnail generation failed: {e}")

    # Ghép words vào subs
    for sub in subs:
        sub["words"] = []
        for w in words_data:
            w_mid = (w["start"] + w["end"]) / 2
            if sub["start"] - 0.2 <= w_mid <= sub["end"] + 0.2:
                sub["words"].append(w)

    # 4. Pre-render text frames caching
    logger.info(f"  [Subtitles] Rendering dynamic text frames cache (Style {style}, Position {position})...")
    frame_cache = {}
    
    def get_text_frame(sub_index, active_idx):
        """Get text frame."""
        key = (sub_index, active_idx)
        if key not in frame_cache:
            rgba = _render_text_frame(subs[sub_index]["text"], font, VIDEO_WIDTH, VIDEO_HEIGHT, active_idx, style_mode=style, position=position)
            # Precompute alpha and pre-multiplied RGB for ultra-fast compositing
            alpha = (rgba[:, :, 3:4] / 255.0).astype(np.float32)
            rgb_alpha = (rgba[:, :, :3] * alpha).astype(np.float32)
            inv_alpha = (1.0 - alpha).astype(np.float32)
            frame_cache[key] = (rgb_alpha, inv_alpha)
        return frame_cache[key]

    # 5. Tạo clip kết hợp: background + overlay tối + subtitle
    # 5. Tạo clip kết hợp: background + overlay tối + subtitle
    def make_combined_frame(get_frame, t):
        # Mặc định
        """Make combined frame."""
        curr_offset_x = 0
        curr_offset_y = 0
        curr_scale = 1.0
        shake_intensity = 0
        
        # Tìm subtitle và cảm xúc để điều chỉnh camera/acting
        active_sub_idx = -1
        active_word_idx = -1
        for i, sub in enumerate(subs):
            if sub["start"] <= t <= sub["end"]:
                active_sub_idx = i
                for w_idx, w in enumerate(sub["words"]):
                    if w["start"] <= t <= w["end"]:
                        active_word_idx = w_idx
                        break
                break
        
        bg_frame = get_frame(t).astype(np.float32)
        # Phủ overlay tối
        bg_frame *= (1.0 - OVERLAY_OPACITY)
        
        # Subtitle Overlay
        sub_data = None
        if active_sub_idx != -1:
            sub_data = get_text_frame(active_sub_idx, active_word_idx)
                
        if sub_data is not None:
            rgb_alpha, inv_alpha = sub_data
            bg_frame = bg_frame * inv_alpha + rgb_alpha
            
        return bg_frame.clip(0, 255).astype(np.uint8)

    # 6. Render ra file bằng FFmpeg Pipe (Chống tràn RAM)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    logger.info(f"\n  [Audio] Đang trộn âm thanh nền và giọng đọc...")
    temp_audio_path = output_path.replace(".mp4", "_temp_audio.mp3")
    try:
        audio.write_audiofile(temp_audio_path, fps=44100, logger=None)
    except Exception as e:
        logger.info(f"  [Audio] ⚠️ Lỗi xuất âm thanh: {e}")
        # Fallback to pure audio_path if mix fails
        temp_audio_path = audio_path
        
    logger.info(f"  [Render] Bắt đầu stream frames trực tiếp tới FFmpeg (Siêu nhẹ, RAM < 200MB)...")
    import subprocess
    
    # Tìm đường dẫn ffmpeg đi kèm với imageio (moviepy) thay vì dùng lệnh toàn cục
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    ffmpeg_cmd = [
        ffmpeg_exe, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}",
        "-pix_fmt", "rgb24",
        "-r", str(FPS),
        "-i", "-",          # stdin pipe
        "-i", temp_audio_path,  # Audio file
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_path
    ]
    
    # Mở tiến trình FFmpeg ẩn output để đỡ rác console
    process = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    
    def safe_get_frame(t_val):
        # Tránh lỗi index out of bounds của moviepy
        """Safe get frame."""
        t_safe = max(0.0, min(t_val, bg_clip.duration - 0.001))
        return bg_clip.get_frame(t_safe)

    total_frames = int(duration * FPS)
    try:
        for frame_idx in range(total_frames):
            t = frame_idx / FPS
            # Tính toán frame
            frame_data = make_combined_frame(safe_get_frame, t)
            
            # Ghi vào pipe của FFmpeg
            process.stdin.write(frame_data.tobytes())
            
            # Hiển thị tiến độ mỗi 10 frame
            if frame_idx % 10 == 0:
                percent = (frame_idx / total_frames) * 100
                logger.info(f"  [Render] Đang ghép khung hình: {frame_idx}/{total_frames} ({percent:.1f}%)", end="\r")
                
        logger.info(f"\n  [Render] Đã nạp xong {total_frames} frames. Đang chờ FFmpeg hoàn thiện file...")
    except Exception as e:
        logger.info(f"\n  [Render] ⚠️ Lỗi trong quá trình bơm frame: {e}")
    finally:
        process.stdin.close()
        process.wait()

    # Dọn dẹp rác (Garbage Collection)
    if os.path.exists(temp_audio_path) and temp_audio_path != audio_path:
        os.remove(temp_audio_path)
        
    try:
        audio.close()
        if bgm_mix_clip is not None:
            bgm_mix_clip.close()
        bg_clip.close()
    except Exception:
        pass
        
    # Ép Python dọn RAM ngay lập tức
    import gc
    gc.collect()

    # Ghi nhận các video IDs đã dùng
    try:
        record_used_backgrounds(actually_used_assets)
    except Exception as e:
        logger.info(f"  [Video] ⚠️ Không thể lưu vết background đã dùng: {e}")

    logger.info(f"\n✅ Video created successfully: {output_path}")
    return output_path


if __name__ == "__main__":
    make_video("temp/audio.mp3", "temp/subtitles.srt")
