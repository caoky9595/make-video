#!/usr/bin/env python3
"""
main.py - TikTok Affiliate Automation Pipeline
================================================
Hệ thống tự động hoá TikTok Affiliate: Tải video → Xử lý → Tạo TTS →
Render → Đăng lên nhiều tài khoản.

Chế độ hoạt động:
  1. CREATE   — Tạo video từ kịch bản (giữ nguyên chức năng cũ)
  2. PROCESS  — Tải + xử lý video từ nguồn bên ngoài (Douyin, TikTok...)
  3. FULL     — Pipeline đầy đủ: Process → TTS → Render → Upload
  4. NICK     — Quản lý tài khoản

Cách dùng:
    # === Chế độ cũ (tạo video từ kịch bản) ===
    python main.py create --script script.txt
    python main.py create --script script.txt --upload

    # === Chế độ mới (affiliate pipeline) ===
    python main.py process --url "https://douyin.com/xxx" --hook "Đừng mua khi chưa xem!"
    python main.py process --file "raw_video.mp4"
    python main.py process --batch data/sources.csv

    # === Pipeline đầy đủ ===
    python main.py full --url "https://douyin.com/xxx" --tts-script "Mùa hè nóng quá..."
    python main.py full --batch data/sources.csv --nick nick_01

    # === Quản lý nick ===
    python main.py nick list
    python main.py nick add nick_01
    python main.py nick login nick_01
    python main.py nick plan
"""

import argparse
import os
import sys
from core.utils.logger_config import logger

from core.engines.tts import run_tts
from core.engines.video_maker import make_video
from core.automation.uploader import login_tiktok, upload_video, upload_queue
from core.engines.bg_finder import find_and_download_background
from core.engines.video_processor import download_video, process_video, batch_process
from core.utils.caption_builder import build_caption, auto_select_format
from core.automation.nick_manager import (
    add_nick, remove_nick, list_nicks,
    get_upload_plan, record_upload, get_available_nicks,
)


# ============================================================
# COMMAND: CREATE (giữ nguyên chức năng cũ)
# ============================================================

def cmd_create(args):
    """Tạo video từ kịch bản text (chế độ cũ)."""
    if not os.path.exists(args.script):
        logger.info(f"❌ Không tìm thấy file kịch bản: {args.script}")
        sys.exit(1)

    with open(args.script, "r", encoding="utf-8") as f:
        script_text = f.read().strip()

    script_parts = [script_text]
    if args.auto_split:
        try:
            from core.utils.ai_splitter import split_story_script
            result = split_story_script(script_text)
            if result is None:
                sys.exit(1)
            elif len(result) > 1:
                script_parts = result
                logger.info(f"  [AI Splitter] ✅ Đã chia thành {len(script_parts)} phần!")
        except ImportError:
            logger.info("❌ Không tìm thấy module ai_splitter.py")

    # Tự động tìm video nền nếu cần
    supported = (".mp4", ".mov", ".avi", ".mkv", ".webm")
    os.makedirs(args.bg_dir, exist_ok=True)
    bg_videos = [f for f in os.listdir(args.bg_dir) if f.lower().endswith(supported)]

    if not bg_videos and args.auto_bg and not args.no_auto_bg:
        logger.info("\n🔍 Không có video nền. Tự động tìm trên Pexels...")
        find_and_download_background(script_text, output_dir=args.bg_dir)
        bg_videos = [f for f in os.listdir(args.bg_dir) if f.lower().endswith(supported)]

    if not bg_videos:
        logger.info(f"❌ Không tìm thấy video nền trong '{args.bg_dir}/'")
        sys.exit(1)

    # Nhạc nền
    os.makedirs(args.bgm_dir, exist_ok=True)
    bgm_files = [f for f in os.listdir(args.bgm_dir) if f.lower().endswith((".mp3", ".wav", ".ogg"))]
    bgm_path = None
    if bgm_files:
        import random
        bgm_path = os.path.join(args.bgm_dir, random.choice(bgm_files))

    # Pipeline
    logger.info("=" * 60)
    logger.info("🎬 TIKTOK VIDEO CREATOR (từ kịch bản)")
    logger.info("=" * 60)

    for i, part_text in enumerate(script_parts):
        part_num = i + 1
        is_multi = len(script_parts) > 1

        if is_multi:
            logger.info(f"\n{'='*50}\n🔄 PHẦN {part_num}/{len(script_parts)}\n{'='*50}")
            temp_script = f"temp/script_part{part_num}.txt"
            os.makedirs("temp", exist_ok=True)
            with open(temp_script, "w", encoding="utf-8") as f:
                f.write(part_text)
            current_script = temp_script
            audio_path = f"temp/audio_part{part_num}.mp3"
            srt_path = f"temp/subtitles_part{part_num}.srt"
            base, ext = os.path.splitext(args.output)
            current_output = f"{base}_part{part_num}{ext}"
        else:
            current_script = args.script
            audio_path = "temp/audio.mp3"
            srt_path = "temp/subtitles.srt"
            current_output = args.output

        logger.info(f"\n📌 BƯỚC 1: TTS...")
        run_tts(current_script, audio_path, srt_path, rate=args.rate, voice=args.voice)

        logger.info(f"\n📌 BƯỚC 2: Render...")
        final_video = make_video(
            audio_path=audio_path, srt_path=srt_path,
            bg_dir=args.bg_dir, output_path=current_output,
            style=args.style, position=args.position, bgm_path=bgm_path,
        )

        if args.upload:
            logger.info(f"\n📌 BƯỚC 3: Upload...")
            tags = [t.strip() for t in args.tags.split(",") if t.strip()]
            title = f"{args.title} (Phần {part_num})" if args.title and is_multi else args.title
            upload_video(video_path=final_video, title=title, tags=tags, nick_name=args.nick)
        else:
            logger.info(f"\n✅ Video xong: {final_video}")

    logger.info(f"\n{'='*60}\n🎉 HOÀN TẤT!\n{'='*60}")


