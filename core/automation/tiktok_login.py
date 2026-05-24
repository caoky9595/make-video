import os
import time
from dotenv import load_dotenv
from core.utils.logger_config import logger

def update_env_session_id(session_id: str):
    """
    Cập nhật TIKTOK_SESSION_ID vào file .env và cập nhật os.environ.
    """
    # Ghi session_id vào file text để dùng trực tiếp (không bị lỗi cache biến môi trường của hệ điều hành)
    session_file = os.path.join(os.path.dirname(__file__), "tiktok_session.txt")
    with open(session_file, "w", encoding="utf-8") as f:
        f.write(session_id.strip())
        
    env_path = ".env"
    if not os.path.exists(env_path):
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"TIKTOK_SESSION_ID={session_id}\n")
        os.environ["TIKTOK_SESSION_ID"] = session_id
        return
        
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    replaced = False
    for i, line in enumerate(lines):
        # Kiểm tra nếu dòng chứa TIKTOK_SESSION_ID (kể cả dòng comment)
        if line.strip().startswith("TIKTOK_SESSION_ID=") or line.strip().startswith("# TIKTOK_SESSION_ID="):
            lines[i] = f"TIKTOK_SESSION_ID={session_id}\n"
            replaced = True
            break
            
    if not replaced:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(f"TIKTOK_SESSION_ID={session_id}\n")
        
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
        
    os.environ["TIKTOK_SESSION_ID"] = session_id
    # Reload lại dotenv
    load_dotenv(override=True)

def run_tiktok_login_automation():
    """
    Mở trình duyệt Chromium thông qua DrissionPage để người dùng đăng nhập TikTok.
    Tự động dò tìm cookie sessionid, lưu vào .env và đóng trình duyệt.
    """
    import traceback
    from DrissionPage import ChromiumPage, ChromiumOptions
    
    logger.info("[TikTok Login] Đang khởi chạy trình duyệt DrissionPage...")
    
    try:
        co = ChromiumOptions()
        # Dùng một profile cục bộ riêng biệt để tránh đụng độ với Chrome của máy và bỏ qua màn hình chọn profile
        profile_path = os.path.abspath(".tiktok_profile")
        co.set_user_data_path(profile_path)
        
        # Thêm cờ chống phát hiện bot để bypass block mã QR của TikTok
        co.set_argument("--disable-blink-features=AutomationControlled")
        
        page = ChromiumPage(addr_or_opts=co)
    except Exception as e:
        error_msg = f"Lỗi khởi động trình duyệt: {e}\n{traceback.format_exc()}"
        logger.info(f"[TikTok Login] {error_msg}")
        return False, "Không thể mở trình duyệt. Vui lòng tắt các cửa sổ Chrome đang mở hoặc thử lại."

    try:
        # Mở thẳng trang login như yêu cầu
        page.get("https://www.tiktok.com/login")
        logger.info("[TikTok Login] Đã mở TikTok Login. Hãy đăng nhập (Quét QR, Google, v.v.).")
        
        # Chờ người dùng đăng nhập và lấy sessionid cookie
        timeout = 300  # 5 phút
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                cookies = page.cookies()
                session_id = None
                for cookie in cookies:
                    if cookie.get("name") == "sessionid":
                        session_id = cookie.get("value")
                        break
                if not session_id and hasattr(cookies, "as_dict"):
                    session_id = cookies.as_dict().get("sessionid")
                
                if session_id:
                    logger.info(f"[TikTok Login] Đăng nhập thành công! Lấy được sessionid: {session_id[:15]}...")
                    update_env_session_id(session_id)
                    page.quit()
                    return True, session_id
            except Exception as e:
                logger.info(f"[TikTok Login] Lỗi trong quá trình quét cookies: {e}")
                
            time.sleep(1)
            
        page.quit()
        return False, "Hết thời gian chờ đăng nhập (5 phút)."
    except Exception as e:
        try:
            page.quit()
        except Exception:
            pass
        return False, f"Lỗi trong quá trình chạy trình duyệt: {e}"
