"""
bg_finder.py - AI Scene Prompt Helper
======================================
Gọi Gemini (tự chuyển sang Groq nếu Gemini hết quota) để: tách kịch bản thành từng câu và
sinh prompt tiếng Anh nhất quán cho mỗi cảnh — dùng cho trợ lý "Hoạt hình Veo thủ công"
(người dùng tự dán prompt vào Google Flow để tạo video bằng Veo).
"""

import os
import re
from dotenv import load_dotenv
from core.utils.logger_config import logger

# Tải biến môi trường từ file .env
load_dotenv()


# Model Gemini dùng cho mọi tác vụ sinh chữ (ý tưởng/kịch bản/prompt cảnh/caption).
# KHÔNG dùng alias `gemini-flash-latest`: alias luôn trỏ tới bản flash mới nhất, mà bản mới nhất
# là bản đông nhất — đo thực tế 24/08/2026 cho thấy alias này 0/3 request thành công (timeout +
# 429), còn bản ghim `gemini-2.5-flash` 3/3 thành công, trễ TB 1,4s. Ghim phiên bản cụ thể để
# tính ổn định không phụ thuộc việc Google trỏ alias sang đâu.
# Đổi nhanh bằng biến môi trường GEMINI_MODEL trong .env nếu sau này model này chậm/bị bỏ.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Mã lỗi HTTP đáng thử lại: 429 = vượt rate limit, còn 5xx là lỗi TẠM THỜI phía Google
# (503 = model đang quá tải — hay gặp nhất ở free tier vào giờ cao điểm). Trước đây chỉ retry
# 429, nên 503 bị `raise` ngay lập tức và bỏ Gemini luôn dù chỉ cần thử lại sau 1-2 giây là được.
GEMINI_RETRYABLE_CODES = (429, 500, 502, 503, 504)

# Không đặt timeout thì urlopen có thể treo VÔ HẠN — lúc Gemini chậm, cả request của người dùng
# treo theo thay vì fail nhanh để nhảy sang Groq.
# Con số 30s lấy theo TẢI THẬT: sinh prompt cảnh (3-5 prompt tiếng Anh 40-60 từ, trả JSON) đo
# được ~9-11s khi thành công. Đừng hạ về ~12s: sát mép quá nên timeout chập chờn dù Gemini vẫn
# đang chạy bình thường (đã bị đúng lỗi này khi hiệu chỉnh bằng prompt ngắn 1 từ, chỉ mất 1,4s).
GEMINI_TIMEOUT_SEC = 30

# Tổng thời gian tối đa dành cho Gemini trước khi bỏ sang Groq. Cần cái này vì 2 loại lỗi có
# giá rất khác nhau: 503 trả về NGAY (retry gần như miễn phí), còn timeout ngốn đủ 30s mỗi lần.
# Không có ngân sách tổng thì gặp chuỗi timeout là người dùng phải chờ cả phút — trong khi Groq
# vẫn rảnh và miễn phí. Hết ngân sách thì dừng thử, nhảy sang Groq luôn.
GEMINI_TOTAL_BUDGET_SEC = 35


def call_gemini_with_retry(url: str, payload: dict, max_retries: int = 4, initial_delay: float = 0.8) -> dict:
    """Gọi Gemini API bằng urllib, retry các lỗi tạm thời (429 + 5xx) với backoff.

    Dừng sớm khi hết GEMINI_TOTAL_BUDGET_SEC để không bắt người dùng chờ quá lâu.
    """
    import urllib.request
    import urllib.error
    import json
    import time

    delay = initial_delay
    last_err = None
    started = time.monotonic()

    for attempt in range(max_retries):
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=GEMINI_TIMEOUT_SEC) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            # Lỗi vĩnh viễn (400 sai payload, 401/403 sai key, 404 sai model...) thì retry vô
            # nghĩa — thoát ngay để nhảy sang Groq cho nhanh.
            if e.code not in GEMINI_RETRYABLE_CODES:
                raise e
            if attempt == max_retries - 1 or time.monotonic() - started + delay > GEMINI_TOTAL_BUDGET_SEC:
                break
            logger.warning(
                f"  [Gemini API] Lỗi tạm thời HTTP {e.code} "
                f"({'quá tải' if e.code >= 500 else 'rate limit'}), thử lại sau {delay}s..."
            )
            time.sleep(delay)
            delay *= 2
        except Exception as e:
            # Timeout/lỗi mạng — cũng là tạm thời, vẫn thử lại.
            last_err = e
            if attempt == max_retries - 1 or time.monotonic() - started + delay > GEMINI_TOTAL_BUDGET_SEC:
                break
            logger.warning(f"  [Gemini API] {type(e).__name__}, thử lại sau {delay}s...")
            time.sleep(delay)
            delay *= 2

    if last_err:
        raise last_err
    raise RuntimeError("Không thể kết nối tới Gemini API")


