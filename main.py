#!/usr/bin/env python3
"""
main.py - TikTok Video Auto-Creator Pipeline
=============================================
Hệ thống tạo video TikTok tự động.

Cách dùng:
    # Tạo video từ kịch bản
    python main.py

    # Tạo video + tự động upload lên TikTok
    python main.py --upload

    # Đăng nhập TikTok (chỉ cần làm 1 lần)
    python main.py --login

    # Chỉ định file kịch bản khác
    python main.py --script my_script.txt

    # Chỉ định tiêu đề và hashtag
    python main.py --upload --title "Review tool AI" --tags fyp,viral,review
"""

import argparse
import os
import sys

from tts import run_tts
from video_maker import make_video
from uploader import login_tiktok, upload_video
from bg_finder import find_and_download_background


def main():
    parser = argparse.ArgumentParser(
        description="🎬 TikTok Video Auto-Creator Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ sử dụng:
  python main.py                              # Tạo video từ script.txt
  python main.py --script idea.txt            # Tạo video từ file khác
  python main.py --upload                     # Tạo video + upload TikTok
  python main.py --login                      # Đăng nhập TikTok lần đầu
  python main.py --upload --title "Mẹo hay"   # Upload với tiêu đề tùy chỉnh
        """,
    )

    parser.add_argument(
        "--script",
        default="script.txt",
        help="Đường dẫn tới file kịch bản (mặc định: script.txt)",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Tự động upload video lên TikTok sau khi render",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Mở trình duyệt để đăng nhập TikTok (lưu cookie)",
    )
    parser.add_argument(
        "--title",
        default="",
        help="Tiêu đề/Caption cho video TikTok",
    )
    parser.add_argument(
        "--tags",
        default="fyp,viral,tiktokvietnam,review,affiliate",
        help="Hashtag cho video, ngăn cách bằng dấu phẩy (mặc định: fyp,viral,...)",
    )
    parser.add_argument(
        "--output",
        default="output/final_video.mp4",
        help="Đường dẫn file video đầu ra (mặc định: output/final_video.mp4)",
    )
    parser.add_argument(
        "--bg-dir",
        default="backgrounds",
        help="Thư mục chứa video nền (mặc định: backgrounds/)",
    )
    parser.add_argument(
        "--rate",
        default="+20%",
        help="Tốc độ đọc. VD: '+0%%' (bình thường), '+20%%' (nhanh hơn), '-15%%' (chậm hơn). Mặc định: +20%%",
    )
    parser.add_argument(
        "--auto-bg",
        action="store_true",
        default=True,
        help="Tự động tìm và tải video nền từ Pexels nếu thư mục backgrounds/ trống (mặc định: bật)",
    )
    parser.add_argument(
        "--no-auto-bg",
        action="store_true",
        help="Tắt tự động tải video nền, chỉ dùng video có sẵn trong backgrounds/",
    )
    parser.add_argument(
        "--voice",
        default="hoaimy",
        choices=["hoaimy", "namminh"],
        help="Giọng đọc: 'hoaimy' (nữ - mặc định) hoặc 'namminh' (nam)",
    )

    args = parser.parse_args()

    # === Chế độ đăng nhập TikTok ===
    if args.login:
        login_tiktok()
        return

    # === Kiểm tra file kịch bản ===
    if not os.path.exists(args.script):
        print(f"❌ Không tìm thấy file kịch bản: {args.script}")
        print(f"   Hãy tạo file '{args.script}' với nội dung kịch bản video của bạn.")
        sys.exit(1)

    # Đọc nội dung kịch bản
    with open(args.script, "r", encoding="utf-8") as f:
        script_text = f.read().strip()

    # === Tự động tìm video nền nếu cần ===
    supported = (".mp4", ".mov", ".avi", ".mkv", ".webm")
    os.makedirs(args.bg_dir, exist_ok=True)
    bg_videos = [f for f in os.listdir(args.bg_dir) if f.lower().endswith(supported)]

    if not bg_videos and args.auto_bg and not args.no_auto_bg:
        print("\n🔍 Không có video nền. Tự động tìm trên Pexels...")
        find_and_download_background(script_text, output_dir=args.bg_dir)
        # Kiểm tra lại sau khi tải
        bg_videos = [f for f in os.listdir(args.bg_dir) if f.lower().endswith(supported)]

    if not bg_videos:
        print(f"❌ Không tìm thấy video nền nào trong '{args.bg_dir}/'.")
        print(f"   Hãy tải video dọc (9:16) từ Pexels.com và bỏ vào thư mục này.")
        print(f"   Hoặc chạy lại với flag --auto-bg để tự động tải.")
        sys.exit(1)

    # === Pipeline chính ===
    print("=" * 60)
    print("🎬 TIKTOK VIDEO AUTO-CREATOR")
    print("=" * 60)

    # Đường dẫn file tạm
    audio_path = os.path.join("temp", "audio.mp3")
    srt_path = os.path.join("temp", "subtitles.srt")

    # Bước 1: Text-to-Speech
    print("\n📌 BƯỚC 1: Tạo giọng đọc từ kịch bản...")
    print(f"   Script: {args.script}")
    print(f"   Tốc độ đọc: {args.rate}")
    print(f"   Giọng đọc: {args.voice}")
    run_tts(args.script, audio_path, srt_path, rate=args.rate, voice=args.voice)

    # Bước 2: Render Video
    print("\n📌 BƯỚC 2: Render video...")
    output_path = make_video(
        audio_path=audio_path,
        srt_path=srt_path,
        bg_dir=args.bg_dir,
        output_path=args.output,
    )

    # Bước 3: Upload (nếu có flag --upload)
    if args.upload:
        print("\n📌 BƯỚC 3: Upload lên TikTok...")
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        upload_video(
            video_path=output_path,
            title=args.title,
            tags=tags,
        )
    else:
        print("\n" + "=" * 60)
        print(f"✅ HOÀN TẤT! Video đã được tạo tại: {output_path}")
        print(f"   Để upload lên TikTok, chạy:")
        print(f"   python main.py --upload")
        print("=" * 60)


if __name__ == "__main__":
    main()
