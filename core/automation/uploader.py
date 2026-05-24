"""
uploader.py - TikTok Auto Upload via DrissionPage (Anti-Detect)
===============================================================
Nâng cấp từ Playwright → DrissionPage để tránh bị TikTok phát hiện bot.

Ưu điểm so với phiên bản cũ (Playwright):
  - Kết nối vào Chrome đang chạy thật (không tạo browser giả)
  - Không để lộ dấu hiệu automation (navigator.webdriver = false)
  - Hỗ trợ nhiều profile Chrome riêng biệt (multi-nick)

Luồng hoạt động:
  1. Lần đầu: Mở Chrome, bạn đăng nhập thủ công → Cookie tự lưu trong profile.
  2. Các lần sau: Gắn vào Chrome profile đó → Upload tự động không cần login lại.
"""

import os
import sys
import json
import time
import random
import logging
from pathlib import Path
from typing import Optional
from core.utils.logger_config import logger

logger = logging.getLogger(__name__)

# ============================================================
# CẤU HÌNH
# ============================================================

PROFILES_DIR = Path("profiles")           # Thư mục chứa các Chrome profile
TIKTOK_UPLOAD_URL = "https://www.tiktok.com/creator#/upload?scene=creator_center"
TIKTOK_LOGIN_URL  = "https://www.tiktok.com/login"

# Thời gian chờ ngẫu nhiên (giây) — giả lập hành vi người thật
DELAY_AFTER_UPLOAD  = (8, 15)    # Sau khi chọn file
DELAY_AFTER_CAPTION = (1, 3)     # Sau khi điền caption
DELAY_AFTER_POST    = (5, 10)    # Sau khi bấm đăng


# ============================================================
# HELPERS
# ============================================================

def _random_delay(range_tuple: tuple):
    """Nghỉ ngẫu nhiên trong khoảng (min, max) giây."""
    t = random.uniform(*range_tuple)
    time.sleep(t)


def _get_profile_dir(nick_name: str) -> Path:
    """Trả về đường dẫn thư mục profile cho một nick."""
    profile = PROFILES_DIR / nick_name
    profile.mkdir(parents=True, exist_ok=True)
    return profile


def _type_like_human(page, text: str):
    """Gõ text từng ký tự với delay ngẫu nhiên để giả lập người thật."""
    for char in text:
        page.actions.key_down(char)
        time.sleep(random.uniform(0.03, 0.12))


# ============================================================
# ĐĂNG NHẬP
# ============================================================

