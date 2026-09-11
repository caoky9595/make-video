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


# DANH SÁCH model Gemini thử lần lượt, KHÔNG phải 1 model duy nhất.
# Lý do: free tier giới hạn theo quota `GenerateRequestsPerDayPerProjectPerModel` = 20 request/NGÀY,
# và chữ "PerModel" nghĩa là MỖI MODEL CÓ HẠN MỨC RIÊNG. Hết 20 lượt của model này thì chuyển sang
# model khác vẫn còn nguyên 20 lượt — xếp tầng 3 model là có ~60 lượt/ngày thay vì 20.
# Thứ tự xếp theo độ ổn định đo thực tế 24/08/2026 (mỗi model gọi thử nhiều lần):
#   gemini-2.5-flash  3/3 và 4/4 OK, trễ TB 1,4s  <- tốt nhất
#   gemini-3.5-flash  3/3 OK, trễ TB 2,1s
# KHÔNG dùng alias `gemini-flash-latest`: alias trỏ tới bản flash mới nhất, cũng là bản đông nhất —
# đo được 0/3 và 2/8 request thành công (timeout + 503). Luôn ghim phiên bản cụ thể.
# Đổi nhanh bằng biến môi trường GEMINI_MODEL (nhiều model cách nhau bằng dấu phẩy).
GEMINI_MODELS = [
    m.strip() for m in os.environ.get(
        "GEMINI_MODEL", "gemini-2.5-flash,gemini-3.5-flash,gemini-flash-lite-latest"
    ).split(",") if m.strip()
]

# Groq tính CẢ max_tokens vào hạn mức token/phút (đo được x-ratelimit-limit-tokens: 8000 TPM).
# Đặt 4096 như trước khiến mỗi request "giữ chỗ" ~6.000 token -> chỉ chạy nổi ~1 request/phút rồi
# 429, dù số lượt request còn dư 998/1000. Sinh 5 prompt cảnh thực tế chỉ tốn ~900 token đầu ra,
# nên 1.500 vừa đủ chống cắt vừa không ăn hết hạn mức.
GROQ_DEFAULT_MAX_TOKENS = 1500

# Model -> ngày (YYYY-MM-DD) đã cạn quota, để khỏi gọi lại vô ích suốt phần còn lại của ngày.
# Chỉ giữ trong RAM: mất khi restart app cũng không sao, cùng lắm tốn thêm 1 lượt gọi hỏng.
_EXHAUSTED_TODAY: dict = {}

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
            # Đọc body 1 lần rồi gắn vào exception: body của HTTPError chỉ đọc được MỘT lần,
            # caller cần nó để biết 429 này là hết-quota-ngày hay chỉ vượt-rate-limit-phút.
            if not hasattr(e, "_body"):
                try:
                    e._body = e.read().decode("utf-8", "replace")
                except Exception:
                    e._body = ""
            # Hết quota theo NGÀY thì retry hoàn toàn vô nghĩa (không hồi trong vài giây) —
            # thoát ngay để nhường lượt cho model kế tiếp, đỡ bắt người dùng chờ.
            if "PerDay" in e._body:
                raise e
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


def call_groq(prompt: str, json_mode: bool = False, model: str = "openai/gpt-oss-120b",
              max_tokens: int = GROQ_DEFAULT_MAX_TOKENS) -> str:
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
        "max_tokens": max_tokens,
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