def call_groq(prompt: str, json_mode: bool = False, model: str = "openai/gpt-oss-120b") -> str:
    """Gọi Groq (miễn phí ~14.400 request/ngày) bằng API OpenAI-compatible.

    Cần biến môi trường GROQ_API_KEY (đăng ký miễn phí tại console.groq.com).
    Trả về text thô — caller tự json.loads nếu json_mode=True.
    """
    import urllib.request
    import json as json_lib

    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        raise RuntimeError("Chưa cấu hình GROQ_API_KEY trong .env (đăng ký miễn phí tại console.groq.com)")

    full_prompt = prompt
    if json_mode:
        full_prompt += "\n\nCHỈ TRẢ VỀ JSON hợp lệ, không kèm giải thích hay markdown code fence."

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": full_prompt}],
        "temperature": 0.8,
        # Không đặt max_tokens thì Groq dùng mặc định khá thấp -> JSON dài bị CẮT GIỮA DÒNG,
        # json.loads ném "Unterminated string" và toàn bộ prompt cảnh rơi về mô tả chung chung.
        # Sinh 5 prompt cảnh (mỗi cái ~110 từ) tốn khoảng 2.000+ ký tự JSON nên phải nới hẳn ra.
        "max_tokens": 4096,
    }
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json_lib.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {groq_key}",
            # Cloudflare (đứng trước Groq) chặn request thiếu User-Agent (403) — cùng nguyên
            # nhân đã gặp với Pollinations.
            "User-Agent": "Mozilla/5.0 (compatible; VideoMakerBot/1.0)",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json_lib.loads(response.read().decode("utf-8"))
    text = result["choices"][0]["message"]["content"].strip()
    if json_mode:
        # Groq đôi khi bọc JSON trong ```json ... ``` dù đã dặn không làm vậy — bóc ra nếu có.
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text).strip()
    return text


