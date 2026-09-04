"""
music_finder.py - Auto Music Resolver for Studio
===============================================
Chọn nhạc nền phù hợp mood kịch bản từ thư viện nhạc local đã upload (`audio_bg/`).
"""

import os
import random
import re

from core.utils.logger_config import logger


# Mỗi mood gồm nhiều từ khoá (tiếng Việt có/không dấu) — cộng dồn điểm theo SỐ LẦN khớp thay vì
# dừng ở mood đầu tiên tìm thấy, để phản ánh đúng hơn tâm trạng chủ đạo của cả kịch bản. Từ khoá
# được chọn theo ngách Sự Thật Thú Vị & Tâm Lý Cuộc Sống (thay vì bộ từ khoá chung chung cũ hầu
# như không bao giờ khớp với nội dung ngách này).
MOOD_KEYWORDS = {
    "dark mysterious cinematic": [
        r"bí ẩn", r"mất tích", r"biến mất", r"không dấu vết", r"chưa có lời giải",
        r"khó hiểu", r"kỳ lạ", r"bí hiểm", r"không ai biết",
    ],
    "tense anxious suspenseful": [
        r"vụ án", r"điều tra", r"hiện trường", r"nghi phạm", r"cảnh sát", r"truy tìm",
        r"nguy hiểm", r"đe doạ", r"săn lùng",
    ],
    "eerie unsettling horror ambient": [
        r"kinh dị", r"rùng rợn", r"ma quái", r"ám ảnh", r"tâm linh", r"hồn ma",
        r"quỷ", r"nghĩa địa", r"ghê rợn",
    ],
    "epic dramatic orchestral": [
        r"cổ đại", r"kim tự tháp", r"nền văn minh", r"khảo cổ", r"di tích", r"đế chế",
        r"lịch sử", r"hàng nghìn năm",
    ],
    "cosmic space ambient": [
        r"vũ trụ", r"thiên hà", r"hành tinh", r"ngoài trái đất", r"ufo", r"người ngoài hành tinh",
        r"sao hoả", r"hố đen",
    ],
    "melancholic emotional piano": [
        r"bi kịch", r"tang thương", r"mất mát", r"không bao giờ trở về", r"tưởng niệm",
    ],
}

# Mood mặc định khi kịch bản không rơi rõ vào nhóm nào — trung tính, hợp giọng kể chuyện đời
# thường/tâm lý (không quá kịch tính như "cinematic" chung chung trước đây).
DEFAULT_MOOD_QUERY = "dark mysterious suspense ambient"


def _extract_music_query(script_text: str, custom_query: str = "") -> str:
    """Xác định 1 mood-query cho kịch bản bằng cách CỘNG DỒN điểm khớp từ khoá mỗi nhóm mood,
    chọn nhóm điểm cao nhất — thay vì dừng ở nhóm đầu tiên khớp (dễ chọn sai khi kịch bản có cả
    từ khoá của nhiều nhóm)."""
    if custom_query.strip():
        return custom_query.strip()

    script_lower = script_text.lower()
    scores = {}
    for mood_query, keywords in MOOD_KEYWORDS.items():
        score = sum(1 for kw in keywords if re.search(kw, script_lower))
        if score > 0:
            scores[mood_query] = score

    if not scores:
        return DEFAULT_MOOD_QUERY
    return max(scores, key=scores.get)


def pick_local_music_for_script(script_text: str, music_dir: str = "audio_bg"):
    """Chọn 1 file nhạc trong thư viện local hợp mood kịch bản nhất.

    Khớp theo TÊN FILE — chỉ hoạt động đúng nghĩa nếu file được đặt tên có từ khoá liên quan
    (vd `calm_piano_01.mp3`, `upbeat_motivation.mp3`). Không thể suy ra mood thật của 1 file từ
    tên chung chung (vd `sample.mp3`) — trường hợp đó (hoặc khi không file nào khớp được từ nào)
    sẽ chọn NGẪU NHIÊN thật trong toàn bộ thư viện, thay vì luôn rơi vào cùng 1 file cố định.
    """
    if not os.path.isdir(music_dir):
        return None

    supported = (".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac", ".webm")
    tracks = [f for f in os.listdir(music_dir) if f.lower().endswith(supported)]
    if not tracks:
        return None

    query = _extract_music_query(script_text)
    query_tokens = {t for t in re.split(r"[^a-zA-Z0-9]+", query.lower()) if len(t) > 2}

    scored = []
    for t in tracks:
        file_tokens = {x for x in re.split(r"[^a-zA-Z0-9]+", t.lower()) if len(x) > 2}
        score = len(query_tokens.intersection(file_tokens))
        scored.append((score, t))

    best_score = max(s for s, _ in scored)
    best_candidates = [t for s, t in scored if s == best_score]
    # Không tên file nào khớp có nghĩa (best_score == 0 nghĩa là mọi file đều điểm 0, tức không
    # phân biệt được) -> chọn ngẫu nhiên thật trong TOÀN BỘ thư viện thay vì trong "best_candidates"
    # (lúc đó best_candidates chính là toàn bộ danh sách nên kết quả tương đương, nhưng viết rõ
    # ràng cho dễ hiểu ý đồ).
    best_name = random.choice(best_candidates)
    best_path = os.path.join(music_dir, best_name)

    if best_score > 0:
        logger.info(f"  [Music AI] Mood '{query}' khớp tên file -> chọn: {best_name}")
    else:
        logger.info(f"  [Music AI] Không file nào khớp mood '{query}' theo tên -> chọn ngẫu nhiên: {best_name}")
    return best_path