def login_tiktok(nick_name: str = "default"):
    """
    Mở Chrome với profile riêng để bạn đăng nhập TikTok thủ công.
    Cookie sẽ được lưu tự động trong profile (không cần export JSON).

    Args:
        nick_name: Tên nick/tài khoản, dùng để tạo profile riêng biệt.
    """
    try:
        from DrissionPage import ChromiumPage, ChromiumOptions
    except ImportError:
        logger.info("❌ DrissionPage chưa được cài. Chạy: pip install DrissionPage")
        return False

    from core.automation.nick_manager import _load_nicks
    nicks = _load_nicks()
    nick_data = nicks.get(nick_name, {})
    proxy = nick_data.get("proxy", "")

    profile_path = _get_profile_dir(nick_name)

    co = ChromiumOptions()
    
    # Fix trên MacOS: Dùng CloakBrowser nếu đã cài, nếu không dùng Chrome mặc định
    try:
        from core.automation import cloakbrowser
        path = cloakbrowser.ensure_binary()
        co.set_browser_path(path)
        logger.info(f"🚀 Sử dụng CloakBrowser: {path}")
    except ImportError:
        if sys.platform == "darwin":
            path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            co.set_browser_path(path)
            logger.info(f"🚀 Sử dụng Chrome mặc định: {path}")
    
    # Dùng port ngẫu nhiên thay vì 9222 mặc định
    port = random.randint(9250, 9999)
    co.set_local_port(port)
    logger.info(f"🔌 Port: {port}")
    
    # Đảm bảo dùng đường dẫn tuyệt đối cho profile (giúp CloakBrowser chạy ổn định hơn)
    import os
    abs_profile = os.path.abspath(str(profile_path))
    co.set_user_data_path(abs_profile)     # Profile riêng cho nick này
    co.headless(False)                            # Hiện trình duyệt để bạn đăng nhập
    
    # Fingerprint & Proxy (M1-02, M1-03)
    co.set_argument("--no-sandbox")
    co.set_argument("--disable-blink-features=AutomationControlled")
    # Tắt thông báo rác
    co.set_argument("--disable-notifications")
    co.set_argument("--mute-audio")
    
    # Gắn Proxy nếu có
    if proxy:
        # Nếu proxy có dạng user:pass@ip:port
        co.set_proxy(proxy)
        logger.info(f"   🌐 Đang dùng Proxy: {proxy}")

    logger.info(f"\n🔐 Mở Chrome cho nick: [{nick_name}]")
    logger.info(f"   Profile: {profile_path}")
    logger.info("   Hãy đăng nhập TikTok trong cửa sổ vừa mở.")
    logger.info("   Sau khi đăng nhập xong → Nhấn Enter ở terminal này.\n")

    page = ChromiumPage(co)
    page.get(TIKTOK_LOGIN_URL)

    input("✅ Đã đăng nhập xong? Nhấn Enter để lưu và thoát...")

    page.disconnect()
    logger.info(f"✅ Cookie đã lưu trong profile: {profile_path} (Vui lòng tự đóng cửa sổ Chrome)")
    return True


# ============================================================
# UPLOAD VIDEO
# ============================================================

