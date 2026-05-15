import time
import json
import random
import os
from datetime import datetime
from pathlib import Path
from uploader import upload_video, log_upload_result
from nick_manager import _load_nicks, record_upload

QUEUE_FILE = Path("data/queue.json")

def load_queue():
    if not QUEUE_FILE.exists():
        return []
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_queue(queue):
    os.makedirs(QUEUE_FILE.parent, exist_ok=True)
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=4, ensure_ascii=False)

def is_golden_hour():
    """Kiểm tra xem hiện tại có phải là giờ vàng không (11h-13h và 18h-21h)"""
    hour = datetime.now().hour
    return (11 <= hour <= 13) or (18 <= hour <= 21)

def run_scheduler():
    print("🚀 Khởi động Scheduler Background...")
    print("🕒 Chờ đến giờ vàng (11h-13h hoặc 18h-21h) để tự động đăng...")
    
    while True:
        try:
            queue = load_queue()
            if not queue:
                time.sleep(60)
                continue
                
            if is_golden_hour():
                job = queue.pop(0)
                nick = job.get("nick_name")
                video = job.get("video_path")
                title = job.get("title")
                tags = job.get("tags")
                product_id = job.get("product_id")
                
                print(f"\n[SCHEDULER] ⏰ Đang đăng video cho nick: {nick}")
                
                max_retries = 3
                success = False
                for attempt in range(max_retries):
                    success = upload_video(
                        video_path=video,
                        title=title,
                        tags=tags,
                        nick_name=nick,
                        product_id=product_id
                    )
                    if success:
                        break
                    print(f"[SCHEDULER] ⚠️ Thử lại lần {attempt + 1} cho nick {nick}...")
                    time.sleep(random.uniform(10, 20))
                
                if success:
                    record_upload(nick, success=True)
                    log_upload_result(nick, video, "SUCCESS", "Via Scheduler")
                else:
                    record_upload(nick, success=False)
                    log_upload_result(nick, video, "FAILED", f"Via Scheduler after {max_retries} retries")
                    
                save_queue(queue)
                
                # Delay ngẫu nhiên giữa các video trong hàng đợi
                if queue:
                    wait_time = random.uniform(300, 900) # 5 - 15 phút
                    print(f"[SCHEDULER] ⏳ Nghỉ {wait_time:.0f}s trước khi đăng tiếp...")
                    time.sleep(wait_time)
            else:
                time.sleep(60) # Kiểm tra mỗi phút nếu chưa tới giờ
        except Exception as e:
            print(f"[SCHEDULER] ❌ Lỗi: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_scheduler()