def call_llm_with_fallback(prompt: str, json_mode: bool = False) -> str:
    """Gọi Gemini trước; nếu lỗi (hết quota 20 request/ngày free tier, rate limit...) thì tự
    động chuyển sang Groq để tính năng (sinh ý tưởng/kịch bản/prompt cảnh) không bị gián đoạn
    cả ngày. Trả về text thô — caller tự json.loads nếu json_mode=True.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.8}}
            if json_mode:
                payload["generationConfig"]["response_mime_type"] = "application/json"
            result = call_gemini_with_retry(url, payload, max_retries=2, initial_delay=1.0)
            return result["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            logger.warning(f"  [LLM Fallback] Gemini lỗi ({e}), chuyển sang Groq...")

    return call_groq(prompt, json_mode=json_mode)


def split_script_into_sentences(script_text: str) -> list:
    """Tách kịch bản thô thành danh sách câu, cùng quy tắc tách câu với
    `tiktok_tts.py::generate_tiktok_tts` (chỉ tách tại .!?\\n, không tách tại dấu phẩy).
    Dùng cho timing phụ đề — KHÔNG dùng trực tiếp để quyết định số cảnh Flow (xem
    `group_script_into_scenes`), vì 1 câu văn không nhất thiết = 1 cảnh quay có nghĩa.
    """
    pieces = re.split(r'[.!?\n]+', script_text)
    return [p.strip() for p in pieces if p.strip()]


# Model video đang dùng (Veo 3.1 Lite) chỉ nhận đúng 3 mốc độ dài này mỗi lần tạo clip — tối đa
# 8 giây, KHÔNG phải 10s như Omni Flash (xác nhận thực tế 21/08/2026, khác nghiên cứu ban đầu).
# Vì đây là hội thoại (không có dropdown), người dùng phải NÓI rõ mốc này trong chat trước khi
# bấm phê duyệt.
FLOW_DURATION_OPTIONS = [4, 6, 8]
CHARS_PER_SECOND_ESTIMATE = 20  # tốc độ đọc TTS tiếng Việt ước lượng (đo thực tế edge-tts
# +50% ra ~24 ký tự/giây; lấy thấp hơn 1 chút cho an toàn vì TikTok TTS có chèn khoảng lặng
# giữa các câu, đọc chậm hơn edge-tts).


SCENE_EFFORT_PENALTY_SEC = 3  # mỗi cảnh thêm = 1 lần thao tác tay thật trên Flow (dán prompt,
# chờ, tải) — quy đổi thành "phạt" tương đương vài giây lãng phí, để thuật toán không chọn
# nhiều cảnh ngắn chỉ để tiết kiệm vài giây audio thừa (trần độ dài càng thấp, càng dễ xảy ra
# nếu chỉ tối ưu lãng phí thuần tuý mà không tính công sức thao tác tay).


def estimate_scenes_and_duration(script_text: str, min_scenes: int = 1, max_scenes: int = 5) -> tuple:
    """Ước lượng (số cảnh, độ dài mỗi cảnh) hợp lý dựa trên ĐỘ DÀI AUDIO ước tính của kịch bản,
    không phải số câu trong văn bản — vì mỗi cảnh = 1 lần tạo clip Flow, và clip chỉ có vài mốc độ
    dài cố định (FLOW_DURATION_OPTIONS). Duyệt mọi cặp (số cảnh, độ dài) khả thi, chọn cặp có
    điểm (lãng phí + phạt theo số cảnh) THẤP NHẤT — ưu tiên ÍT CẢNH hơn thay vì chỉ khớp giây
    tuyệt đối, vì công sức thao tác tay thực tế đáng kể hơn nhiều so với vài giây audio dư ra.
    Trả về (số_cảnh, độ_dài_giây).
    """
    estimated_seconds = len(script_text) / CHARS_PER_SECOND_ESTIMATE
    best = None  # (score, so_canh) -> (so_canh, do_dai)
    for n in range(min_scenes, max_scenes + 1):
        for d in FLOW_DURATION_OPTIONS:
            total = n * d
            if total < estimated_seconds:
                continue  # không đủ che audio, loại
            waste = total - estimated_seconds
            score = waste + n * SCENE_EFFORT_PENALTY_SEC
            if best is None or score < best[0]:
                best = (score, n, d)
    if best is None:
        # Audio quá dài so với mọi tổ hợp thử (hiếm, kịch bản rất dài) — dùng max cảnh + mốc dài nhất.
        return max_scenes, FLOW_DURATION_OPTIONS[-1]
    return best[1], best[2]


def estimate_ideal_scene_count(script_text: str, min_scenes: int = 1, max_scenes: int = 5) -> int:
    """Chỉ lấy số cảnh từ `estimate_scenes_and_duration` — dùng khi không cần độ dài đi kèm."""
    n, _ = estimate_scenes_and_duration(script_text, min_scenes, max_scenes)
    return n


def group_script_into_scenes(script_text: str, max_scenes: int = None) -> list:
    """Gộp các câu liên tiếp thành 1 số cảnh hợp lý (ước lượng theo độ dài audio thực tế qua
    `estimate_ideal_scene_count`, xem ở trên để hiểu vì sao không dùng số câu trong văn bản),
    thay vì tách 1 cảnh/câu.

    Mỗi cảnh = 1 lần người dùng phải tự tạo clip trên Google Flow, nên tách quá vụn (1 câu
    ngắn/cảnh, như `split_script_into_sentences` trả về) khiến thao tác thừa và mỗi cảnh chỉ
    còn vài từ nội dung — không khớp cấu trúc Hook->Demo->Chốt (2-5 cảnh/video) khuyến nghị ở
    `docs/content_ideas_bank.md`. Câu đầu luôn là Hook, câu cuối luôn là Chốt/CTA (đúng cấu
    trúc kịch bản đang dùng), các câu giữa được gộp đều vào các cảnh Demo còn lại.
    """
    if max_scenes is None:
        max_scenes = estimate_ideal_scene_count(script_text)

    sentences = split_script_into_sentences(script_text)
    if len(sentences) <= max_scenes:
        return sentences

    if max_scenes <= 2:
        n = len(sentences)
        base, rem = divmod(n, max_scenes)
        groups, idx = [], 0
        for i in range(max_scenes):
            size = base + (1 if i < rem else 0)
            if size:
                groups.append(" ".join(sentences[idx:idx + size]))
            idx += size
        return groups

    hook = sentences[0]
    chot = sentences[-1]
    middle = sentences[1:-1]
    demo_slots = max_scenes - 2
    if len(middle) <= demo_slots:
        demo_groups = middle
    else:
        n = len(middle)
        base, rem = divmod(n, demo_slots)
        demo_groups, idx = [], 0
        for i in range(demo_slots):
            size = base + (1 if i < rem else 0)
            demo_groups.append(" ".join(middle[idx:idx + size]))
            idx += size
    return [hook, *demo_groups, chot]


# Nhân vật/mascot CỐ ĐỊNH xuyên suốt kênh — không để AI tự nghĩ lại mỗi video (khác trước đây),
# vì đã kiểm chứng thực tế: nếu để AI tự chốt mô tả bằng chữ mỗi lần, Veo vẫn ra người khác nhau
# giữa các cảnh dù mô tả gần giống hệt nhau. Cách đúng là dùng ảnh tham chiếu qua "Ingredients to
# Video" của Veo 3.1 (upload 1 ảnh nhân vật cố định, tạo 1 lần từ đúng mô tả này) — mô tả chữ ở
# đây chỉ là lớp hỗ trợ thêm cho AI viết prompt, KHÔNG thay thế được ảnh tham chiếu.
MASCOT_DESCRIPTION = (
    "Bống, a gentle young Vietnamese woman, fair skin, wavy dark hair half-up with a ribbon "
    "clip, warm kind brown eyes, gold hoop earrings, layered gold necklace, lavender pleated "
    "mini skirt, white top, white high-top sneakers, slender graceful figure, modern "
    "slice-of-life anime illustration style, clean crisp linework, soft cel-shading, lavender "
    "pastel palette"
)

FALLBACK_SCENE_DESCRIPTION = (
    f"{MASCOT_DESCRIPTION}, relatable everyday moment, thoughtful expression, subtle natural "
    "motion, warm soft lighting"
)


# Đại từ/danh từ chỉ NAM -> nữ. Lưới an toàn CUỐI: dặn AI trong prompt là chưa đủ tin cậy (đo thực
# tế vẫn lọt đại từ), mà 1 chữ "he" lọt vào là mâu thuẫn ngay với "a ... woman" trong mô tả nhân
# vật, khiến Veo vẽ sai giới tính ở đúng cảnh đó. Sửa bằng code thì chắc chắn 100%.
# Thay dài trước ngắn (himself trước him trước he) để không cắt nhầm giữa từ.
_MASCULINE_FIXES = [
    (r"\bhimself\b", "herself"),
    (r"\bHimself\b", "Herself"),
    (r"\bhis\b", "her"),
    (r"\bHis\b", "Her"),
    (r"\bhim\b", "her"),
    (r"\bHim\b", "Her"),
    (r"\bhe\b", "she"),
    (r"\bHe\b", "She"),
    (r"\bman\b", "woman"),
    (r"\bmale\b", "female"),
    (r"\bboy\b", "girl"),
    (r"\bguy\b", "woman"),
]


def _force_feminine(text: str) -> str:
    """Ép mọi đại từ/danh từ chỉ nam trong prompt cảnh về nữ, khớp với mascot Bống (nữ)."""
    for pattern, repl in _MASCULINE_FIXES:
        text = re.sub(pattern, repl, text)
    return text


def _generic_scene_fallback(sub_texts: list) -> list:
    """Fallback khi cả Gemini lẫn Groq đều lỗi: dùng 1 mô tả cảnh chung chung nhưng đúng ngách
    (tiếng Anh) cho mọi câu."""
    return [FALLBACK_SCENE_DESCRIPTION] * len(sub_texts)


def generate_scene_prompts_with_gemini(script_text: str, sub_texts: list, scene_duration_sec: int = 10) -> list:
    """Sinh prompt tiếng Anh nhất quán cho từng cảnh — dùng cho trợ lý "Hoạt hình Veo thủ công"
    (người dùng copy từng prompt dán vào Google Flow).

    Ghép mascot CỐ ĐỊNH (MASCOT_DESCRIPTION, không đổi giữa các video) vào hành động/bối cảnh
    riêng của từng câu do Gemini/Groq viết — để các cảnh trông như "cùng một bộ phim" thay vì rời
    rạc. Trả về list cùng độ dài với sub_texts (fallback: mô tả cảnh chung chung nếu cả 2 đều lỗi).
    """
    import json

    if not sub_texts:
        return _generic_scene_fallback(sub_texts)
    if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GROQ_API_KEY"):
        return _generic_scene_fallback(sub_texts)

    numbered_subs = "\n".join(f"{i+1}. {t}" for i, t in enumerate(sub_texts))
    prompt = f"""Bạn là đạo diễn hình ảnh chuyên viết prompt cho Google Flow/Veo, ngách Sự Thật Thú Vị & Tâm Lý Cuộc Sống.
