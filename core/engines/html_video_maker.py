import os
import time
import json
import random
import re
import subprocess
import numpy as np
from moviepy.editor import AudioFileClip, ColorClip
from playwright.sync_api import sync_playwright

from core.utils.logger_config import logger

# Advance subtitle nhẹ để chữ hiện đúng lúc bắt đầu phát âm (bù thời gian animation).
# Drift tích lũy MP3 đã được hiệu chỉnh tại tts.py nên chỉ cần lead nhỏ.
# Tăng nếu sub vẫn chậm, giảm về 0 nếu sub chạy trước tiếng.
SUBTITLE_ADVANCE_SEC = 0.05

from core.engines.video_maker import (
    _collect_visual_sources,
    _prepare_visual_background,
    _select_video_encoder,
    _mix_audio_with_ducking,
    _parse_srt,
    record_used_backgrounds,
    open_ffmpeg_with_log,
    check_ffmpeg_result,
    VIDEO_WIDTH,
    VIDEO_HEIGHT,
    FPS,
)

def parse_subtitle_data(srt_path: str) -> list:
    """Đọc dữ liệu phụ đề cấp từ (word-level) hoặc cấp block (srt) để cấp cho GSAP."""
    words_path = srt_path.replace(".srt", "_words.json")
    if os.path.exists(words_path):
        try:
            with open(words_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [{"text": item["text"], "start": item["start"], "end": item["end"]} for item in data]
        except Exception as e:
            logger.info(f"  [GSAP Render] ⚠️ Không thể đọc file _words.json: {e}. Sử dụng SRT fallback.")
            
    # Fallback: phân tích file SRT thông thường
    subs = []
    if not os.path.exists(srt_path):
        return subs
        
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(
        r"\d+\s*\n"
        r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*\n"
        r"(.*?)(?:\n\n|\Z)",
        re.DOTALL,
    )

    for match in pattern.finditer(content):
        h1, m1, s1, ms1 = int(match[1]), int(match[2]), int(match[3]), int(match[4])
        h2, m2, s2, ms2 = int(match[5]), int(match[6]), int(match[7]), int(match[8])
        start = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0
        end = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0
        text = match[9].strip().replace("\n", " ")
        if text:
            words = text.split()
            duration = end - start
            if len(words) > 0:
                word_dur = duration / len(words)
                for idx, w in enumerate(words):
                    subs.append({
                        "text": w,
                        "start": start + idx * word_dur,
                        "end": start + (idx + 1) * word_dur
                    })
    return subs


def _write_lazy_clip_to_file(bg_clip, filepath: str, duration: float, fps: int):
    """Ghi dữ liệu frame từ LazyBackgroundClip ra file video bằng FFmpeg pipe."""
    ffmpeg_exe, pre_input_args, post_input_args = _select_video_encoder()
    
    ffmpeg_cmd = (
        [ffmpeg_exe, "-y"]
        + pre_input_args
        + [
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}",
            "-r", str(fps),
            "-i", "-",
        ]
        + post_input_args
        + [
            "-an",
            "-vcodec", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            filepath
        ]
    )
    
    process, ffmpeg_log = open_ffmpeg_with_log(ffmpeg_cmd, filepath)
    total_frames = int(duration * fps)

    try:
        for frame_idx in range(total_frames):
            t = frame_idx / fps
            frame_data = bg_clip.get_frame(t).astype(np.uint8)
            process.stdin.write(frame_data.tobytes())
    finally:
        if process.stdin:
            process.stdin.close()
        process.wait()

    check_ffmpeg_result(process, filepath, ffmpeg_log)


def _prepare_bg_only_clip(duration: float, visual_mode: str, visual_sources: list, srt_path: str):
    """Chuẩn bị background video giống hệt như logic trong video_maker.py."""
    subs = _parse_srt(srt_path)
    actually_used_assets = []
    
    if not visual_sources:
        bg_clip = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(30, 30, 30), duration=duration)
    else:
        # LOGIC MULTI-SCENE
        if not subs:
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
                random.shuffle(visual_sources)
            
            if visual_mode == "ai":
                from core.engines import ai_visuals
                import concurrent.futures
                logger.info(f"  [GSAP Render] Đang sinh {len(subs)} ảnh AI bằng đa luồng...")
                
                def generate_ai_bg(sub_item):
                    return ai_visuals.generate_pollinations_image(sub_item["text"])
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    ai_images = list(executor.map(generate_ai_bg, subs))
            else:
                ai_images = []
            
            # LazyBackgroundClip để tránh tràn RAM
            from core.engines.video_maker import LazyBackgroundClip
            bg_clip = LazyBackgroundClip(subs, duration, visual_sources, visual_mode, ai_images)
            actually_used_assets = bg_clip.actually_used
            
    if actually_used_assets:
        record_used_backgrounds(actually_used_assets)
        
    return bg_clip


