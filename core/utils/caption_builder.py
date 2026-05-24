"""
caption_builder.py - Tạo caption TikTok theo format hiệu quả
=============================================================
Tự động tạo caption + hashtag dựa trên template (Problem/Solution,
Before/After, Top Ranking...) thay vì dùng 1 caption bán hàng cứng.

Nguyên tắc: Entertainment First, Commerce Second
  - 40% video: Giải trí / Thông tin thuần túy
  - 40% video: Problem/Solution + gắn sản phẩm tự nhiên
  - 20% video: CTA mạnh (Deal hot, Ranking)
"""

import random
from typing import Optional
from core.utils.logger_config import logger

# ============================================================
# TEMPLATE CAPTIONS
# ============================================================

TEMPLATES = {
    # === Format 1: Problem → Solution (Hiệu quả nhất) ===
    "problem_solution": [
        "{problem}\n\nMình đã thử {product} và bất ngờ!\n{result}\n\n💰 Chỉ {price}\n👉 Link trong giỏ hàng ⬇️\n\n{hashtags}",
        "{problem}\n\nCho đến khi phát hiện ra {product}...\n{result}\n\n✅ Giá chỉ {price}\n🛒 Link giỏ hàng ⬇️\n\n{hashtags}",
        "Ai cũng gặp vấn đề này: {problem}\n\nGiải pháp? {product}\n{result}\n\n💰 {price} — Link ⬇️\n\n{hashtags}",
    ],

    # === Format 2: Before / After ===
    "before_after": [
        "Trước: {before} 😰\nSau khi dùng {product}: {after} ✨\n\nKhông ngờ hiệu quả đến vậy!\n💰 Chỉ {price}\n👉 Link giỏ hàng ⬇️\n\n{hashtags}",
        "TRƯỚC vs SAU khi dùng {product} 🔥\n\n❌ Trước: {before}\n✅ Sau: {after}\n\n💰 {price} — Link ⬇️\n\n{hashtags}",
    ],

    # === Format 3: Top / Ranking ===
    "top_ranking": [
        "Top {count} {category} đáng mua nhất tháng này 🔥\n\n{ranking_items}\n\n👉 Link đầy đủ trong giỏ hàng ⬇️\n\n{hashtags}",
        "{count} sản phẩm {category} mà ai cũng nên có 💯\n\n{ranking_items}\n\n🛒 Link mua trong giỏ hàng\n\n{hashtags}",
    ],

    # === Format 4: Review thật (kể cả điểm chưa tốt — tăng uy tín) ===
    "honest_review": [
        "Review thật {product} sau {duration} ngày dùng\n\n✅ Ưu điểm:\n{pros}\n\n⚠️ Nhược điểm:\n{cons}\n\n💰 Giá: {price}\nĐánh giá: {rating}/10\n👉 Link giỏ hàng ⬇️\n\n{hashtags}",
        "{product} — Có đáng mua không?\n\n👍 {pros}\n👎 {cons}\n\nKết luận: {conclusion}\n💰 {price} — Link ⬇️\n\n{hashtags}",
    ],

    # === Format 5: Giải trí thuần (KHÔNG bán hàng — nuôi nick) ===
    "entertainment": [
        "{hook}\n\n{content}\n\n{hashtags}",
        "{hook} 😂\n\n{content}\n\nFollow để xem thêm!\n\n{hashtags}",
    ],
}

# ============================================================
# THƯ VIỆN HOOK (3 giây đầu gây tò mò)
# ============================================================

HOOK_LIBRARY = {
    "gadget": [
        "Đừng mua khi chưa xem cái này",
        "Sản phẩm này có gì mà ai cũng khen?",
        "Tiết kiệm tiền triệu nhờ mẹo này",
        "Nhà mình trước đây tốn cả đống tiền điện...",
        "Mình ước mình biết cái này sớm hơn",
    ],
    "fashion": [
        "Outfit này chỉ có 200k thôi 😱",
        "Mẹo phối đồ mà ít ai biết",
        "Đừng mặc kiểu này ra đường nhé",
        "Biến hình trong 5 giây",
    ],
    "beauty": [
        "Da mình thay đổi sau 7 ngày dùng cái này",
        "Đừng mua kem dưỡng nào trước khi xem video này",
        "Bí quyết da đẹp mà không tốn tiền spa",
    ],
    "food": [
        "Món này ngon khó cưỡng 🤤",
        "Cách nấu trong 5 phút, ngon hơn nhà hàng",
        "Đồ ăn vặt này đang cháy hàng trên TikTok",
    ],
    "general": [
        "Xem đến cuối sẽ bất ngờ!",
        "Mình vừa phát hiện ra điều này...",
        "Tại sao mọi người đang mua cái này?",
        "Sản phẩm viral nhất tuần này 🔥",
        "Thật ra giá chỉ có vậy thôi 😱",
    ],
}

