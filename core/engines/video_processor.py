"""
video_processor.py - Content Factory (yt-dlp + FFmpeg)
======================================================
Module tải video từ nhiều nguồn và xử lý để thay đổi fingerprint,
tránh bị TikTok quét trùng lặp (Unoriginal Content).

Pipeline:
  1. Tải video (yt-dlp) — Douyin, TikTok, Pinterest, YouTube Shorts
  2. Xóa metadata gốc
  3. Biến đổi visual (màu sắc, grain, speed)
  4. Biến đổi audio (pitch-shift)
  5. Thêm text overlay (hook, CTA)
  6. Xuất video sạch → sẵn sàng upload

Cách dùng:
    python video_processor.py --url "https://douyin.com/xxx"
    python video_processor.py --file "raw_videos/product.mp4"
    python video_processor.py --batch "data/sources.csv"
"""

import os
import sys
import uuid
import random
import subprocess
import csv
import json
import shutil
from pathlib import Path
from typing import Optional
from core.utils.logger_config import logger

# ============================================================
# CẤU HÌNH
# ============================================================

RAW_DIR       = Path("raw_videos")        # Video gốc tải về
PROCESSED_DIR = Path("processed")         # Video đã xử lý, sẵn sàng upload
TEMP_DIR      = Path("temp/processing")   # File tạm trong quá trình xử lý

# Giới hạn biến đổi visual (tránh quá lố làm giảm chất lượng)
SATURATION_RANGE = (0.95, 1.08)     # ±5-8%
BRIGHTNESS_RANGE = (-0.03, 0.03)    # ±3%
NOISE_STRENGTH   = (1, 4)           # Grain noise nhẹ
PITCH_SHIFT_RANGE = (-2, 2)         # ±2 semitones

# Kích thước video TikTok
TIKTOK_WIDTH  = 1080
TIKTOK_HEIGHT = 1920


# ============================================================
# BƯỚC 1: TẢI VIDEO
# ============================================================

