"""
music_fetcher.py - Tải nhạc nền miễn phí bản quyền về thư viện local
=====================================================================
Tải nhạc qua API Openverse (openverse.org — dự án của WordPress Foundation, tổng hợp nội dung
Creative Commons từ Freesound/Jamendo/Wikimedia). API mở, không cần đăng ký key.

CHỈ lấy giấy phép CC0 (public domain):
  - Dùng thương mại thoải mái (kênh có affiliate vẫn hợp lệ)
  - KHÔNG phải ghi nguồn — quan trọng vì không thể chèn dòng credit vào video TikTok 15 giây
Các giấy phép khác của Openverse KHÔNG dùng được cho kênh này:
  - `by-nc-*` : NC = NonCommercial, cấm dùng cho kênh kiếm tiền (Jamendo trả về gần như toàn bộ
    là by-nc-nd, nhìn hấp dẫn vì bài dài 2-3 phút nhưng dùng là vi phạm)
  - `by-*`    : phải ghi nguồn tác giả, bất tiện với video ngắn

VÌ SAO KHÔNG PHẢI PIXABAY: Pixabay API chỉ có endpoint ảnh và video, KHÔNG có nhạc; còn trang web
thì chặn truy cập tự động (HTTP 403) và điều khoản ghi rõ "Systematic mass downloads are not
allowed". Muốn lấy nhạc Pixabay thì phải tự vào trang tải tay.

Tên file đặt theo đúng mood-query trong `music_finder.py` để `pick_local_music_for_script()` khớp
được — xem MOOD_KEYWORDS ở file đó.
"""

import json
import os
import re
import urllib.parse
import urllib.request

from core.utils.logger_config import logger

OPENVERSE_API = "https://api.openverse.org/v1/audio/"

# Nhạc ngắn quá (tiếng động lẻ, one-shot) nghe như lỗi khi lặp lại — chặn từ đầu.
MIN_DURATION_SEC = 15

# Mỗi mood thử lần lượt nhiều từ khoá: kho CC0 khá mỏng, từ khoá hẹp thường ra 0 kết quả.
# Key = đúng mood-query trong music_finder.MOOD_KEYWORDS (dùng luôn làm tên file để khớp).
MOOD_QUERIES = {
    "dark_mysterious_cinematic": ["dark ambient drone", "mysterious cinematic", "dark atmosphere"],
    "tense_anxious_suspenseful": ["tense suspense drone", "suspense", "tension build"],
    "eerie_unsettling_horror_ambient": ["horror ambient", "eerie drone", "creepy atmosphere"],
    "epic_dramatic_orchestral": ["epic cinematic", "dramatic orchestral", "epic drums"],
    "cosmic_space_ambient": ["space ambient", "cosmic pad", "deep space"],
    "melancholic_emotional_piano": ["sad emotional piano", "melancholy piano", "slow piano"],
}


def _search_cc0(query: str, page_size: int = 20) -> list:
    """Tìm nhạc CC0 trên Openverse. Trả về list kết quả thô (rỗng nếu lỗi mạng)."""
    url = OPENVERSE_API + "?" + urllib.parse.urlencode({
        "q": query,
        "license": "cc0",
        "page_size": page_size,
    })
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; VideoMakerBot/1.0)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")).get("results", [])
    except Exception as e:
        logger.warning(f"  [Music Fetch] Lỗi tìm '{query}': {e}")
        return []


def _safe_name(mood: str, title: str, index: int) -> str:
    """Tên file = mood-query + phần tên gốc đã làm sạch, giữ đuôi .mp3.

    Tiền tố mood là phần BẮT BUỘC — `music_finder` khớp mood bằng cách so từ trong TÊN FILE.
    """
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", (title or "track")).strip("_").lower()[:28]
    return f"{mood}_{index}_{slug or 'track'}.mp3"


