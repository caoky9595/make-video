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
    "calm soft ambient reflective": [
        r"ngủ", r"mất ngủ", r"thư giãn", r"bình yên", r"tĩnh lặng", r"chill", r"lofi", r"nhẹ nhàng",
    ],
    "melancholic emotional piano": [
        # KHÔNG dùng riêng chữ "nhớ": ngách này đầy từ "trí nhớ"/"ghi nhớ" (chuyện nhận thức,
        # trung tính) — khớp bừa sẽ gán nhạc piano buồn cho video mẹo cải thiện trí nhớ.
        r"buồn", r"cô đơn", r"chia tay", r"mất mát", r"tổn thương", r"khóc",
        r"nhớ nhung", r"thương nhớ", r"tiếc nuối",
    ],
    "tense anxious suspenseful": [
        r"lo âu", r"lo lắng", r"căng thẳng", r"sợ", r"áp lực", r"stress", r"hoảng", r"ám ảnh",
    ],
    "upbeat motivational inspiring": [
        r"động lực", r"cố gắng", r"thành công", r"tự tin", r"vượt qua", r"mạnh mẽ", r"thay đổi",
    ],
    "playful quirky lighthearted": [
        r"hài", r"vui", r"funny", r"buồn cười", r"thú vị", r"bất ngờ",
    ],
    "dark mysterious cinematic": [
        # BỎ "sự thật": tên ngách là "Sự Thật Thú Vị" nên gần như kịch bản nào cũng chứa cụm này,
        # để lại thì đa số video bị gán nhạc kiểu kinh dị — sai hẳn tông mẹo tâm lý đời thường.
        r"kinh dị", r"bí ẩn", r"rùng rợn", r"ghê rợn", r"đáng sợ",
    ],
}

# Mood mặc định khi kịch bản không rơi rõ vào nhóm nào — trung tính, hợp giọng kể chuyện đời
# thường/tâm lý (không quá kịch tính như "cinematic" chung chung trước đây).
DEFAULT_MOOD_QUERY = "calm contemplative background instrumental"


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