def make_video_gsap(
    audio_path: str,
    srt_path: str,
    bg_dir: str = "backgrounds",
    image_dir: str = "uploaded_images",
    output_path: str = "output/final_video.mp4",
    style: int = 1,
    position: str = "bottom",
    bgm_path: str = None,
    bgm_start_sec: float = 0.0,
    bgm_volume: float = 0.22,
    visual_mode: str = "pexels",
    uploaded_images=None,
    progress_callback=None
) -> str:
    """Tạo video sử dụng HTML/GSAP và chụp màn hình bằng Playwright, tăng tốc bằng GPU/iGPU."""
    logger.info("🚀 Bắt đầu render video bằng động cơ HTML/GSAP + Playwright...")

    # 1. Load audio và xác định độ dài
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Không tìm thấy file audio: {audio_path}")
    audio = AudioFileClip(audio_path)
    duration = audio.duration
    logger.info(f"  [GSAP Render] Audio Duration: {duration:.2f}s")
    
    # 2. Xử lý Trộn Nhạc Nền (BGM) giống video_maker.py
    ducked_audio_path = None
    temp_audio_path = output_path.replace(".mp4", "_temp_audio.mp3")
    bgm_volume = max(0.0, min(1.0, float(bgm_volume)))
    
    if bgm_path and os.path.exists(bgm_path):
        logger.info(f"  [GSAP Render] Mixing BGM: {os.path.basename(bgm_path)}")
        candidate = output_path.replace(".mp4", "_ducked.mp3")
        if _mix_audio_with_ducking(audio_path, bgm_path, candidate, duration, bgm_start_sec, bgm_volume):
            ducked_audio_path = candidate
            temp_audio_path = candidate
            logger.info("  [GSAP Render] ✅ Đã áp dụng ducking (né giọng) thành công.")
        else:
            logger.info("  [GSAP Render] ⚠️ Ducking thất bại, dùng MoviePy để trộn BGM.")
            try:
                bgm_clip = AudioFileClip(bgm_path)
                bgm_start_sec = max(0.0, float(bgm_start_sec or 0.0))
                if bgm_start_sec >= bgm_clip.duration:
                    bgm_start_sec = 0.0
                bgm_mix_clip = bgm_clip.subclip(bgm_start_sec, bgm_clip.duration)
                if bgm_mix_clip.duration <= 0.05:
                    bgm_mix_clip = bgm_clip
                
                from moviepy.audio.fx.all import audio_loop
                bgm_mix_clip = audio_loop(bgm_mix_clip, duration=duration)
                bgm_mix_clip = bgm_mix_clip.subclip(0, duration)
                bgm_mix_clip = bgm_mix_clip.volumex(bgm_volume)
                
                from moviepy.editor import CompositeAudioClip
                combined_audio = CompositeAudioClip([bgm_mix_clip, audio])
                combined_audio.write_audiofile(temp_audio_path, fps=44100, logger=None)
                logger.info("  [GSAP Render] ✅ Đã trộn nhạc nền thành công bằng MoviePy.")
            except Exception as e:
                logger.info(f"  [GSAP Render] ⚠️ Trộn nhạc nền thất bại: {e}. Sử dụng audio gốc.")
                temp_audio_path = audio_path
    else:
        # Không có BGM, export hoặc dùng luôn audio_path
        try:
            audio.write_audiofile(temp_audio_path, fps=44100, logger=None)
        except Exception:
            temp_audio_path = audio_path

    # 3. Chuẩn bị Visual Background Clip
    visual_sources = _collect_visual_sources(
        bg_dir=bg_dir,
        image_dir=image_dir,
        visual_mode=visual_mode,
        uploaded_images=uploaded_images
    )
    
    bg_clip = _prepare_bg_only_clip(duration, visual_mode, visual_sources, srt_path)
    
    # 4. Xuất background-only video thành temp file để Playwright tải
    temp_bg_path = output_path.replace(".mp4", "_temp_bg.mp4")
    logger.info(f"  [GSAP Render] Đang xuất background clip không chữ ra: {temp_bg_path}...")
    
    if progress_callback:
        progress_callback(35, "Đang xử lý tài nguyên nền...")
        
    if hasattr(bg_clip, "write_videofile"):
        bg_clip.write_videofile(
            temp_bg_path,
            fps=FPS,
            codec="libx264",
            audio=False,
            preset="ultrafast",
            logger=None
        )
    else:
        _write_lazy_clip_to_file(bg_clip, temp_bg_path, duration, FPS)
    bg_clip.close()

    # 5. Phân tích Subtitles thành list cấp từ cho GSAP
    subtitles = parse_subtitle_data(srt_path)
    logger.info(f"  [GSAP Render] Đã nạp {len(subtitles)} từ phụ đề cho GSAP.")

    # 6. Khởi tạo Playwright và chụp ảnh màn hình
    current_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(current_dir, "templates", "gsap_video.html")
    if not os.path.exists(html_path):
        raise FileNotFoundError(f"Không tìm thấy template HTML GSAP: {html_path}")

    ffmpeg_exe, pre_input_args, post_input_args = _select_video_encoder()
    
    # JPEG thay PNG: encode mỗi frame nhanh hơn ~3x, quality 90 trên video 1080p
    # không phân biệt được bằng mắt sau khi libx264 nén lại.
    ffmpeg_cmd = [
        ffmpeg_exe, "-y",
        *pre_input_args,
        "-thread_queue_size", "64",
        "-f", "image2pipe",
        "-vcodec", "mjpeg",
        "-r", str(FPS),
        "-i", "-",               # stdin pipe
        "-i", temp_audio_path,   # Audio input
        *post_input_args,
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_path
    ]
    
    logger.info("  [GSAP Render] Khởi tạo Playwright Headless Chromium...")
    if progress_callback:
        progress_callback(50, "Đang khởi tạo trình duyệt kết xuất...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--enable-gpu", "--use-angle=metal"] if os.name != "nt" else ["--enable-gpu"]
        )
        page = browser.new_page(viewport={"width": VIDEO_WIDTH, "height": VIDEO_HEIGHT})
        
        file_url = f"file://{os.path.abspath(html_path)}"
        page.goto(file_url)
        
        # Áp dụng subtitles, style và vị trí phụ đề
        page.evaluate(f"window.setSubtitles({json.dumps(subtitles)}, {style}, '{position}')")
        
        # Áp dụng video nền
        abs_bg_video = os.path.abspath(temp_bg_path)
        page.evaluate(f"window.setBackgroundVideo('file://{abs_bg_video}')")
        
        # Chờ video và DOM ổn định
        time.sleep(1.5)
        
        logger.info(f"  [GSAP Render] Đang chạy lệnh FFmpeg và ghi frames...")
        process, ffmpeg_log = open_ffmpeg_with_log(ffmpeg_cmd, output_path)

        total_frames = int(duration * FPS)

        try:
            for frame_idx in range(total_frames):
                t = frame_idx / FPS

                # Đồng bộ GSAP timeline — advance thêm SUBTITLE_ADVANCE_SEC để
                # bù cho MP3 frame-padding tích lũy khiến sub bị lag sau tiếng.
                page.evaluate(f"window.seekTo({t + SUBTITLE_ADVANCE_SEC})")

                screenshot_bytes = page.screenshot(type="jpeg", quality=90)
                process.stdin.write(screenshot_bytes)

                if frame_idx % 30 == 0 or frame_idx == total_frames - 1:
                    percent = int(frame_idx / total_frames * 100)
                    overall_progress = 50 + int(percent * 0.45) # 50% -> 95%
                    logger.info(f"   [GSAP Progress] Frame {frame_idx + 1}/{total_frames} ({percent}%)")
                    if progress_callback:
                        progress_callback(overall_progress, f"Đang vẽ chuyển động chữ: {percent}%")

        except Exception as e:
            logger.error(f"❌ Lỗi trong lúc ghi frame GSAP: {e}")
            raise e
        finally:
            if process.stdin:
                process.stdin.close()
            process.wait()
            browser.close()

    check_ffmpeg_result(process, output_path, ffmpeg_log)

    # 7. Dọn dẹp các file rác trung gian để giữ ổ đĩa sạch sẽ
    for temp_f in [temp_bg_path, temp_audio_path]:
        if temp_f and temp_f != audio_path and os.path.exists(temp_f):
            try:
                os.remove(temp_f)
            except Exception:
                pass
                
    if ducked_audio_path and os.path.exists(ducked_audio_path):
        try:
            os.remove(ducked_audio_path)
        except Exception:
            pass

    # 8. Tạo thumbnail
    thumb = _generate_thumbnail(output_path, srt_path, style, duration)
    if thumb:
        logger.info(f"  [Thumbnail] ✅ Đã lưu: {thumb}")
    else:
        logger.info("  [Thumbnail] ⚠️ Không tạo được thumbnail, bỏ qua.")

    logger.info(f"✅ Render GSAP hoàn tất! File lưu tại: {output_path}")
    if progress_callback:
        progress_callback(100, "Hoàn tất tạo video!")

    return output_path


