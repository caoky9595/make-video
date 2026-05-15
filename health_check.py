import time
import random
from nick_manager import _load_nicks, _save_nicks
from DrissionPage import ChromiumPage, ChromiumOptions

def run_health_check():
    """
    Tự động kiểm tra trạng thái nick và mô phỏng hành động warm-up (lướt TikTok).
    M3-01 Health check & Warm-up sequence
    """
    nicks = _load_nicks()
    if not nicks:
        print("Không có nick nào để kiểm tra.")
        return

    print("🩺 Bắt đầu quy trình Health Check & Warm-up...")
    
    for name, data in nicks.items():
        if data.get("status") in ["banned", "paused"]:
            continue
            
        print(f"\n[{name}] Bắt đầu warm-up...")
        
        co = ChromiumOptions()
        try:
            import cloakbrowser
            path = cloakbrowser.ensure_binary()
            co.set_browser_path(path)
            print(f"🚀 Sử dụng CloakBrowser: {path}")
        except ImportError:
            if __import__("sys").platform == "darwin":
                path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
                co.set_browser_path(path)
                print(f"🚀 Sử dụng Chrome mặc định: {path}")
            
        port = random.randint(9250, 9999)
        co.set_local_port(port)
        print(f"🔌 Port: {port}")
        
        # Đảm bảo dùng đường dẫn tuyệt đối cho profile (giúp CloakBrowser chạy ổn định hơn)
        import os
        abs_profile = os.path.abspath(f"profiles/{name}")
        co.set_user_data_path(abs_profile)
        
        co.headless(False)
        co.set_argument("--no-sandbox")
        co.set_argument("--disable-blink-features=AutomationControlled")
        
        proxy = data.get("proxy")
        if proxy:
            co.set_proxy(proxy)
            
        try:
            page = ChromiumPage(co)
            page.get("https://www.tiktok.com/foryou")
            
            # Mô phỏng xem video ngẫu nhiên (30s - 2 phút)
            watch_time = random.randint(30, 120)
            print(f"  📺 Đang lướt For You ({watch_time}s)...")
            
            # Cuộn trang vài lần ngẫu nhiên
            start_time = time.time()
            while time.time() - start_time < watch_time:
                time.sleep(random.uniform(5, 15))
                page.actions.key_down("ArrowDown").key_up("ArrowDown")
                
            print(f"  ✅ Warm-up hoàn tất.")
            
            # Đánh dấu nick là active nếu nó đang là warmup
            if data.get("status") == "warmup":
                data["status"] = "active"
                _save_nicks(nicks)
                
        except Exception as e:
            print(f"  ❌ Lỗi khi warm-up: {e}")
        finally:
            try:
                page.close()
                page.disconnect()
            except:
                pass
                
        # Nghỉ giữa các nick
        time.sleep(random.uniform(10, 30))

if __name__ == "__main__":
    run_health_check()
