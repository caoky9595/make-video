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
        "--style",
        type=int,
        default=1,
        choices=[1, 2, 3, 4],
        help="Kiểu dáng subtitle: 1 (Ali Abdaal - Mặc định), 2 (Marker Box), 3 (MrBeast), 4 (Typewriter)",
    )
    parser.add_argument(
        "--position",
        default="bottom",
        choices=["center", "bottom"],
        help="Vị trí subtitle: 'center' (giữa) hoặc 'bottom' (dưới - mặc định)",
    )
    parser.add_argument(
        "--bg-dir",
        default="backgrounds",
        help="Thư mục chứa video nền (mặc định: backgrounds/)",
    )
    parser.add_argument(
        "--bgm-dir",
        default="audio_bg",
        help="Thư mục chứa file nhạc nền (mặc định: audio_bg/)",
    )
    parser.add_argument(
        "--rate",
        default="+20%",
        help="Tốc độ đọc. VD: '+0%%' (bình thường), '+20%%' (nhanh hơn), '-15%%' (chậm hơn). Mặc định: +20%%",
    )
    parser.add_argument(
        "--auto-split",
        action="store_true",
        help="Sử dụng AI Google Gemini để cắt cốt truyện dài thành nhiều Phần (Part 1, Part 2) tại vị trí gay cấn nhất.",
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
        choices=["hoaimy", "namminh", "banmai", "thuminh", "leminh", "myan", "giahuy", "lannhi", "linhsan"],
        help=(
            "Giọng đọc. Edge-TTS: 'hoaimy' (nữ Bắc), 'namminh' (nam Bắc). "
            "FPT.AI: 'banmai' (nữ Bắc), 'thuminh' (nữ Bắc), 'leminh' (nam Bắc), "
            "'myan' (nữ Trung), 'giahuy' (nam Trung), 'lannhi' (nữ Nam), 'linhsan' (nữ Nam). "
            "Mặc định: hoaimy"
        ),
    )
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="Hiển thị danh sách tất cả giọng đọc có sẵn và thoát",
    )

    args = parser.parse_args()

    # === Hiển thị danh sách giọng đọc ===
    if args.list_voices:
        from tts import list_voices
        list_voices()
        return

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

    script_parts = [script_text]
    if args.auto_split:
        try:
            from ai_splitter import split_story_script
            result = split_story_script(script_text)
            if result is None:
                sys.exit(1)
            elif len(result) > 1:
                script_parts = result
                print(f"  [AI Splitter] ✅ Đã chia thành {len(script_parts)} phần độc lập!")
        except ImportError:
            print("❌ Không tìm thấy module ai_splitter.py")

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

    # === Chuẩn bị nhạc nền BGM (nếu có) ===
    os.makedirs(args.bgm_dir, exist_ok=True)
    bgm_files = [f for f in os.listdir(args.bgm_dir) if f.lower().endswith((".mp3", ".wav", ".ogg"))]
    bgm_path = None
    if bgm_files:
        import random
        bgm_path = os.path.join(args.bgm_dir, random.choice(bgm_files))

    # === Pipeline chính ===
    print("=" * 60)
    print("🎬 TIKTOK VIDEO AUTO-CREATOR")
    print("=" * 60)

    for i, part_text in enumerate(script_parts):
        part_num = i + 1
        is_multi_part = len(script_parts) > 1

        if is_multi_part:
            print(f"\n" + "="*50)
            print(f"🔄 ĐANG XỬ LÝ PHẦN {part_num}/{len(script_parts)}")
            print("="*50)
            
            # Ghi text tạm
            temp_script = f"temp/script_part{part_num}.txt"
            with open(temp_script, "w", encoding="utf-8") as f:
                f.write(part_text)
            current_script = temp_script
            
            audio_path = os.path.join("temp", f"audio_part{part_num}.mp3")
            srt_path = os.path.join("temp", f"subtitles_part{part_num}.srt")
            
            base, ext = os.path.splitext(args.output)
            current_output = f"{base}_part{part_num}{ext}"
        else:
            current_script = args.script
            audio_path = os.path.join("temp", "audio.mp3")
            srt_path = os.path.join("temp", "subtitles.srt")
            current_output = args.output

        # Bước 1: Text-to-Speech
        print("\n📌 BƯỚC 1: Tạo giọng đọc từ kịch bản...")
        print(f"   Script: {current_script}")
        print(f"   Tốc độ đọc: {args.rate}")
        print(f"   Giọng đọc: {args.voice}")
        run_tts(current_script, audio_path, srt_path, rate=args.rate, voice=args.voice)

        # Bước 2: Render Video
        print("\n📌 BƯỚC 2: Render video...")
        final_video = make_video(
            audio_path=audio_path,
            srt_path=srt_path,
            bg_dir=args.bg_dir,
            output_path=current_output,
            style=args.style,
            position=args.position,
            bgm_path=bgm_path,
        )

        # Bước 3: Upload (nếu có flag --upload)
        if args.upload:
            print("\n📌 BƯỚC 3: Upload lên TikTok...")
            tags = [t.strip() for t in args.tags.split(",") if t.strip()]
            upload_title = f"{args.title} (Phần {part_num})" if args.title and is_multi_part else args.title
            upload_video(
                video_path=final_video,
                title=upload_title,
                tags=tags,
            )
        else:
            print(f"\n✅ Xong {'Phần ' + str(part_num) if is_multi_part else 'Video'}! Tệp xuất tại: {final_video}")

    print("\n" + "=" * 60)
    print("🎉 HOÀN TẤT TOÀN BỘ CHƯƠNG TRÌNH!")
    print("=" * 60)


if __name__ == "__main__":
    main()
