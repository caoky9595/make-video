"""
nick_manager.py - Quản lý nhiều tài khoản TikTok
=================================================
Quản lý danh sách nick, trạng thái, thống kê và phân bổ video.

Dữ liệu lưu trong file JSON đơn giản (không cần database).
Mỗi nick có Chrome profile riêng biệt trong thư mục profiles/.
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ============================================================
# CẤU HÌNH
# ============================================================

NICKS_FILE   = Path("data/nicks.json")
PROFILES_DIR = Path("profiles")

# Giới hạn an toàn
MAX_VIDEOS_PER_DAY_NEW   = 2    # Nick mới (< 7 ngày)
MAX_VIDEOS_PER_DAY_WARM  = 3    # Nick warm (7-14 ngày)
MAX_VIDEOS_PER_DAY_READY = 5    # Nick sẵn sàng (> 14 ngày)


# ============================================================
# NICK MODEL
# ============================================================

def _default_nick(nick_name: str) -> dict:
    """Tạo dữ liệu mặc định cho 1 nick mới."""
    return {
        "nick_name": nick_name,
        "username": "",
        "status": "new",              # new | warmup | active | paused | banned
        "proxy": "",                   # http://user:pass@ip:port
        "created_at": datetime.now().isoformat(),
        "last_upload": None,
        "last_warmup": None,
        "total_videos": 0,
        "videos_today": 0,
        "videos_today_date": None,
        "total_views": 0,
        "total_commission": 0,
        "notes": "",
    }


# ============================================================
# CRUD — Quản lý nick
# ============================================================

def _load_nicks() -> dict:
    """Load danh sách nick từ file."""
    NICKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if NICKS_FILE.exists():
        with open(NICKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_nicks(nicks: dict):
    """Lưu danh sách nick ra file."""
    NICKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(NICKS_FILE, "w", encoding="utf-8") as f:
        json.dump(nicks, f, ensure_ascii=False, indent=2)


def add_nick(nick_name: str, username: str = "", proxy: str = "") -> dict:
    """
    Thêm 1 nick mới vào hệ thống.

    Args:
        nick_name: Tên định danh (dùng nội bộ)
        username:  TikTok username
        proxy:     Proxy riêng cho nick này
    """
    nicks = _load_nicks()

    if nick_name in nicks:
        print(f"⚠️  Nick [{nick_name}] đã tồn tại.")
        return nicks[nick_name]

    nick_data = _default_nick(nick_name)
    nick_data["username"] = username
    nick_data["proxy"] = proxy

    # Tạo thư mục profile
    profile_dir = PROFILES_DIR / nick_name
    profile_dir.mkdir(parents=True, exist_ok=True)

    nicks[nick_name] = nick_data
    _save_nicks(nicks)

    print(f"✅ Đã thêm nick [{nick_name}] | Profile: {profile_dir}")
    return nick_data


def remove_nick(nick_name: str):
    """Xóa 1 nick khỏi hệ thống (không xóa profile Chrome)."""
    nicks = _load_nicks()
    if nick_name in nicks:
        del nicks[nick_name]
        _save_nicks(nicks)
        print(f"✅ Đã xóa nick [{nick_name}]")
    else:
        print(f"⚠️  Nick [{nick_name}] không tồn tại")


def list_nicks(status_filter: Optional[str] = None) -> list:
    """
    Hiển thị danh sách tất cả nick.

    Args:
        status_filter: Lọc theo trạng thái (new/warmup/active/paused/banned)
    """
    nicks = _load_nicks()

    if status_filter:
        filtered = {k: v for k, v in nicks.items() if v["status"] == status_filter}
    else:
        filtered = nicks

    if not filtered:
        print("📋 Chưa có nick nào.")
        return []

    print(f"\n📋 Danh sách nick ({len(filtered)}):")
    print("-" * 70)
    print(f"{'Tên':12} {'Username':15} {'Trạng thái':10} {'Video':7} {'Hôm nay':8} {'Proxy':15}")
    print("-" * 70)

    for name, data in filtered.items():
        status_icon = {
            "new": "🆕", "warmup": "🔥", "active": "✅",
            "paused": "⏸️", "banned": "❌"
        }.get(data["status"], "❓")

        proxy_short = data["proxy"][-15:] if data["proxy"] else "—"

        print(
            f"{status_icon} {name:10} {data['username']:15} "
            f"{data['status']:10} {data['total_videos']:>5}   "
            f"{data['videos_today']:>5}   {proxy_short}"
        )

    print("-" * 70)
    return list(filtered.values())


def update_nick(nick_name: str, **kwargs):
    """Cập nhật thông tin cho 1 nick."""
    nicks = _load_nicks()
    if nick_name not in nicks:
        print(f"⚠️  Nick [{nick_name}] không tồn tại")
        return

    for key, value in kwargs.items():
        if key in nicks[nick_name]:
            nicks[nick_name][key] = value

    _save_nicks(nicks)


# ============================================================
# LOGIC — Phân bổ video cho nick
# ============================================================

def get_available_nicks() -> list:
    """
    Lấy danh sách nick có thể đăng video hôm nay.
    Loại bỏ nick đã đạt giới hạn hoặc đang bị ban/tạm dừng.
    """
    nicks = _load_nicks()
    today = datetime.now().strftime("%Y-%m-%d")
    available = []

    for name, data in nicks.items():
        # Bỏ qua nick bị ban hoặc tạm dừng
        if data["status"] in ("banned", "paused"):
            continue

        # Reset counter nếu sang ngày mới
        if data.get("videos_today_date") != today:
            data["videos_today"] = 0
            data["videos_today_date"] = today

        # Tính giới hạn video/ngày theo tuổi nick
        created = datetime.fromisoformat(data["created_at"])
        age_days = (datetime.now() - created).days

        if age_days < 7:
            max_videos = MAX_VIDEOS_PER_DAY_NEW
        elif age_days < 14:
            max_videos = MAX_VIDEOS_PER_DAY_WARM
        else:
            max_videos = MAX_VIDEOS_PER_DAY_READY

        # Kiểm tra còn quota không
        if data["videos_today"] < max_videos:
            data["_max_today"] = max_videos
            data["_remaining"] = max_videos - data["videos_today"]
            available.append(data)

    _save_nicks(nicks)
    return available


def record_upload(nick_name: str, success: bool = True):
    """Ghi nhận 1 lần upload cho nick."""
    nicks = _load_nicks()
    today = datetime.now().strftime("%Y-%m-%d")

    if nick_name not in nicks:
        return

    data = nicks[nick_name]

    if data.get("videos_today_date") != today:
        data["videos_today"] = 0
        data["videos_today_date"] = today

    if success:
        data["total_videos"] += 1
        data["videos_today"] += 1
        data["last_upload"] = datetime.now().isoformat()

        # Auto-upgrade status
        created = datetime.fromisoformat(data["created_at"])
        age_days = (datetime.now() - created).days
        if age_days >= 14 and data["status"] != "active":
            data["status"] = "active"
        elif age_days >= 3 and data["status"] == "new":
            data["status"] = "warmup"

    _save_nicks(nicks)


def get_upload_plan() -> list:
    """
    Tạo kế hoạch đăng video cho hôm nay.
    Phân bổ video cho các nick theo quota còn lại.

    Returns:
        List of dicts: [{"nick_name": ..., "slots": ...}, ...]
    """
    available = get_available_nicks()

    if not available:
        print("📋 Không có nick nào có thể đăng hôm nay.")
        return []

    plan = []
    total_slots = 0

    print(f"\n📅 Kế hoạch đăng video hôm nay:")
    print("-" * 40)

    for nick in available:
        remaining = nick["_remaining"]
        plan.append({
            "nick_name": nick["nick_name"],
            "slots": remaining,
            "status": nick["status"],
        })
        total_slots += remaining
        print(f"  {nick['nick_name']:12} → {remaining} video (status: {nick['status']})")

    print("-" * 40)
    print(f"  Tổng: {total_slots} video cần chuẩn bị")
    return plan


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Cách dùng:")
        print("  python nick_manager.py list              # Xem tất cả nick")
        print("  python nick_manager.py add <name> [user] # Thêm nick")
        print("  python nick_manager.py remove <name>     # Xóa nick")
        print("  python nick_manager.py plan              # Kế hoạch hôm nay")
        print("  python nick_manager.py available          # Nick có thể đăng")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "list":
        list_nicks()
    elif cmd == "add" and len(sys.argv) >= 3:
        username = sys.argv[3] if len(sys.argv) > 3 else ""
        add_nick(sys.argv[2], username=username)
    elif cmd == "remove" and len(sys.argv) >= 3:
        remove_nick(sys.argv[2])
    elif cmd == "plan":
        get_upload_plan()
    elif cmd == "available":
        nicks = get_available_nicks()
        for n in nicks:
            print(f"  {n['nick_name']}: {n['_remaining']} slots left")
    else:
        print("❌ Lệnh không hợp lệ")