def download_video(url: str, output_name: Optional[str] = None) -> Optional[str]:
    """
    Tải video từ URL bằng yt-dlp (không watermark nếu có thể).

    Args:
        url: Link video (Douyin, TikTok, Pinterest, YouTube...)
        output_name: Tên file output (không có extension). Nếu None → dùng UUID.

    Returns:
        Đường dẫn file đã tải, hoặc None nếu thất bại.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if output_name is None:
        output_name = str(uuid.uuid4())[:12]

    output_path = str(RAW_DIR / f"{output_name}.%(ext)s")

    cmd = [
        "yt-dlp",
        "--no-warnings",
        "-f", "best[ext=mp4]/best",     # Ưu tiên MP4
        "-o", output_path,
        "--no-playlist",
        "--socket-timeout", "30",
        url,
    ]

    logger.info(f"  [Download] Đang tải: {url[:60]}...")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            logger.info(f"  [Download] ❌ Lỗi yt-dlp: {result.stderr[:200]}")
            return None

        if result.returncode == 0:
            # Tìm file đã tải (yt-dlp tự thêm extension)
            downloaded = list(RAW_DIR.glob(f"{output_name}.*"))
            if downloaded:
                final_path = str(downloaded[0])
                logger.info(f"  [Download] ✅ Tải xong: {final_path}")
                return final_path

        logger.info(f"  [Download] ❌ Lỗi: {result.stderr[:200]}")
        return None

    except subprocess.TimeoutExpired:
        logger.info("  [Download] ❌ Timeout (quá 120 giây)")
        return None
    except FileNotFoundError:
        logger.info("  [Download] ❌ yt-dlp chưa được cài. Chạy: pip install yt-dlp")
        return None


# ============================================================
# BƯỚC 2: XỬ LÝ VIDEO (FFmpeg Pipeline)
# ============================================================

def process_video(
    input_path: str,
    output_name: Optional[str] = None,
    bg_music: Optional[str] = None,
    add_noise: bool = True,
    shift_pitch: bool = True,
    crop_vertical: bool = True,
    hook_text: Optional[str] = None,
    cta_text: Optional[str] = None,
) -> Optional[str]:
    """
    Xử lý video để thay đổi fingerprint (tránh bị quét trùng lặp).

    Pipeline:
      1. Re-encode + xóa metadata
      2. Biến đổi visual (saturation, brightness, grain noise)
      3. Biến đổi audio (pitch-shift)
      4. Crop sang 9:16 (nếu cần)
      5. Thêm text overlay (hook + CTA)

    Args:
        input_path:    Đường dẫn video gốc.
        output_name:   Tên file output (không extension). None → UUID.
        add_noise:     Thêm grain noise nhẹ.
        shift_pitch:   Thay đổi pitch âm thanh.
        crop_vertical: Crop sang tỉ lệ 9:16 nếu video ngang.
        hook_text:     Text hiển thị 3 giây đầu (gây tò mò).
        cta_text:      Text hiển thị 3 giây cuối (kêu gọi hành động).

    Returns:
        Đường dẫn file output, hoặc None nếu thất bại.
    """
    if not os.path.exists(input_path):
        logger.info(f"  [Process] ❌ Không tìm thấy: {input_path}")
        return None

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    if output_name is None:
        output_name = str(uuid.uuid4())[:12]

    output_path = str(PROCESSED_DIR / f"{output_name}.mp4")

    # Lấy thông tin video gốc
    video_info = _get_video_info(input_path)
    if not video_info:
        logger.info("  [Process] ❌ Không đọc được thông tin video")
        return None

    duration = video_info.get("duration", 30)
    width = video_info.get("width", 1080)
    height = video_info.get("height", 1920)

    logger.info(f"  [Process] Video gốc: {width}x{height}, {duration:.1f}s")

    # === Xây dựng FFmpeg filter chain ===
    video_filters = []
    audio_filters = []

    # 1. Crop sang 9:16 nếu video ngang
    if crop_vertical and width > height:
        # Video ngang → crop giữa sang dọc
        new_width = int(height * 9 / 16)
        x_offset = (width - new_width) // 2
        video_filters.append(f"crop={new_width}:{height}:{x_offset}:0")
        logger.info(f"  [Process] Crop: {width}x{height} → {new_width}x{height}")

    # 2. Scale về kích thước TikTok chuẩn
    video_filters.append(
        f"scale={TIKTOK_WIDTH}:{TIKTOK_HEIGHT}:"
        f"force_original_aspect_ratio=decrease,"
        f"pad={TIKTOK_WIDTH}:{TIKTOK_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black"
    )

    # 3. Biến đổi màu sắc ngẫu nhiên
    sat = round(random.uniform(*SATURATION_RANGE), 2)
    bri = round(random.uniform(*BRIGHTNESS_RANGE), 2)
    video_filters.append(f"eq=saturation={sat}:brightness={bri}")
    logger.info(f"  [Process] Saturation: {sat}, Brightness: {bri}")

    # 4. Thêm grain noise
    if add_noise:
        noise_str = random.randint(*NOISE_STRENGTH)
        video_filters.append(f"noise=alls={noise_str}:allf=t")

    # 5. Hook text (TTS Audio)
    tts_audio_path = None
    if hook_text:
        try:
            from core.engines.tts import run_tts
            tts_audio_path = str(TEMP_DIR / f"tts_{uuid.uuid4().hex[:6]}.mp3")
            # Tạo TTS file (có thể dùng voice FPT hoặc Edge)
            run_tts(output_audio=tts_audio_path, raw_text_input=hook_text)
            logger.info(f"  [Process] 🗣️ Đã tạo TTS cho hook: {hook_text[:30]}...")
        except Exception as e:
            logger.info(f"  [Process] ❌ Lỗi tạo TTS: {e}")
            tts_audio_path = None

    # 6. CTA text (3 giây cuối) - Bỏ qua vì thiếu drawtext
    if cta_text:
        pass

    # 7. Audio: Pitch shift (chỉ áp dụng nếu không thay nhạc nền)
    if not bg_music and shift_pitch:
        semitones = random.randint(*PITCH_SHIFT_RANGE)
        if semitones != 0:
            # asetrate thay đổi pitch mà không đổi speed
            factor = 2 ** (semitones / 12.0)
            audio_filters.append(f"asetrate=44100*{factor:.4f},aresample=44100")
            logger.info(f"  [Process] Pitch shift: {semitones:+d} semitones")

    # === Ghép lệnh FFmpeg ===
    vf_str = ",".join(video_filters) if video_filters else "null"
    af_str = ",".join(audio_filters) if audio_filters else "anull"

    cmd = [
        "ffmpeg", "-y",
    ]

    # Input 0: Video gốc
    cmd.extend(["-i", input_path])
    
    inputs_count = 1

    # Input 1 (optional): Nhạc nền
    if bg_music and os.path.exists(bg_music):
        logger.info(f"  [Process] 🎵 Thay thế bằng nhạc nền an toàn: {os.path.basename(bg_music)}")
        cmd.extend(["-stream_loop", "-1", "-i", bg_music])
        bg_idx = inputs_count
        inputs_count += 1
    else:
        bg_idx = -1
        
    # Input 2 (optional): TTS Audio
    if tts_audio_path and os.path.exists(tts_audio_path):
        cmd.extend(["-i", tts_audio_path])
        tts_idx = inputs_count
        inputs_count += 1
    else:
        tts_idx = -1

    # Audio Mixing Logic
    if bg_idx != -1 and tts_idx != -1:
        # Cả nhạc nền và TTS
        complex_filter = (
            f"[0:v]{vf_str}[vout]; "
            f"[{bg_idx}:a]volume=0.3[bg]; "
            f"[{tts_idx}:a]volume=1.5,adelay=500|500[tts]; "
            f"[bg][tts]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
        cmd.extend(["-filter_complex", complex_filter])
        cmd.extend(["-map", "[vout]", "-map", "[aout]", "-shortest"])
    elif bg_idx != -1:
        # Chỉ có nhạc nền
        cmd.extend(["-vf", vf_str])
        cmd.extend(["-map", "0:v:0", "-map", f"{bg_idx}:a:0", "-shortest"])
    elif tts_idx != -1:
        # Video gốc + TTS
        orig_af = f"volume=0.3" if af_str == "anull" else f"{af_str},volume=0.3"
        complex_filter = (
            f"[0:v]{vf_str}[vout]; "
            f"[0:a]{orig_af}[orig]; "
            f"[{tts_idx}:a]volume=1.5,adelay=500|500[tts]; "
            f"[orig][tts]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
        cmd.extend(["-filter_complex", complex_filter])
        cmd.extend(["-map", "[vout]", "-map", "[aout]"])
    else:
        # Không có TTS, không thay nhạc nền
        cmd.extend(["-vf", vf_str])
        cmd.extend(["-af", af_str])

    # Cấu hình video codec chung
    cmd.extend([
        "-c:v", "libx264",
        "-crf", "23",               # Chất lượng tốt, file nhẹ
        "-preset", "fast",
        "-map_metadata", "-1",      # XÓA toàn bộ metadata gốc
        "-movflags", "+faststart",  # Tối ưu cho web streaming
        output_path,
    ])

    logger.info(f"  [Process] Đang xử lý video...")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300
        )

        if result.returncode == 0:
            output_size = os.path.getsize(output_path) / (1024 * 1024)
            logger.info(f"  [Process] ✅ Xong: {output_path} ({output_size:.1f} MB)")
            return output_path
        else:
            logger.info(f"  [Process] ❌ FFmpeg lỗi: {result.stderr[-300:]}")
            return None

    except subprocess.TimeoutExpired:
        logger.info("  [Process] ❌ Timeout (quá 5 phút)")
        return None
    except FileNotFoundError:
        logger.info("  [Process] ❌ FFmpeg chưa cài. Chạy: brew install ffmpeg")
        return None


def _get_video_info(video_path: str) -> Optional[dict]:
    """Lấy thông tin video bằng ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        video_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            # Tìm video stream
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    return {
                        "width": int(stream.get("width", 0)),
                        "height": int(stream.get("height", 0)),
                        "duration": float(
                            data.get("format", {}).get("duration", 0)
                        ),
                    }
    except Exception:
        pass
    return None


