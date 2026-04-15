"""
uploader.py - TikTok Auto Upload via Playwright (Cross-platform)
=================================================================
Module này dùng Playwright (Headless Chromium) để tự động upload video lên TikTok.

Luồng hoạt động:
1. Lần đầu: Mở trình duyệt, bạn quét QR đăng nhập -> Cookie được lưu lại.
2. Các lần sau: Dùng Cookie đã lưu để upload tự động không cần đăng nhập lại.
"""

import os
import json
import time

COOKIE_FILE = "tiktok_cookies.json"
TIKTOK_UPLOAD_URL = "https://www.tiktok.com/creator#/upload?scene=creator_center"


def _save_cookies(context, cookie_path: str = COOKIE_FILE):
    """Lưu cookies từ trình duyệt ra file JSON."""
    cookies = context.cookies()
    with open(cookie_path, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"  [Cookies] Saved {len(cookies)} cookies to {cookie_path}")


def _load_cookies(context, cookie_path: str = COOKIE_FILE):
    """Nạp cookies đã lưu vào trình duyệt."""
    if not os.path.exists(cookie_path):
        return False
    with open(cookie_path, "r", encoding="utf-8") as f:
        cookies = json.load(f)
    context.add_cookies(cookies)
    print(f"  [Cookies] Loaded {len(cookies)} cookies from {cookie_path}")
    return True


def login_tiktok():
    """
    Mở trình duyệt để bạn đăng nhập TikTok bằng QR Code.
    Cookie sẽ được lưu lại cho các lần upload sau.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ Playwright chưa được cài đặt. Chạy:")
        print("   pip install playwright && python -m playwright install chromium")
        return False

    print("\n🔐 Mở trình duyệt để đăng nhập TikTok...")
    print("   Vui lòng quét mã QR hoặc đăng nhập thủ công.")
    print("   Sau khi đăng nhập xong, nhấn Enter trong terminal này.\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.goto("https://www.tiktok.com/login", wait_until="networkidle")

        input("\n✅ Đã đăng nhập xong? Nhấn Enter để lưu cookie...")

        _save_cookies(context)
        browser.close()

    print("✅ Đăng nhập thành công! Cookie đã được lưu.")
    return True


def upload_video(
    video_path: str,
    title: str = "",
    tags: list = None,
):
    """
    Upload video lên TikTok tự động.

    Args:
        video_path: Đường dẫn file MP4.
        title: Tiêu đề/Caption cho video.
        tags: Danh sách hashtag (ví dụ: ["fyp", "review", "affiliate"]).
    """
    if tags is None:
        tags = ["fyp", "viral", "tiktokvietnam"]

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    if not os.path.exists(COOKIE_FILE):
        print("⚠️  Chưa đăng nhập TikTok. Đang mở trình duyệt đăng nhập...")
        if not login_tiktok():
            return False

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ Playwright chưa được cài đặt. Chạy:")
        print("   pip install playwright && python -m playwright install chromium")
        return False

    # Tạo caption với hashtags
    hashtags = " ".join([f"#{tag}" for tag in tags])
    caption = f"{title} {hashtags}".strip()

    print(f"\n📤 Uploading video to TikTok...")
    print(f"   File: {video_path}")
    print(f"   Caption: {caption}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headless=False để debug
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        # Nạp cookies đã lưu
        _load_cookies(context)

        page = context.new_page()

        try:
            # Vào trang upload
            page.goto(TIKTOK_UPLOAD_URL, wait_until="networkidle", timeout=30000)
            time.sleep(3)

            # Kiểm tra xem đã đăng nhập chưa
            if "login" in page.url.lower():
                print("⚠️  Cookie hết hạn. Cần đăng nhập lại.")
                browser.close()
                login_tiktok()
                return upload_video(video_path, title, tags)

            # Tìm input file để upload
            # TikTok dùng input[type="file"] ẩn
            file_input = page.locator('input[type="file"]').first
            file_input.set_input_files(os.path.abspath(video_path))
            print("  [Upload] File selected, waiting for upload...")

            # Đợi video upload xong (thanh tiến trình biến mất)
            time.sleep(10)

            # Nhập caption
            # TikTok Creator Center dùng một editor phức tạp
            caption_editor = page.locator(
                'div[contenteditable="true"]'
            ).first
            if caption_editor.is_visible():
                caption_editor.click()
                # Xóa nội dung cũ
                page.keyboard.press("Control+A" if os.name == "nt" else "Meta+A")
                page.keyboard.press("Backspace")
                time.sleep(0.5)
                # Gõ caption mới
                caption_editor.type(caption, delay=50)
                print(f"  [Caption] Set: {caption}")
            
            time.sleep(2)

            # Tìm và bấm nút Post / Đăng
            post_button = page.locator('button:has-text("Post"), button:has-text("Đăng")').first
            if post_button.is_visible():
                post_button.click()
                print("  [Post] Clicked Post button!")
                time.sleep(10)  # Đợi xử lý
            else:
                print("  [Post] Could not find Post button. Please post manually.")
                input("  Nhấn Enter sau khi đã đăng xong...")

            # Lưu lại cookies mới
            _save_cookies(context)

        except Exception as e:
            print(f"❌ Upload error: {e}")
            print("  Bạn có thể upload thủ công tại: https://www.tiktok.com/creator")
            return False
        finally:
            browser.close()

    print("✅ Upload hoàn tất!")
    return True


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--login":
        login_tiktok()
    else:
        upload_video(
            "output/final_video.mp4",
            title="Review sản phẩm số hot nhất",
            tags=["fyp", "viral", "review", "affiliate", "tiktokvietnam"],
        )