# ============================================================
# THƯ VIỆN HASHTAG
# ============================================================

HASHTAG_SETS = {
    "gadget":  ["fyp", "viral", "tiktokvietnam", "review", "gadget", "dogiaygia", "sangchehaynhat"],
    "fashion": ["fyp", "viral", "tiktokvietnam", "fashion", "ootd", "thoitrang", "outfit"],
    "beauty":  ["fyp", "viral", "tiktokvietnam", "beauty", "skincare", "lamdep", "duongda"],
    "food":    ["fyp", "viral", "tiktokvietnam", "food", "anngon", "doanvat", "recipe"],
    "general": ["fyp", "viral", "tiktokvietnam", "review", "trending", "muasam", "affiliate"],
}


# ============================================================
# HÀM CHÍNH
# ============================================================

def build_caption(
    template_type: str = "problem_solution",
    category: str = "general",
    extra_tags: Optional[list] = None,
    **kwargs,
) -> dict:
    """
    Tạo caption hoàn chỉnh cho video TikTok.

    Args:
        template_type: Loại format ("problem_solution", "before_after",
                       "top_ranking", "honest_review", "entertainment")
        category:      Ngách sản phẩm ("gadget", "fashion", "beauty", "food", "general")
        extra_tags:    Hashtag bổ sung
        **kwargs:      Các biến để điền vào template (product, price, problem, result...)

    Returns:
        Dict chứa:
          - caption: str - Nội dung caption đầy đủ
          - hook: str - Hook text cho 3 giây đầu video
          - tags: list - Danh sách hashtag
    """
    # Chọn template ngẫu nhiên từ format
    templates = TEMPLATES.get(template_type, TEMPLATES["problem_solution"])
    template = random.choice(templates)

    # Tạo hashtags
    tags = HASHTAG_SETS.get(category, HASHTAG_SETS["general"]).copy()
    if extra_tags:
        tags.extend(extra_tags)
    # Loại bỏ trùng và giới hạn 8 hashtag
    tags = list(dict.fromkeys(tags))[:8]
    hashtags_str = " ".join([f"#{t}" for t in tags])

    # Chọn hook ngẫu nhiên
    hooks = HOOK_LIBRARY.get(category, HOOK_LIBRARY["general"])
    hook = kwargs.get("hook") or random.choice(hooks)

    # Điền template
    kwargs["hashtags"] = hashtags_str
    kwargs.setdefault("hook", hook)

    try:
        caption = template.format(**kwargs)
    except KeyError as e:
        # Nếu thiếu biến → dùng template đơn giản
        caption = f"{hook}\n\n👉 Link trong giỏ hàng ⬇️\n\n{hashtags_str}"

    return {
        "caption": caption.strip(),
        "hook": hook,
        "tags": tags,
    }


def auto_select_format() -> str:
    """
    Tự động chọn format caption theo tỉ lệ lý tưởng.
    40% Problem/Solution — 20% Before/After — 20% Review — 20% Ranking
    """
    roll = random.random()
    if roll < 0.40:
        return "problem_solution"
    elif roll < 0.60:
        return "before_after"
    elif roll < 0.80:
        return "honest_review"
    else:
        return "top_ranking"


# ============================================================
# CLI — TEST NHANH
# ============================================================

if __name__ == "__main__":
    # Demo tạo caption theo từng format
    logger.info("=" * 50)
    logger.info("🎬 CAPTION BUILDER — Demo")
    logger.info("=" * 50)

    # 1. Problem/Solution
    result = build_caption(
        template_type="problem_solution",
        category="gadget",
        product="quạt mini cầm tay",
        problem="Mùa hè đi đường nóng kinh khủng",
        result="Mát lạnh tức thì, pin dùng cả ngày",
        price="89k",
    )
    logger.info("\n--- Problem/Solution ---")
    logger.info(result["caption"])
    logger.info(f"\n🎣 Hook video: {result['hook']}")

    # 2. Before/After
    result = build_caption(
        template_type="before_after",
        category="beauty",
        product="serum vitamin C",
        before="Da xỉn màu, nhiều thâm mụn",
        after="Da sáng đều, thâm mờ hẳn sau 2 tuần",
        price="150k",
    )
    logger.info("\n--- Before/After ---")
    logger.info(result["caption"])

    # 3. Auto format
    logger.info("\n--- Auto Select Format ---")
    fmt = auto_select_format()
    logger.info(f"Format được chọn: {fmt}")