def upload_video(
    video_path: str,
    title: str = "",
    tags: Optional[list] = None,
    nick_name: str = "default",
    product_id: Optional[str] = None,
) -> bool:
    """
    Upload video lên TikTok tự động qua DrissionPage.

    Args:
        video_path:  Đường dẫn file MP4.
        title:       Caption/tiêu đề video.
        tags:        Danh sách hashtag (không có dấu #).
        nick_name:   Tên nick để dùng đúng Chrome profile.
        product_id:  (TODO) ID sản phẩm affiliate để gắn vào video.

    Returns:
        True nếu upload thành công, False nếu thất bại.
    """
    if tags is None:
        tags = ["fyp", "viral", "tiktokvietnam"]

    if not os.path.exists(video_path):
        logger.error(f"Video không tồn tại: {video_path}")
        return False

    try:
        from DrissionPage import ChromiumPage, ChromiumOptions
    except ImportError:
        logger.info("❌ DrissionPage chưa được cài. Chạy: pip install DrissionPage")
        return False

    profile_path = _get_profile_dir(nick_name)

    # Kiểm tra profile đã đăng nhập chưa
    if not any(profile_path.iterdir()):
        logger.info(f"⚠️  Nick [{nick_name}] chưa đăng nhập. Đang mở đăng nhập...")
        if not login_tiktok(nick_name):
            return False

    # Tạo caption đầy đủ
    hashtags_str = " ".join([f"#{tag.strip('#')}" for tag in tags])
    caption = f"{title} {hashtags_str}".strip()

    logger.info(f"\n📤 Uploading video...")
    logger.info(f"   Nick:    [{nick_name}]")
    logger.info(f"   File:    {video_path}")
    logger.info(f"   Caption: {caption}")

    # Cấu hình Chrome Option
    from core.automation.nick_manager import _load_nicks
    nicks = _load_nicks()
    nick_data = nicks.get(nick_name, {})
    proxy = nick_data.get("proxy", "")

    # Khởi tạo ChromiumOptions với profile riêng
    co = ChromiumOptions()
    
    # Fix trên MacOS: Dùng CloakBrowser nếu đã cài, nếu không dùng Chrome mặc định
    try:
        from core.automation import cloakbrowser
        path = cloakbrowser.ensure_binary()
        co.set_browser_path(path)
        logger.info(f"🚀 Sử dụng CloakBrowser: {path}")
    except ImportError:
        if sys.platform == "darwin":
            path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            co.set_browser_path(path)
            logger.info(f"🚀 Sử dụng Chrome mặc định: {path}")
    
    # Dùng port ngẫu nhiên thay vì 9222 mặc định
    port = random.randint(9250, 9999)
    co.set_local_port(port)
    logger.info(f"🔌 Port: {port}")
    
    # Đảm bảo dùng đường dẫn tuyệt đối cho profile (giúp CloakBrowser chạy ổn định hơn)
    import os
    abs_profile = os.path.abspath(str(profile_path))
    co.set_user_data_path(abs_profile)
    co.headless(False)      # Không chạy ẩn — TikTok dễ detect headless
    co.set_argument("--no-sandbox")
    co.set_argument("--disable-blink-features=AutomationControlled")
    co.set_argument("--disable-notifications")
    co.set_argument("--mute-audio")
    
    if proxy:
        co.set_proxy(proxy)
        logger.info(f"   🌐 Đang dùng Proxy: {proxy}")

    page = ChromiumPage(co)

    try:
        # Vào trang upload
        page.get(TIKTOK_UPLOAD_URL)
        _random_delay((2, 4))

        # Kiểm tra đã đăng nhập chưa
        if "login" in page.url.lower():
            logger.info("⚠️  Session hết hạn. Cần đăng nhập lại.")
            page.quit()
            login_tiktok(nick_name)
            return upload_video(video_path, title, tags, nick_name, product_id)

        # === BƯỚC 1: Chọn file video ===
        logger.info("  [1/4] Chọn file video...")

        # TikTok dùng iframe cho trang upload — cần switch vào iframe
        # Tìm iframe upload
        try:
            iframe = page.get_frame("tiktok.com/creator")
            upload_input = iframe.ele('xpath://input[@type="file"]', timeout=10)
        except Exception:
            # Thử tìm trực tiếp trên page nếu không có iframe
            upload_input = page.ele('xpath://input[@type="file"]', timeout=10)

        if not upload_input:
            logger.info("  ❌ Không tìm thấy ô upload file. TikTok có thể đã thay đổi UI.")
            return False

        upload_input.input(os.path.abspath(video_path))
        logger.info(f"  ✅ Đã chọn file: {video_path}")
        _random_delay(DELAY_AFTER_UPLOAD)

        # === BƯỚC 2: Điền caption ===
        logger.info("  [2/4] Điền caption...")
        try:
            # Tìm caption editor (contenteditable div)
            caption_box = page.ele('xpath://div[@contenteditable="true"]', timeout=15)
            if caption_box:
                caption_box.click()
                _random_delay((0.5, 1))

                # Xóa nội dung cũ (nếu có)
                page.actions.key_down("ctrl").key_down("a").key_up("a").key_up("ctrl")
                _random_delay((0.2, 0.5))
                page.actions.key_down("Backspace").key_up("Backspace")
                _random_delay((0.3, 0.7))

                # Gõ caption trực tiếp (hỗ trợ Tiếng Việt có dấu) thay vì gõ từng phím
                caption_box.input(caption)
                logger.info(f"  ✅ Caption: {caption[:50]}...")
            else:
                logger.info("  ⚠️  Không tìm thấy ô caption")

        except Exception as e:
            logger.info(f"  ⚠️  Lỗi caption: {e}")

        _random_delay(DELAY_AFTER_CAPTION)

        # === BƯỚC 3: Gắn sản phẩm ===
        if product_id:
            logger.info(f"  [3/4] Gắn sản phẩm ID: {product_id}...")
            try:
                # Click "Thêm liên kết" / "Add link"
                add_link_btn = page.ele('xpath://div[contains(text(), "Add link") or contains(text(), "Thêm liên kết") or @class[contains(., "add-link")]]', timeout=3)
                if add_link_btn:
                    add_link_btn.run_js('this.click();')
                    _random_delay((1, 2))
                    
                    # Chọn "Product" / "Sản phẩm"
                    product_btn = page.ele('xpath://div[contains(text(), "Product") or contains(text(), "Sản phẩm") or @class[contains(., "product")]]', timeout=3)
                    if product_btn:
                        product_btn.run_js('this.click();')
                        _random_delay((2, 4))
                        
                        # Điền ID sản phẩm
                        search_box = page.ele('xpath://input[@placeholder="Search" or @placeholder="Tìm kiếm" or @type="search"]', timeout=3)
                        if search_box:
                            search_box.input(product_id)
                            _random_delay((2, 3))
                            
                            # Nhấn nút Add đầu tiên
                            add_btn = page.ele('xpath://button[contains(text(), "Add") or contains(text(), "Thêm")]', timeout=5)
                            if add_btn:
                                add_btn.run_js('this.click();')
                                logger.info(f"  ✅ Đã gắn sản phẩm: {product_id}")
                                _random_delay((1, 2))
                            else:
                                logger.info(f"  ⚠️ Không tìm thấy sản phẩm {product_id}")
            except Exception as e:
                logger.info(f"  ⚠️ Lỗi khi gắn sản phẩm: {e}")
        else:
            logger.info("  [3/4] Bỏ qua gắn sản phẩm (không có product_id)")

        # === BƯỚC 4: Đăng bài ===
        logger.info("  [4/4] Đăng bài...")
        try:
            # Tìm nút đăng chính xác
            post_btn = page.ele(
                'xpath://button[contains(., "Post") or contains(., "Đăng") or contains(., "post")]',
                timeout=10
            )
            if post_btn:
                # Đảm bảo nút Post đã sáng lên (video tải xong lên cloud)
                # Dùng JS thuần để click thay vì .click() của DrissionPage để tránh lỗi phiên bản
                post_btn.run_js('this.click();')
                logger.info("  ✅ Đã bấm nút Đăng! Đang chờ TikTok xử lý...")
                
                # CHỜ POPUP CONFIRM (Nếu có)
                _random_delay((2, 4))
                confirm_btn = page.ele('xpath://button[contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "confirm") or contains(., "Xác nhận") or contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "post anyway") or contains(., "Vẫn đăng") or contains(., "Continue") or contains(., "Tiếp tục")]', timeout=3)
                if confirm_btn:
                    confirm_btn.run_js('this.click();')
                    logger.info("  ✅ Đã bấm nút Xác Nhận trên Popup!")
                    _random_delay((2, 4))

                # Đợi xuất hiện popup báo thành công ("Manage posts" hoặc "Tải video khác lên")
                success_modal = page.ele(
                    'xpath://*[contains(text(), "Manage posts") or contains(text(), "Upload another") or contains(text(), "Quản lý bài đăng") or contains(text(), "Tải video khác")]',
                    timeout=30
                )
                
                if success_modal:
                    logger.info("  ✅ Đã thấy thông báo đăng thành công từ TikTok!")
                    _random_delay((2, 4))
                else:
                    logger.info("  ⚠️  Không thấy thông báo thành công, đang đợi thêm 15s để chắc chắn...")
                    time.sleep(15)
            else:
                logger.info("  ⚠️  Không tìm thấy nút Đăng. Hãy đăng thủ công.")
                input("  Nhấn Enter sau khi đã đăng xong...")

        except Exception as e:
            logger.info(f"  ⚠️  Lỗi khi bấm đăng: {e}")
            input("  Nhấn Enter sau khi đã đăng thủ công...")

        logger.info(f"\n✅ Upload hoàn tất cho nick [{nick_name}]!")
        return True

    except Exception as e:
        logger.exception(f"Lỗi upload: {e}")
        logger.info(f"❌ Lỗi không xác định: {e}")
        return False

    finally:
        # Không dùng page.quit() vì trên Mac DrissionPage hay dùng killall làm chết Chrome gốc của user
        try:
            page.close()  # Đóng tab hiện tại
            page.disconnect() # Ngắt kết nối để DrissionPage giải phóng tài nguyên
        except Exception:
            pass