# ============================================================
# COMMAND: PROCESS (tải + xử lý video nguồn)
# ============================================================

def cmd_process(args):
    """Tải và xử lý video từ nguồn bên ngoài."""
    logger.info("=" * 60)
    logger.info("🏭 CONTENT FACTORY")
    logger.info("=" * 60)

    if args.batch:
        results = batch_process(args.batch)
        logger.info(f"\n✅ {len(results)} video đã xử lý xong trong processed/")

    elif args.url:
        raw = download_video(args.url)
        if raw:
            output = process_video(raw, hook_text=args.hook, cta_text=args.cta, bg_music=getattr(args, 'bg_music', None))
            if output:
                logger.info(f"\n✅ Video sẵn sàng: {output}")

    elif args.file:
        output = process_video(args.file, hook_text=args.hook, cta_text=args.cta, bg_music=getattr(args, 'bg_music', None))
        if output:
            logger.info(f"\n✅ Video sẵn sàng: {output}")

    else:
        logger.info("❌ Phải chỉ định --url, --file, hoặc --batch")


# ============================================================
# COMMAND: FULL (pipeline đầy đủ)
# ============================================================

def cmd_full(args):
    """Pipeline đầy đủ: Tải → Xử lý → TTS → Upload."""
    logger.info("=" * 60)
    logger.info("🚀 FULL AFFILIATE PIPELINE")
    logger.info("=" * 60)

    # Bước 1: Tải/xử lý video
    if args.url:
        logger.info("\n📌 BƯỚC 1: Tải video...")
        raw = download_video(args.url)
        if not raw:
            logger.info("❌ Tải video thất bại")
            return
        logger.info("\n📌 BƯỚC 2: Xử lý video...")
        processed = process_video(raw, hook_text=args.hook, cta_text=args.cta, bg_music=getattr(args, 'bg_music', None))
    elif args.file:
        logger.info("\n📌 BƯỚC 1-2: Xử lý video local...")
        processed = process_video(args.file, hook_text=args.hook, cta_text=args.cta, bg_music=getattr(args, 'bg_music', None))
    else:
        logger.info("❌ Phải chỉ định --url hoặc --file")
        return

    if not processed:
        logger.info("❌ Xử lý video thất bại")
        return

    # Bước 2.5: Thêm TTS (nếu có script)
    if args.tts_script:
        logger.info("\n📌 BƯỚC 3: Tạo TTS voiceover...")
        os.makedirs("temp", exist_ok=True)
        tts_script_file = "temp/tts_script_temp.txt"
        with open(tts_script_file, "w", encoding="utf-8") as f:
            f.write(args.tts_script)

        tts_audio = "temp/tts_overlay.mp3"
        tts_srt = "temp/tts_overlay.srt"
        run_tts(tts_script_file, tts_audio, tts_srt, voice=args.voice)

        # TODO: Ghép TTS audio vào processed video bằng FFmpeg
        logger.info(f"  ✅ TTS audio: {tts_audio}")
        logger.info(f"  ⚠️  Ghép TTS vào video sẽ được tích hợp trong bản sau")

    # Bước 3: Tạo caption
    logger.info("\n📌 BƯỚC 4: Tạo caption...")
    fmt = auto_select_format()
    caption_data = build_caption(
        template_type=fmt,
        category=args.category,
        product=args.product or "sản phẩm",
        price=args.price or "giá tốt",
        problem=args.hook or "Vấn đề phổ biến",
        result="Hiệu quả bất ngờ",
    )
    logger.info(f"  Format: {fmt}")
    logger.info(f"  Caption: {caption_data['caption'][:80]}...")

    # Bước 4: Upload
    nick = args.nick or "default"
    logger.info(f"\n📌 BƯỚC 5: Upload cho nick [{nick}]...")
    success = upload_video(
        video_path=processed,
        title=caption_data["caption"],
        tags=caption_data["tags"],
        nick_name=nick,
    )

    if success:
        record_upload(nick, success=True)
        logger.info(f"\n🎉 PIPELINE HOÀN TẤT!")
    else:
        logger.info(f"\n❌ Upload thất bại")