def _generate_thumbnail(video_path: str, srt_path: str, style: int, duration: float):
    """Extract frame từ video đã render, overlay hook text, lưu _cover.jpg."""
    try:
        import io
        import shutil
        from PIL import Image, ImageDraw, ImageFilter

        # --- Màu accent theo style ---
        STYLE_COLORS = {
            1: (247, 194, 4),    # MrBeast yellow
            2: (6, 182, 212),    # Ali cyan
            3: (34, 197, 94),    # Marker green
            4: (255, 255, 255),  # Typewriter white
            5: (251, 191, 36),   # Aesthetic gold
        }
        accent = STYLE_COLORS.get(style, (247, 194, 4))

        # --- 1. Extract frame tại 20% video bằng FFmpeg ---
        ff = shutil.which("ffmpeg")
        if not ff:
            try:
                import imageio_ffmpeg
                ff = imageio_ffmpeg.get_ffmpeg_exe()
            except ImportError:
                return None

        ts = max(0.5, duration * 0.20)
        result = subprocess.run(
            [ff, "-y", "-ss", str(ts), "-i", video_path,
             "-vframes", "1", "-f", "image2", "-vcodec", "png", "pipe:1"],
            capture_output=True, timeout=15
        )
        if not result.stdout:
            return None

        img = Image.open(io.BytesIO(result.stdout)).convert("RGBA")
        w, h = img.size

        # --- 2. Gradient overlay: tối đỉnh + đáy để text nổi ---
        grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(grad)
        for y in range(h):
            t = y / h
            # 0 → 1 → 0 shaped curve, darker near top/bottom
            alpha = int(200 * (1.0 - (2 * t - 1) ** 4))
            alpha = max(80, min(210, alpha))
            draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
        img = Image.alpha_composite(img, grad)

        # --- 3. Đọc hook text từ SRT (block đầu tiên) ---
        hook = ""
        if os.path.exists(srt_path):
            content = open(srt_path, "r", encoding="utf-8").read()
            m = re.search(
                r'\d+\s*\n[\d:,]+ --> [\d:,]+\s*\n(.+?)(?:\n\n|\Z)',
                content, re.DOTALL
            )
            if m:
                hook = m.group(1).strip().replace("\n", " ")

        if not hook:
            img.convert("RGB").save(video_path.rsplit(".", 1)[0] + "_cover.jpg", quality=92)
            return video_path.rsplit(".", 1)[0] + "_cover.jpg"

        # --- 4. Tải font ---
        from core.engines.video_maker import _get_font
        FONT_SIZE = 88
        font = _get_font(FONT_SIZE)
        font_small = _get_font(int(FONT_SIZE * 0.55))

        # --- 5. Word-wrap hook vào 2-3 dòng (max ~16 chars/line) ---
        MAX_CHARS = 16
        words = hook.split()
        lines = []
        cur = ""
        for word in words:
            if len(cur) + len(word) + 1 > MAX_CHARS and cur:
                lines.append(cur)
                cur = word
            else:
                cur += (" " + word) if cur else word
        if cur:
            lines.append(cur)
        lines = lines[:3]  # tối đa 3 dòng

        draw = ImageDraw.Draw(img)

        LINE_H = FONT_SIZE + 24
        total_h = len(lines) * LINE_H
        # Đặt text ở 40% chiều cao (vùng trung tâm-trên)
        start_y = int(h * 0.38) - total_h // 2

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            x = (w - tw) // 2
            y = start_y + i * LINE_H

            # Stroke đen
            stroke_color = (0, 0, 0, 220)
            for dx, dy in [(-5, -5), (5, -5), (-5, 5), (5, 5),
                           (0, -5), (0, 5), (-5, 0), (5, 0)]:
                draw.text((x + dx, y + dy), line, font=font, fill=stroke_color)

            # Dòng đầu màu accent (highlight), các dòng còn lại trắng
            color = (*accent, 255) if i == 0 else (255, 255, 255, 255)
            draw.text((x, y), line, font=font, fill=color)

        # --- 6. Label nhỏ ở dưới ---
        label = "▶ Xem ngay"
        label_bbox = draw.textbbox((0, 0), label, font=font_small)
        lw = label_bbox[2] - label_bbox[0]
        lh = label_bbox[3] - label_bbox[1]
        lx = (w - lw) // 2
        ly = h - 220
        # Pill background
        pad = 18
        draw.rounded_rectangle(
            [lx - pad, ly - pad // 2, lx + lw + pad, ly + lh + pad // 2],
            radius=30, fill=(*accent, 200)
        )
        draw.text((lx, ly), label, font=font_small, fill=(0, 0, 0, 255))

        thumb_path = video_path.rsplit(".", 1)[0] + "_cover.jpg"
        img.convert("RGB").save(thumb_path, quality=92)
        return thumb_path

    except Exception as e:
        logger.warning(f"  [Thumbnail] Lỗi: {e}")
        return None