def call_llm_with_fallback(prompt: str, json_mode: bool = False, max_tokens: int = GROQ_DEFAULT_MAX_TOKENS) -> str:
    """Thử lần lượt từng model Gemini trong GEMINI_MODELS, hết sạch mới sang Groq.

    Free tier Gemini chỉ cho 20 request/ngày MỖI MODEL, nên khi model đầu báo hết quota thì model
    kế tiếp vẫn còn nguyên hạn mức của nó — nhờ vậy không bị đứng hình cả ngày chỉ vì 1 model cạn.
    Trả về text thô — caller tự json.loads nếu json_mode=True.
    """
    import time as _time

    api_key = os.environ.get("GEMINI_API_KEY")
    today = _time.strftime("%Y-%m-%d")
    if api_key:
        for model in GEMINI_MODELS:
            # Model đã cạn quota NGÀY hôm nay thì bỏ qua thẳng, khỏi tốn thêm 1 vòng gọi mạng
            # cho mỗi request tiếp theo trong ngày.
            if _EXHAUSTED_TODAY.get(model) == today:
                continue
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.8}}
                if json_mode:
                    payload["generationConfig"]["response_mime_type"] = "application/json"
                result = call_gemini_with_retry(url, payload, max_retries=2, initial_delay=1.0)
                return result["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                if "PerDay" in getattr(e, "_body", ""):
                    _EXHAUSTED_TODAY[model] = today
                    logger.warning(f"  [LLM] Gemini '{model}' đã hết quota ngày, bỏ qua tới hết hôm nay.")
                else:
                    logger.warning(f"  [LLM] Gemini '{model}' lỗi ({e}), thử model kế tiếp...")

    logger.warning("  [LLM] Không model Gemini nào dùng được, chuyển sang Groq.")
    return call_groq(prompt, json_mode=json_mode, max_tokens=max_tokens)


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
CHARS_PER_SECOND_ESTIMATE = 17  # đo THỰC TẾ với giọng mặc định MỚI `tiktok_nam_1`: kịch bản 242
# ký tự -> 14,09 giây -> 17,2 ký tự/giây (đo 11/09/2026, khớp với mốc 16,7 đo trước đó). Đã bỏ
# hẳn FPT (leminh) vì free tier liên tục 429 trong lúc dùng thực tế, và bỏ namminh (Edge) vì nghe
# ra âm Nam Bộ chứ không phải Bắc như suy đoán ban đầu — namminh trước đó là 12,1 ký tự/giây,
# CHẬM HƠN ~40% so với tiktok_nam_1, nên số này ảnh hưởng cả DEFAULT_SCRIPT_WORD_CAP (app.py) lẫn
# ước lượng % hiển thị trên UI (frontend/.../Editor.tsx dòng tính "X từ ≈ Y giây") — cả 2 chỗ đó
# PHẢI cùng dùng 17, không được để chỗ 12 chỗ 17 (đúng lỗi TARGET_SEC đã sửa trước đây).
# tiktok_nam_1 KHÔNG chỉnh được tốc độ (rate luôn cố định), khác các giọng Edge/FPT cũ.
# Đổi giọng mặc định thì phải đo lại con số này. Tham chiếu đã đo:
#   tiktok_nam_1  -> 17,2 ký tự/giây (không chỉnh được tốc độ)   <- ĐANG DÙNG
#   namminh (Edge, đã bỏ)  +0% -> 12,1      leminh (FPT, đã bỏ) -> chưa đo được (429 liên tục)


SCENE_EFFORT_PENALTY_SEC = 3  # mỗi cảnh thêm = 1 lần thao tác tay thật trên Flow (dán prompt,
# chờ, tải) — quy đổi thành "phạt" tương đương vài giây lãng phí, để thuật toán không chọn
# nhiều cảnh ngắn chỉ để tiết kiệm vài giây audio thừa (trần độ dài càng thấp, càng dễ xảy ra
# nếu chỉ tối ưu lãng phí thuần tuý mà không tính công sức thao tác tay).

# Độ dài mỗi cảnh MONG MUỐN và mức phạt cho từng giây vượt quá.
# Vì sao cần phạt riêng cho cảnh dài: clip Veo gần như tĩnh (đo được 99% pixel giống hệt nhau
# giữa 2 frame liền kề), nên cảnh 6-8 giây là 6-8 giây khán giả nhìn một hình gần như bất động —
# đúng lý do video rời ở mốc 0:02 và chỉ 4,8% xem hết.
# Chỉ hạ SCENE_EFFORT_PENALTY_SEC thì KHÔNG giải quyết được: với audio 14 giây, 2 cảnh x 8s
# lãng phí 2 giây còn 4 cảnh x 4s cũng lãng phí 2 giây — bằng nhau, nên thuật toán luôn chọn
# phương án ít cảnh. Phải tính thẳng "cảnh càng dài càng mất người xem" vào điểm.
# Ngách kể chuyện giữ chân bằng CÂU CHUYỆN chứ không bằng nhịp cắt cảnh, nên cảnh dài hơn được.
# Mốc 4s trước đây đặt cho format cũ (hình gần như tĩnh, không có gì giữ người xem ngoài chuyển
# động). Nâng lên 6s để giảm số clip phải tạo tay: video 30s còn 5 clip thay vì 8.
SCENE_TARGET_SEC = 6
LONG_SCENE_PENALTY_PER_SEC = 2.5


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
            long_scene_penalty = n * max(0, d - SCENE_TARGET_SEC) * LONG_SCENE_PENALTY_PER_SEC
            score = waste + n * SCENE_EFFORT_PENALTY_SEC + long_scene_penalty
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


# PHONG CÁCH HÌNH CỐ ĐỊNH của kênh, ghép vào mọi prompt cảnh để các cảnh trông cùng một bộ phim.
# Ngách bí ẩn KHÔNG dùng nhân vật mascot: nội dung là dựng lại hiện trường/sự việc, không phải một
# người dẫn chuyện xuất hiện xuyên suốt. Đây cũng là lợi thế lớn — không ai có footage thật của vụ
# việc hàng chục năm trước, nên hình dựng bằng AI là chuẩn mực của ngách, không bị coi là hàng giả
# (khác hẳn cảnh đời thường, vốn lẽ ra phải quay thật nên hình AI lộ ngay).
SCENE_STYLE = (
    "cinematic documentary reconstruction, desaturated muted color grade, heavy atmosphere, "
    "volumetric haze, film grain, dramatic low-key lighting, photorealistic, no text, no watermark"
)

FALLBACK_SCENE_DESCRIPTION = (
    f"{SCENE_STYLE}, a dimly lit abandoned location, cold blue moonlight through broken windows, "
    "slow creeping camera push-in, unsettling stillness"
)


def _generic_scene_fallback(sub_texts: list) -> list:
    """Fallback khi cả Gemini lẫn Groq đều lỗi: dùng 1 mô tả cảnh chung chung nhưng đúng ngách
    (tiếng Anh) cho mọi câu."""
    return [FALLBACK_SCENE_DESCRIPTION] * len(sub_texts)


def generate_scene_prompts_with_gemini(script_text: str, sub_texts: list, scene_duration_sec: int = 10) -> list:
    """Sinh prompt tiếng Anh nhất quán cho từng cảnh — dùng cho trợ lý "Hoạt hình Veo thủ công"
    (người dùng copy từng prompt dán vào Google Flow).

    Ghép phong cách hình CỐ ĐỊNH (SCENE_STYLE) vào khung cảnh riêng của từng câu do Gemini/Groq
    dựng — để các cảnh trông như "cùng một bộ phim" thay vì rời rạc. Ngách bí ẩn không dùng nhân
    vật dẫn chuyện, mỗi cảnh là một hiện trường/khung cảnh của sự việc.
    Trả về list cùng độ dài với sub_texts (fallback: mô tả cảnh chung chung nếu cả 2 đều lỗi).
    """
    import json

    if not sub_texts:
        return _generic_scene_fallback(sub_texts)
    if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GROQ_API_KEY"):
        return _generic_scene_fallback(sub_texts)

    numbered_subs = "\n".join(f"{i+1}. {t}" for i, t in enumerate(sub_texts))
    prompt = f"""Bạn là đạo diễn hình ảnh viết prompt cho Google Flow/Veo, kênh KỂ CHUYỆN BÍ ẨN & VỤ ÁN CÓ THẬT.
Nhiệm vụ: với mỗi câu thoại, viết 1 prompt tiếng Anh dựng lại KHUNG CẢNH minh hoạ cho câu đó.

Kịch bản đầy đủ: {script_text[:1200]}

Danh sách {len(sub_texts)} câu thoại theo thứ tự thời gian:
{numbered_subs}

Nhiệm vụ:
1. Mỗi prompt LUÔN bắt đầu bằng đúng nguyên văn phong cách hình cố định của kênh:
   "{SCENE_STYLE}"
   Giữ nguyên không đổi để mọi cảnh trông cùng một bộ phim.
2. Sau phần phong cách, viết 40-60 TỪ (đếm riêng) dựng lại khung cảnh của câu thoại đó, đủ 4 thứ:
   - BỐI CẢNH CỤ THỂ đúng nội dung câu (khu rừng tuyết đêm, khoang tàu bỏ hoang, hầm mộ đá,
     đồn cảnh sát thập niên 70...). Có chi tiết vật thể kể được chuyện: lều rách, giày bỏ lại,
     đèn pin lăn trên tuyết, hồ sơ ố vàng.
   - CHUYỂN ĐỘNG CAMERA chậm, tạo bất an: "slow dolly push-in", "drifting aerial descent",
     "handheld unsteady approach". BẮT BUỘC có, vì cảnh tĩnh làm người xem lướt.
   - GÓC MÁY/CỠ CẢNH: "extreme wide establishing shot", "low angle", "overhead top-down".
   - ÁNH SÁNG: "cold moonlight", "single flashlight beam in darkness", "grey overcast dawn".
   Viết bằng CỤM PHÂN TỪ nối dấu phẩy, không viết thành câu có chủ ngữ.
3. **KHÔNG có người dẫn chuyện xuất hiện.** Nếu cảnh cần người thì chỉ là bóng dáng mờ, người ở
   xa, hoặc chỉ thấy bàn tay/dấu chân — KHÔNG cận mặt ai, KHÔNG nhân vật cố định. Ngách này kể về
   SỰ VIỆC, không phải về một người dẫn.
4. **KHÔNG máu me, tử thi, thương tích, bạo lực.** Gợi sự bí ẩn bằng cái VẮNG MẶT và cái BỎ LẠI
   (lều trống, bàn ăn còn nguyên, dấu chân dừng giữa chừng), không bằng cảnh ghê rợn — vừa bị hạn
   chế phân phối, vừa kém hiệu quả hơn.
5. Mỗi cảnh phải KHÁC nhau rõ rệt về bối cảnh và góc máy, không lặp lại.
6. Chỉ mô tả hình, KHÔNG chèn chữ hay lời thoại vào ảnh.
7. Một số câu thoại có thể đã gộp nhiều ý vì mỗi cảnh là 1 clip Flow ~{scene_duration_sec} giây —
   khi đó chọn MỘT hình ảnh đại diện rõ nét nhất, không nhồi hết mọi ý vào 1 prompt.

TỰ KIỂM TRA: bỏ phần phong cách ra, phần còn lại có tả được một KHUNG CẢNH CỤ THỂ với chuyển động
camera không? Nếu chỉ còn mấy từ khoá địa điểm suông thì prompt đó rỗng, phải viết lại.

CHỈ TRẢ VỀ JSON array đúng {len(sub_texts)} phần tử (mỗi phần tử = phong cách nguyên văn + 40-60 từ
dựng cảnh), theo đúng thứ tự: ["prompt cảnh 1", "prompt cảnh 2", ...]
"""

    try:
        content = call_llm_with_fallback(prompt, json_mode=True)
        prompts = json.loads(content)
        if isinstance(prompts, list) and len(prompts) == len(sub_texts):
            return [str(x) for x in prompts]
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


# ============================================================
# CHẾ ĐỘ NỀN "BẢNG HỒ SƠ ĐIỀU TRA" — thay thế clip Flow bằng đồ hoạ dựng bằng code (GSAP), không
# cần AI video-gen. Xem core/engines/templates/gsap_video.html::window.setCaseFile.
# ============================================================

CASE_FILE_FALLBACK = {
    "case_number": "07",
    "case_title": "HỒ SƠ VỤ ÁN",
    "status_label": "CHƯA CÓ LỜI GIẢI",
    "beats": [
        {"note_lines": ["Nhân chứng cuối cùng nhìn thấy tại [[hiện trường]]."]},
        {"note_lines": ["Không tìm thấy [[dấu vết rời đi]] nào được ghi nhận."]},
        {"note_lines": ["Đến nay hồ sơ vẫn còn [[bỏ ngỏ]]."]},
    ],
    "photo_caption": "HIỆN TRƯỜNG",
    "map_caption": "VỊ TRÍ CUỐI CÙNG",
    "timeline": ["21:40", "22:40", "23:15", "??:??"],
}

_CASE_FILE_REQUIRED_KEYS = set(CASE_FILE_FALLBACK.keys())

MIN_CASE_FILE_BEATS = 3
MAX_CASE_FILE_BEATS = 5


def generate_case_file_content(script_text: str) -> dict:
    """Sinh nội dung THẬT cho 'bảng hồ sơ điều tra' (case_number/title/beats/photo/map/timeline)
    từ chính kịch bản — thay cho nội dung giả lập dùng khi demo style ban đầu.

    `beats`: DANH SÁCH nhiều mốc tình tiết thay vì 1 nội dung tĩnh — bảng phải cảm giác như đang
    được BỔ SUNG GHI CHÚ MỚI liên tục trong lúc video phát (giống lật từng trang hồ sơ theo đúng
    diễn biến), không đứng yên từ đầu tới cuối như bản demo gốc chỉ có 1 note cố định.

    Bảng này là NỀN/SET DRESSING chạy song song với phụ đề động (không thay thế phụ đề), nên nội
    dung ở đây được phép súc tích/khác giọng văn phụ đề (văn phong hồ sơ, không phải lời kể) —
    không cần khớp nguyên văn từng chữ với script.
    Trả về dict luôn đủ field (fallback tĩnh nếu AI lỗi/JSON hỏng) để phía render không phải tự
    xử lý field thiếu.
    """
    import json as _json

    if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GROQ_API_KEY"):
        return _json.loads(_json.dumps(CASE_FILE_FALLBACK))  # deep copy, tránh caller sửa nhầm bản gốc

    n_beats = estimate_ideal_scene_count(script_text, min_scenes=MIN_CASE_FILE_BEATS, max_scenes=MAX_CASE_FILE_BEATS)

    prompt = f"""Bạn dựng nội dung cho 1 "bảng hồ sơ điều tra" (evidence board) làm NỀN cho video kể
chuyện ngách Bí Ẩn & Vụ Án Có Thật. Đây là đạo cụ hình ảnh chạy NỀN, không phải phụ đề — không cần
khớp nguyên văn kịch bản, chỉ cần đúng tinh thần và các chi tiết chính. Bảng PHẢI cảm giác như đang
được BỔ SUNG GHI CHÚ MỚI liên tục trong lúc video phát, không phải 1 tờ giấy đứng yên từ đầu tới cuối.

Kịch bản: {script_text[:1200]}

Viết đúng các trường sau, văn phong HỒ SƠ/TÀI LIỆU (ngắn, khách quan, không phải văn kể chuyện):
- case_number: 2 chữ số bất kỳ (dạng chuỗi, vd "07")
- case_title: tiêu đề hồ sơ, TỐI ĐA 28 ký tự, VIẾT HOA, tóm tắt đúng sự việc (vd "MẤT TÍCH TRÊN CHUYẾN TÀU ĐÊM")
- status_label: 2-4 từ. Nếu vụ CÒN BỎ NGỎ thật sự thì ghi kiểu "CHƯA CÓ LỜI GIẢI"; nếu kịch bản sẽ
  hé lộ đáp án ở câu cuối thì ghi kiểu "ĐANG ĐIỀU TRA" (bảng KHÔNG được lộ đáp án dù script có nói).
- beats: mảng ĐÚNG {n_beats} phần tử, mỗi phần tử 1 MỐC TÌNH TIẾT MỚI theo ĐÚNG THỨ TỰ diễn biến
  trong kịch bản — vd beat 1 là tình huống ban đầu, beat 2 là phát hiện đầu tiên, beat giữa là chi
  tiết ngày càng khó hiểu, beat cuối là hiện trạng/mốc gần nhất. MỖI phần tử là object dạng
  {{"note_lines": [...]}} với 1-2 câu ngắn (dưới 16 từ/câu) văn phong ghi chú hồ sơ. Mỗi câu đánh
  dấu ĐÚNG 1 cụm 1-3 từ bằng [[ ]] (chi tiết nhạy cảm/then chốt nhất câu — sẽ hiện thành vệt đen
  "đã redact", không phải chữ thật). TUYỆT ĐỐI KHÔNG lặp lại cùng 1 chi tiết ở 2 beat khác nhau —
  mỗi beat phải mang thông tin MỚI, tiến triển dần, không phải diễn giải lại beat trước.
- photo_caption: nhãn ảnh hiện trường, TỐI ĐA 22 ký tự, VIẾT HOA (vd "HIỆN TRƯỜNG — 04:12"), lấy giờ
  hoặc địa điểm nếu kịch bản có nhắc, không có thì bỏ giờ và chỉ ghi địa điểm/khung cảnh chung.
- map_caption: nhãn mảnh bản đồ, TỐI ĐA 22 ký tự, VIẾT HOA (vd "VỊ TRÍ CUỐI CÙNG").
- timeline: mảng 3-4 chuỗi giờ/mốc THEO THỨ TỰ THỜI GIAN (định dạng "HH:MM" hoặc mốc mô tả ngắn nếu
  kịch bản không có giờ cụ thể, vd "TRƯỚC KHI MẤT TÍCH"), mốc CUỐI CÙNG luôn là "??:??".

CHỈ TRẢ VỀ JSON đúng format, đúng {n_beats} phần tử trong "beats":
{{"case_number":"..","case_title":"..","status_label":"..","beats":[{{"note_lines":["..."]}}],"photo_caption":"..","map_caption":"..","timeline":["..","..","??:??"]}}"""

    try:
        content = call_llm_with_fallback(prompt, json_mode=True)
        data = _json.loads(content)
        if not isinstance(data, dict) or not _CASE_FILE_REQUIRED_KEYS.issubset(data.keys()):
            logger.warning("  [Case File] AI trả thiếu field, dùng fallback tĩnh.")
            return _json.loads(_json.dumps(CASE_FILE_FALLBACK))
        beats = data.get("beats")
        if not isinstance(beats, list) or not beats or not all(
            isinstance(b, dict) and isinstance(b.get("note_lines"), list) and b["note_lines"] for b in beats
        ):
            logger.warning("  [Case File] AI trả 'beats' sai định dạng, dùng fallback tĩnh.")
            return _json.loads(_json.dumps(CASE_FILE_FALLBACK))
        if not isinstance(data.get("timeline"), list) or len(data["timeline"]) < 2:
            data["timeline"] = CASE_FILE_FALLBACK["timeline"]
        return data
    except _json.JSONDecodeError as e:
        logger.warning(f"  [Case File] JSON lỗi ({e}), dùng fallback tĩnh.")
        return _json.loads(_json.dumps(CASE_FILE_FALLBACK))
    except Exception as e:
        logger.info(f"  [Case File] Error: {e}. Dùng fallback tĩnh.")
        return _json.loads(_json.dumps(CASE_FILE_FALLBACK))


# ============================================================
# TRỢ LÝ "CLAUDE DESIGN" — nhánh thứ 2 song song với "Hoạt hình Veo thủ công". Khác biệt: Google
# Flow chỉ sinh HÌNH (không âm thanh, không phụ đề), còn Claude Design tự dựng animation + phụ đề
# nhưng KHÔNG có giọng đọc riêng — nên trợ lý này đưa CẢ giọng đọc thật (đã ghi âm bằng TTS của
# app) + mốc thời gian thật của từng câu vào 1 bản "brief" duy nhất, để Claude Design đồng bộ
# animation đúng theo giọng đọc có sẵn thay vì tự bịa giọng khác.
# ============================================================

def build_sentence_timings_from_words(words_data: list) -> list:
    """Gộp word-timing (subtitles_words.json) thành mốc thời gian THEO CÂU — tách tại dấu kết câu
    (.!?), dùng timestamp THẬT của TTS engine đang dùng (không phân biệt Edge/TikTok/Google, vì
    đều đã có sẵn words_data chuẩn hoá cùng 1 định dạng). Trả về list (câu, start, end)."""
    sentences = []
    buf, start = [], None
    for w in words_data:
        text = str(w.get("text", "")).strip()
        if not text:
            continue
        if start is None:
            start = w["start"]
        buf.append(text)
        if re.search(r'[.!?…]["\'”’)]*$', text):
            sentences.append((" ".join(buf), start, w["end"]))
            buf, start = [], None
    if buf and start is not None:
        sentences.append((" ".join(buf), start, words_data[-1]["end"]))
    return sentences


def generate_claude_design_brief(script_text: str, duration_sec: float, sentence_timings: list,
                                  audio_filename: str) -> str:
    """Dựng 1 bản brief để dán thẳng vào Claude Design (Anthropic) — KHÔNG gọi LLM, chỉ ghép
    template + dữ liệu thời gian THẬT đã đo, vì đây là thông tin cấu trúc/kỹ thuật, không cần văn
    sáng tạo, và tránh thêm 1 điểm lỗi (429/JSON hỏng) vào bước chuẩn bị vốn đã cần chính xác."""
    lines = [
        f'Dựng 1 video dọc 9:16 (1080x1920), đúng {duration_sec:.1f} giây, ngách "Bí Ẩn & Vụ Án '
        'Có Thật" trên TikTok (kể chuyện 1 vụ án/hiện tượng có thật còn bí ẩn).',
        "",
        "PHONG CÁCH: tối, u ám, điện ảnh — như phim tài liệu tội phạm thật, KHÔNG phải hoạt hình "
        "dễ thương/màu sáng. Được tự do sáng tạo cách kể (nhân vật minh hoạ, hồ sơ giấy tờ, bản "
        "đồ, dòng thời gian, silhouette...) miễn giữ đúng tông tối/bí ẩn và ĐÚNG SỰ THẬT của vụ "
        "việc — không bịa thêm chi tiết rùng rợn không có trong kịch bản dưới đây.",
        "",
        f"KỊCH BẢN ĐẦY ĐỦ:\n{script_text.strip()}",
        "",
        "DIỄN BIẾN THEO ĐÚNG THỜI ĐIỂM GIỌNG ĐỌC THẬT (đã ghi âm sẵn, animation PHẢI khớp các mốc "
        "này — mỗi mốc là lúc giọng đọc bắt đầu nói câu đó):",
    ]
    for text, start, end in sentence_timings:
        lines.append(f'  {start:.1f}s–{end:.1f}s: "{text}"')
    lines += [
        "",
        f'FILE ÂM THANH: đã đính kèm "{audio_filename}" ở tin nhắn này — dùng ĐÚNG file này làm '
        "lời thoại của video, TUYỆT ĐỐI KHÔNG tự tạo giọng đọc/giọng AI khác thay thế.",
        "",
        "YÊU CẦU KỸ THUẬT:",
        "- Khung 1080x1920 (dọc, đúng tỉ lệ TikTok).",
        f"- Tổng thời lượng animation = đúng {duration_sec:.1f} giây, khớp hết file âm thanh, không cắt cụt.",
        "- Phụ đề chữ hiện đúng lúc giọng đọc nói tới câu đó (theo mốc thời gian ở trên).",
        "- Không chèn logo/watermark của bên nào khác ngoài kênh cá nhân.",
        "- Kết bằng 1-2 giây giữ khung hình tĩnh để người xem đọc nốt câu hỏi/câu chốt cuối video.",
    ]
    return "\n".join(lines)