def _is_usable_background(path: str) -> bool:
    """Kiểm tra file có dùng được làm NHẠC NỀN không, bằng cách đo năng lượng ở 5 đoạn đều nhau.

    Cần thiết vì kho CC0 lớn nhất là Freesound — vốn là kho TIẾNG ĐỘNG, không phải kho nhạc — nên
    kết quả tìm lẫn nhiều mẫu thô: gõ một tiếng rồi im, tiếng test tổng hợp, one-shot... Tên file
    nghe vẫn rất hợp lệ nên không lọc được bằng tên (vd 1 file tên "ambient" nhưng đo ra biên độ
    45dB và 2/5 đoạn im lặng — nghe sẽ như video bị lỗi tiếng).

    Nhạc nền tốt thì năng lượng đều: không đoạn nào gần như im, biên độ giữa các đoạn không quá lớn.
    """
    import subprocess

    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=20)
        duration = float(out.stdout.strip())
    except Exception:
        return False
    if duration < MIN_DURATION_SEC:
        return False

    seg = max(1.0, duration / 5)
    vols = []
    for i in range(5):
        try:
            r = subprocess.run(
                ["ffmpeg", "-hide_banner", "-ss", f"{i * seg:.2f}", "-t", f"{seg:.2f}",
                 "-i", path, "-af", "volumedetect", "-f", "null", "-"],
                capture_output=True, text=True, timeout=30)
            m = re.search(r"mean_volume:\s*(-?[\d.]+)", r.stderr)
            vols.append(float(m.group(1)) if m else -99.0)
        except Exception:
            return False

    near_silent = sum(1 for v in vols if v < -45)
    spread = max(vols) - min(vols)
    return near_silent < 2 and spread <= 25


def _download(url: str, dest: str) -> bool:
    """Tải 1 file về đường dẫn dest. Trả True nếu file tải về đủ lớn để coi là hợp lệ."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; VideoMakerBot/1.0)"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        if len(data) < 10_000:  # < 10KB gần như chắc chắn là trang lỗi, không phải nhạc
            return False
        with open(dest, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        logger.warning(f"  [Music Fetch] Tải hỏng {url[:60]}: {e}")
        return False


def fetch_music_library(music_dir: str = "audio_bg", per_mood: int = 1, moods=None) -> dict:
    """Tải về mỗi mood `per_mood` bài CC0, đặt tên khớp bộ khớp-mood của app.

    Trả về dict {mood: [tên file đã tải]}. Bỏ qua mood đã đủ file (không tải trùng).
    """
    os.makedirs(music_dir, exist_ok=True)
    existing = [f for f in os.listdir(music_dir) if f.lower().endswith(".mp3")]
    result = {}

    for mood, queries in (moods or MOOD_QUERIES).items():
        have = [f for f in existing if f.startswith(mood)]
        if len(have) >= per_mood:
            logger.info(f"  [Music Fetch] '{mood}' đã có {len(have)} bài, bỏ qua.")
            result[mood] = have
            continue

        got = []
        seen_urls = set()
        for query in queries:
            if len(got) >= per_mood - len(have):
                break
            for item in _search_cc0(query):
                if len(got) >= per_mood - len(have):
                    break
                url = item.get("url") or ""
                dur_ms = item.get("duration") or 0
                if not url.lower().endswith(".mp3") or url in seen_urls:
                    continue
                if dur_ms < MIN_DURATION_SEC * 1000:
                    continue
                seen_urls.add(url)

                name = _safe_name(mood, item.get("title", ""), len(have) + len(got) + 1)
                dest = os.path.join(music_dir, name)

                # Chống tải trùng bài đã có: chỉ nhớ URL trong 1 lượt chạy là chưa đủ — lần chạy
                # sau (vd tải bù sau khi xoá 1 file rác) sẽ gặp lại đúng bài cũ và tải lại y hệt,
                # chỉ khác số thứ tự trong tên. So bằng phần slug tên bài, bỏ tiền tố mood + số.
                slug = re.sub(r"^" + re.escape(mood) + r"_\d+_", "", name)
                if any(re.sub(r"^" + re.escape(mood) + r"_\d+_", "", e) == slug
                       for e in os.listdir(music_dir) if e.startswith(mood)):
                    continue

                if not _download(url, dest):
                    continue
                # Tải xong mới đo được năng lượng -> file rác thì xoá luôn, thử bài kế tiếp.
                if not _is_usable_background(dest):
                    logger.info(f"  [Music Fetch] ✗ bỏ '{name}' (mẫu tiếng động/one-shot, không phải nhạc nền)")
                    try:
                        os.remove(dest)
                    except OSError:
                        pass
                    continue
                got.append(name)
                logger.info(f"  [Music Fetch] ✅ {name} ({round(dur_ms/1000)}s)")

        if not got:
            logger.warning(f"  [Music Fetch] ⚠️ Không tìm được bài CC0 nào cho '{mood}'.")
        result[mood] = have + got

    return result


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    out = fetch_music_library(per_mood=n)
    print()
    for mood, files in out.items():
        print(f"{mood}: {len(files)} bài")
        for f in files:
            print(f"   - {f}")