# ============================================================
# LOGGING (M3-08)
# ============================================================

def log_upload_result(nick_name: str, video_path: str, status: str, message: str = ""):
    """Ghi log kết quả đăng vào file upload_history.log"""
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "upload_history.log"
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] NICK: {nick_name} | STATUS: {status} | VIDEO: {video_path} | MSG: {message}\n")

# ============================================================
# UPLOAD QUEUE — Đăng hàng loạt cho nhiều nick (Có Scheduler + Retry)
# ============================================================

def upload_queue(jobs: list) -> dict:
    """
    Chạy hàng đợi upload cho nhiều nick.
    Hỗ trợ Retry (tối đa 3 lần) và ngẫu nhiên thời gian.

    Args:
        jobs: Danh sách các công việc upload, mỗi job là dict:
              {
                  "nick_name": "nick_01",
                  "video_path": "processed/video_001.mp4",
                  "title": "Review sản phẩm hot",
                  "tags": ["fyp", "viral"],
                  "product_id": "TT_PRODUCT_001"  # optional
              }

    Returns:
        Dict tổng kết: {"success": [...], "failed": [...]}
    """
    results = {"success": [], "failed": []}

    logger.info(f"\n📋 Upload Queue: {len(jobs)} video cần đăng")
    logger.info("=" * 50)

    for i, job in enumerate(jobs, 1):
        nick = job.get("nick_name", "default")
        video = job.get("video_path", "")
        title = job.get("title", "")
        tags = job.get("tags", ["fyp", "viral"])
        product_id = job.get("product_id")

        logger.info(f"\n[{i}/{len(jobs)}] Nick: {nick} | Video: {os.path.basename(video)}")

        # M3-07 Retry mechanism (Tối đa 3 lần)
        max_retries = 3
        success = False
        
        for attempt in range(max_retries):
            if attempt > 0:
                logger.info(f"  ⚠️ Đang thử lại lần {attempt + 1}/{max_retries} cho nick [{nick}]...")
                _random_delay((10, 20))
                
            success = upload_video(
                video_path=video,
                title=title,
                tags=tags,
                nick_name=nick,
                product_id=product_id,
            )
            
            if success:
                break

        if success:
            results["success"].append(job)
            log_upload_result(nick, video, "SUCCESS")
        else:
            results["failed"].append(job)
            log_upload_result(nick, video, "FAILED", f"Failed after {max_retries} retries")

        # M3-06: Nghỉ ngẫu nhiên giữa các lần upload (tránh pattern)
        if i < len(jobs):
            wait_time = random.uniform(30, 90)
            logger.info(f"  ⏳ Nghỉ {wait_time:.0f}s trước video tiếp theo...")
            time.sleep(wait_time)

    # Tổng kết
    logger.info("\n" + "=" * 50)
    logger.info(f"✅ Thành công: {len(results['success'])}/{len(jobs)}")
    logger.info(f"❌ Thất bại:   {len(results['failed'])}/{len(jobs)}")

    return results


# ============================================================
# CHẠY TRỰC TIẾP
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--login":
        nick = sys.argv[2] if len(sys.argv) > 2 else "default"
        login_tiktok(nick_name=nick)

    elif len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Test upload 1 video
        upload_video(
            video_path="output/final_video.mp4",
            title="Review sản phẩm hot nhất hôm nay",
            tags=["fyp", "viral", "review", "affiliate", "tiktokvietnam"],
            nick_name="test_nick",
        )
    else:
        logger.info("Cách dùng:")
        logger.info("  python uploader.py --login [nick_name]    # Đăng nhập cho 1 nick")
        logger.info("  python uploader.py --test                 # Test upload 1 video")