# ============================================================
# COMMAND: NICK (quản lý tài khoản)
# ============================================================

def cmd_nick(args):
    """Quản lý tài khoản TikTok."""
    subcmd = args.nick_cmd

    if subcmd == "list":
        list_nicks(status_filter=args.status)

    elif subcmd == "add":
        if not args.name:
            logger.info("❌ Thiếu tên nick. VD: python main.py nick add nick_01")
            return
        add_nick(args.name, username=args.username or "")

    elif subcmd == "remove":
        if not args.name:
            logger.info("❌ Thiếu tên nick. VD: python main.py nick remove nick_01")
            return
        remove_nick(args.name)

    elif subcmd == "login":
        nick = args.name or "default"
        login_tiktok(nick_name=nick)

    elif subcmd == "plan":
        get_upload_plan()

    else:
        logger.info("❌ Lệnh nick không hợp lệ. Dùng: list, add, remove, login, plan")


# ============================================================
# ARGUMENT PARSER
# ============================================================

def main():
    """Main."""
    parser = argparse.ArgumentParser(
        description="🚀 TikTok Affiliate Automation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Chế độ hoạt động")

    # --- CREATE (giữ nguyên chức năng cũ) ---
    p_create = subparsers.add_parser("create", help="Tạo video từ kịch bản text")
    p_create.add_argument("--script", default="script.txt")
    p_create.add_argument("--upload", action="store_true")
    p_create.add_argument("--title", default="")
    p_create.add_argument("--tags", default="fyp,viral,tiktokvietnam,review,affiliate")
    p_create.add_argument("--output", default="output/final_video.mp4")
    p_create.add_argument("--style", type=int, default=1, choices=[1, 2, 3, 4])
    p_create.add_argument("--position", default="bottom", choices=["center", "bottom"])
    p_create.add_argument("--bg-dir", default="backgrounds")
    p_create.add_argument("--bgm-dir", default="audio_bg")
    p_create.add_argument("--rate", default="+20%")
    p_create.add_argument("--voice", default="hoaimy")
    p_create.add_argument("--auto-split", action="store_true")
    p_create.add_argument("--auto-bg", action="store_true", default=True)
    p_create.add_argument("--no-auto-bg", action="store_true")
    p_create.add_argument("--nick", default="default")

    # --- PROCESS (tải + xử lý video) ---
    p_process = subparsers.add_parser("process", help="Tải + xử lý video từ nguồn ngoài")
    p_process.add_argument("--url", help="URL video (Douyin, TikTok...)")
    p_process.add_argument("--file", help="Video local")
    p_process.add_argument("--batch", help="File CSV danh sách video")
    p_process.add_argument("--hook", help="Text hook 3 giây đầu")
    p_process.add_argument("--cta", help="Text CTA 3 giây cuối")
    p_process.add_argument("--bg-music", help="Đường dẫn file nhạc nền an toàn để thay thế nhạc gốc")

    # --- FULL (pipeline đầy đủ) ---
    p_full = subparsers.add_parser("full", help="Pipeline đầy đủ: Tải → Xử lý → Upload")
    p_full.add_argument("--url", help="URL video")
    p_full.add_argument("--file", help="Video local")
    p_full.add_argument("--hook", help="Text hook 3 giây đầu")
    p_full.add_argument("--cta", help="Text CTA 3 giây cuối")
    p_full.add_argument("--bg-music", help="Đường dẫn file nhạc nền an toàn để thay thế nhạc gốc")
    p_full.add_argument("--tts-script", help="Nội dung voiceover TTS tiếng Việt")
    p_full.add_argument("--voice", default="hoaimy")
    p_full.add_argument("--nick", default="default", help="Tên nick để upload")
    p_full.add_argument("--category", default="general", help="Ngách: gadget, fashion, beauty, food")
    p_full.add_argument("--product", default="", help="Tên sản phẩm")
    p_full.add_argument("--price", default="", help="Giá sản phẩm")

    # --- NICK (quản lý tài khoản) ---
    p_nick = subparsers.add_parser("nick", help="Quản lý tài khoản TikTok")
    p_nick.add_argument("nick_cmd", choices=["list", "add", "remove", "login", "plan"])
    p_nick.add_argument("name", nargs="?", default=None, help="Tên nick")
    p_nick.add_argument("--username", default="", help="TikTok username")
    p_nick.add_argument("--status", default=None, help="Lọc theo trạng thái")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        logger.info("\n💡 Bắt đầu nhanh:")
        logger.info("  python main.py create --script script.txt          # Tạo video từ kịch bản")
        logger.info("  python main.py process --url 'https://...'         # Xử lý video từ URL")
        logger.info("  python main.py full --file video.mp4 --nick test   # Pipeline đầy đủ")
        logger.info("  python main.py nick list                           # Xem danh sách nick")
        return

    commands = {
        "create": cmd_create,
        "process": cmd_process,
        "full": cmd_full,
        "nick": cmd_nick,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
