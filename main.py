#!/usr/bin/env python3
"""
main.py - CLI tạo video TikTok từ kịch bản
===========================================
Pipeline: Kịch bản text -> TTS (giọng + phụ đề) -> render với video/ảnh đã có sẵn.

Dùng cho ngách Mẹo Vặt Nhà Bếp & Gia Đình (giai đoạn xây follower).
Không upload tự động — đăng thủ công (xem channel_strategy.md, RULES.md).

Video nền lấy từ thư mục ảnh/video đã upload (vd clip tự tạo bằng Google Flow/Veo,
xem trợ lý "Hoạt hình Veo thủ công" trong web app) — không tự động tải/tạo nền.

Cách dùng:
    python main.py --script script.txt
    python main.py --script script.txt --voice hoaimy --style 1
"""

import argparse
import os
import random
import sys

from core.utils.logger_config import logger
from core.engines.tts import run_tts
from core.engines.html_video_maker import make_video_gsap


def cmd_create(args):
    """Tạo video từ kịch bản text."""
    if not os.path.exists(args.script):
        logger.info(f"❌ Không tìm thấy file kịch bản: {args.script}")
        sys.exit(1)

    supported = (".mp4", ".mov", ".avi", ".mkv", ".webm", ".jpg", ".jpeg", ".png", ".webp")
    os.makedirs(args.image_dir, exist_ok=True)
    media_files = [f for f in os.listdir(args.image_dir) if f.lower().endswith(supported)]

    if not media_files:
        logger.info(
            f"❌ Không tìm thấy ảnh/video nào trong '{args.image_dir}/'.\n"
            f"   Dùng trợ lý 'Hoạt hình Veo thủ công' trong web app (python app.py) để sinh "
            f"prompt, tạo clip bằng Google Flow, tải về đặt tên 1_, 2_, 3_... rồi bỏ vào "
            f"'{args.image_dir}/'."
        )
        sys.exit(1)

    # Nhạc nền (nếu có)
    os.makedirs(args.bgm_dir, exist_ok=True)
    bgm_files = [f for f in os.listdir(args.bgm_dir) if f.lower().endswith((".mp3", ".wav", ".ogg"))]
    bgm_path = os.path.join(args.bgm_dir, random.choice(bgm_files)) if bgm_files else None

    logger.info("=" * 60)
    logger.info("🎬 TIKTOK VIDEO CREATOR (từ kịch bản)")
    logger.info("=" * 60)

    os.makedirs("temp", exist_ok=True)
    audio_path = "temp/audio.mp3"
    srt_path = "temp/subtitles.srt"

    logger.info("\n📌 BƯỚC 1: TTS...")
    run_tts(args.script, audio_path, srt_path, rate=args.rate, voice=args.voice)

    logger.info("\n📌 BƯỚC 2: Render...")
    final_video = make_video_gsap(
        audio_path=audio_path, srt_path=srt_path,
        image_dir=args.image_dir, output_path=args.output,
        style=args.style, position=args.position, bgm_path=bgm_path,
    )

    logger.info(f"\n✅ Video xong: {final_video}")
    logger.info(f"\n{'='*60}\n🎉 HOÀN TẤT!\n{'='*60}")


def main():
    """Main."""
    parser = argparse.ArgumentParser(
        description="🎬 TikTok Video Creator - tạo video từ kịch bản",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--script", default="script.txt")
    parser.add_argument("--output", default="output/final_video.mp4")
    parser.add_argument("--style", type=int, default=1, choices=[1, 2, 3, 4, 5])
    parser.add_argument("--position", default="bottom", choices=["center", "bottom"])
    parser.add_argument("--image-dir", default="uploaded_images", help="Thư mục chứa ảnh/video nền đã upload (vd clip Google Flow)")
    parser.add_argument("--bgm-dir", default="audio_bg")
    parser.add_argument("--rate", default="+50%")
    parser.add_argument("--voice", default="tiktok_nu_1", help="tiktok_nu_1/tiktok_nam_1 (cần TIKTOK_SESSION_ID), banmai (FPT), hoaimy/namminh (Edge dự phòng)")

    args = parser.parse_args()
    cmd_create(args)


if __name__ == "__main__":
    main()