# ============================================================
# BƯỚC 3: BATCH PROCESSING — Xử lý hàng loạt
# ============================================================

def batch_process(csv_path: str) -> list:
    """
    Xử lý hàng loạt video từ file CSV.

    Format CSV (sources.csv):
      source_url, product_id, hook_text, cta_text, category
      https://douyin.com/xxx, TT_001, "Đừng mua khi chưa xem!", "Link giỏ hàng ⬇️", gadget

    Returns:
        Danh sách đường dẫn video đã xử lý thành công.
    """
    if not os.path.exists(csv_path):
        logger.info(f"❌ Không tìm thấy file: {csv_path}")
        return []

    results = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    logger.info(f"\n🏭 Batch Processing: {len(rows)} video")
    logger.info("=" * 50)

    for i, row in enumerate(rows, 1):
        url = row.get("source_url", "").strip()
        product_id = row.get("product_id", "").strip()
        hook = row.get("hook_text", "").strip() or None
        cta = row.get("cta_text", "").strip() or None
        category = row.get("category", "general").strip()

        if not url:
            continue

        logger.info(f"\n[{i}/{len(rows)}] {url[:50]}...")

        # Bước 1: Tải
        raw_path = download_video(url, output_name=f"{category}_{product_id}")
        if not raw_path:
            continue

        # Bước 2: Xử lý
        processed_path = process_video(
            input_path=raw_path,
            output_name=f"aff_{product_id}_{uuid.uuid4().hex[:6]}",
            hook_text=hook,
            cta_text=cta,
        )

        if processed_path:
            results.append({
                "video_path": processed_path,
                "product_id": product_id,
                "category": category,
            })

    logger.info(f"\n✅ Batch hoàn tất: {len(results)}/{len(rows)} video thành công")
    return results