Viết prompt đúng chuẩn khuyến nghị của Veo — PHẢI có đủ các thành phần: Chủ thể, Hành động/biểu cảm, Bối cảnh,
Phong cách hình ảnh, Góc máy/cỡ cảnh, Ánh sáng/tông màu. Thiếu góc máy hoặc ánh sáng sẽ ra cảnh phẳng,
chung chung — đây là lỗi cần tránh.

Kịch bản đầy đủ: {script_text[:1200]}

Danh sách {len(sub_texts)} câu thoại theo thứ tự thời gian:
{numbered_subs}

Nhiệm vụ:
1. Nhân vật/mascot của kênh CỐ ĐỊNH, dùng NGUYÊN VĂN không đổi cho mọi video (đây là "chị Bống" —
   người kể chuyện xuyên suốt kênh, có ảnh tham chiếu riêng để giữ nhất quán qua Veo "Ingredients to
   Video"): "{MASCOT_DESCRIPTION}". Bối cảnh/setting (phòng ngủ, văn phòng, công viên...) được phép
   ĐỔI theo từng cảnh cho hợp nội dung câu thoại đó — chỉ mô tả nhân vật ở trên là cố định, không
   được diễn giải lại hay đổi chi tiết ngoại hình.
2. Với MỖI câu thoại, viết 1 prompt tiếng Anh gồm 2 phần ghép liền:
   (a) NGUYÊN VĂN mô tả nhân vật ở bước 1 (không đổi 1 chữ), rồi
   (b) phần CẢNH RIÊNG dài 40-60 TỪ — đếm riêng, KHÔNG tính số từ của phần (a).
   Phần (b) BẮT BUỘC có đủ 5 thứ, thiếu bất kỳ thứ nào là prompt hỏng:
   - HÀNH ĐỘNG CỤ THỂ đang diễn ra (vd "slumped over a desk pushing a laptop away", "scrolling a phone
     under the blanket", "freezing mid-reach for a coffee cup") — KHÔNG được chỉ ghi địa điểm suông.
   - BIỂU CẢM MẶT + NGÔN NGỮ CƠ THỂ (vd "jaw tight, eyes darting away", "shoulders sagging, faint
     defeated smile", "eyebrows lifting in slow realisation").
   - CHI TIẾT BỐI CẢNH gợi đúng nội dung câu thoại (vd "half-finished to-do list and 3 empty mugs",
     "clock reading 2AM", "sticky notes peeling off a monitor") — chi tiết nhỏ kể được câu chuyện.
   - GÓC MÁY/CỠ CẢNH (vd "extreme close-up on face", "top-down shot", "medium shot at eye level").
   - ÁNH SÁNG/TÔNG MÀU đúng cảm xúc (vd "cold blue nighttime glow" cho lo âu, "warm golden light" cho
     nhẹ nhõm).
   CÁCH VIẾT: ưu tiên CỤM PHÂN TỪ nối bằng dấu phẩy ("standing...", "clutching...", "brow furrowing...")
   vì vừa giàu hình ảnh vừa không cần chủ ngữ. Chỗ nào bắt buộc phải có đại từ cho câu tự nhiên
   ("on her back", "over her shoulder") thì CHỈ ĐƯỢC dùng đại từ NỮ: she/her/hers. TUYỆT ĐỐI KHÔNG
   dùng he/his/him — nhân vật là NỮ, lỡ viết "he" là mâu thuẫn ngay với "a ... woman" ở phần (a),
   Veo sẽ vẽ sai giới tính. Đừng vì né đại từ mà viết cụt lủn — nội dung giàu quan trọng hơn.
   Ví dụ ĐÚNG (giàu nội dung, không đại từ — viết theo kiểu này):
     "...lavender pastel palette, slumped in a desk chair at 2AM, pushing the laptop away with one
     fingertip, jaw tight and eyes avoiding the screen, a half-written document and three empty mugs
     beside a glowing phone, extreme close-up on face at eye level, cold blue monitor glow against
     deep shadows."
   Ví dụ SAI 1 — chỉ liệt kê từ khoá suông, KHÔNG có hành động/biểu cảm (đây là lỗi HAY GẶP NHẤT,
   phải tránh): "...lavender pastel palette, home desk night, extreme close-up, cold blue soft glow"
   Ví dụ SAI 2 — dùng đại từ: "...lavender pastel palette, she is lying in bed and her eyes stare..."
3. QUAN TRỌNG — ưu tiên hàng đầu: mô tả 1 KHOẢNH KHẮC ĐỜI THƯỜNG RELATABLE thể hiện đúng cảm xúc/tình huống của câu thoại đó (vd nằm trên giường nhìn trần nhà cho chủ đề mất ngủ, giật mình nhìn đồng hồ cho chủ đề trì hoãn, biểu cảm ngạc nhiên/xoà tay lên đầu cho 1 sự thật bất ngờ). Đây là yếu tố quan trọng nhất để người xem thấy "đúng là mình" — ưu tiên biểu cảm khuôn mặt và ngôn ngữ cơ thể rõ ràng hơn là hành động chung chung. Chuyển động NHẸ NHÀNG TỰ NHIÊN (subtle motion — thở dài, chớp mắt, quay đầu chậm) — KHÔNG chuyển động quá đà/kịch tính, vì phong cách anime slice-of-life hợp với tiết chế hơn là phô diễn.
4. Một số câu thoại ở trên có thể đã GỘP nhiều câu gốc lại (1 cảnh phủ nhiều ý) vì mỗi cảnh = 1 lần tạo clip Flow ~{scene_duration_sec} giây, không thể diễn hết nhiều khoảnh khắc khác nhau trong 1 clip ngắn. Khi đó, CHỌN MỘT khoảnh khắc/cảm xúc đại diện, rõ nét nhất trong câu để mô tả — KHÔNG cố liệt kê hết mọi ý vào 1 prompt.
5. Chỉ mô tả hình ảnh (chủ thể, biểu cảm, bối cảnh, góc máy, ánh sáng), KHÔNG chèn lời thoại hay chữ viết vào ảnh.

TỰ KIỂM TRA trước khi trả về — với TỪNG prompt, bỏ phần mô tả nhân vật ra, phần còn lại có nêu rõ
nhân vật ĐANG LÀM GÌ và MẶT MŨI/DÁNG NGƯỜI THẾ NÀO không? Nếu phần còn lại chỉ là mấy từ khoá địa
điểm + góc máy + ánh sáng thì prompt đó BỊ RỖNG, phải viết lại cho đủ hành động và biểu cảm.
Mỗi cảnh phải có hành động/bối cảnh KHÁC nhau rõ rệt — không được 3 cảnh cùng một kiểu ngồi ở bàn.

CHỈ TRẢ VỀ JSON array đúng {len(sub_texts)} phần tử (mỗi phần tử = mô tả nhân vật nguyên văn + 40-60
từ cảnh riêng giàu hành động/biểu cảm), theo đúng thứ tự: ["prompt cảnh 1", "prompt cảnh 2", ...]
"""

    try:
        content = call_llm_with_fallback(prompt, json_mode=True)
        prompts = json.loads(content)
        if isinstance(prompts, list) and len(prompts) == len(sub_texts):
            return [_force_feminine(str(x)) for x in prompts]
        logger.warning(f"  [Scene Prompts] AI trả về {len(prompts) if isinstance(prompts, list) else 'không phải list'} phần tử, cần {len(sub_texts)}. Dùng fallback.")
        return _generic_scene_fallback(sub_texts)
    except json.JSONDecodeError as e:
        # Hay gặp nhất: model trả JSON bị cắt vì hết token. Log độ dài + đuôi chuỗi để lần sau
        # nhìn log là biết ngay bị cắt hay sai định dạng, không phải ngồi dò lại từ đầu.
        raw = locals().get("content", "")
        logger.warning(
            f"  [Scene Prompts] JSON lỗi ({e}). Độ dài phản hồi {len(raw)} ký tự, "
            f"đuôi: {raw[-80:]!r}. Nghi bị cắt do hết token -> dùng fallback."
        )
        return _generic_scene_fallback(sub_texts)
    except Exception as e:
        logger.info(f"  [Scene Prompts] Error: {e}. Dùng mô tả cảnh chung chung làm fallback.")
        return _generic_scene_fallback(sub_texts)