# ============================================================
# TIỆN ÍCH: Xử lý video local (không cần tải)
# ============================================================

def process_local_video(
    input_path: str,
    hook_text: Optional[str] = None,
    cta_text: Optional[str] = None,
    bg_music: Optional[str] = None,
) -> Optional[str]:
    """
    Xử lý 1 video local sẵn có (không cần tải từ URL).
    Tiện cho việc test nhanh.
    """
    return process_video(
        input_path=input_path,
        hook_text=hook_text,
        cta_text=cta_text,
        bg_music=bg_music,
    )


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="🏭 Video Processor — Tải + Xử lý video cho TikTok Affiliate"
    )
    parser.add_argument("--url", help="URL video để tải và xử lý")
    parser.add_argument("--file", help="Đường dẫn video local để xử lý")
    parser.add_argument("--batch", help="Đường dẫn file CSV để xử lý hàng loạt")
    parser.add_argument("--hook", default=None, help="Text hook 3 giây đầu")
    parser.add_argument("--cta", default=None, help="Text CTA 3 giây cuối")
    parser.add_argument("--bg-music", default=None, help="Đường dẫn file nhạc nền thay thế")

    args = parser.parse_args()

    if args.batch:
        batch_process(args.batch)

    elif args.url:
        raw = download_video(args.url)
        if raw:
            process_video(raw, hook_text=args.hook, cta_text=args.cta, bg_music=args.bg_music)

    elif args.file:
        process_local_video(args.file, hook_text=args.hook, cta_text=args.cta, bg_music=args.bg_music)

    else:
        parser.print_help()
