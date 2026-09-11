"""
tts.py - Text-to-Speech Engine (edge-tts + TikTok TTS + Google Cloud TTS)
====================================================
Chuyển đổi kịch bản text thành file audio MP3 + file subtitle SRT.

Đã bỏ FPT.AI (commit sau "tune(voice)"): free tier liên tục 429 (hết quota ngày) trong lúc dùng
thực tế, không đáng tin làm engine chính — mà chính sách hiện tại là KHÔNG fallback khi lỗi.
"""

import asyncio
import json
import os
import re

import edge_tts
import requests
from dotenv import load_dotenv
from core.utils.logger_config import logger

load_dotenv()

# ============================================================
# DANH SÁCH GIỌNG ĐỌC
# ============================================================

# Edge-TTS voices (Microsoft)
# Đã bỏ "namminh" (vi-VN-NamMinhNeural): người dùng nghe thử bản render thật thấy giọng lệch về
# âm Nam Bộ, không phải Bắc như suy đoán ban đầu (Microsoft không công bố vùng miền chính thức
# cho 2 giọng vi-VN, đây là tai người nghe thật quyết định, không phải nhãn máy).
EDGE_VOICES = {
    "hoaimy":  "vi-VN-HoaiMyNeural",     # Nữ - giọng nữ trẻ, tự nhiên
}

# GOOGLE CLOUD TTS voices (tiếng Việt). Tên giọng theo đúng định danh của Google.
# Hạn mức miễn phí: 1 triệu ký tự/tháng cho Neural2/Chirp3-HD/Studio, 4 triệu cho Standard —
# reset hằng tháng, KHÔNG phải bản dùng thử. Kịch bản ~400 ký tự nên 5 video/ngày chỉ tốn
# ~60k/tháng, không bao giờ chạm trần.
# Cần GOOGLE_TTS_API_KEY trong .env (tạo ở console.cloud.google.com, bật Cloud Text-to-Speech API).
# DANH SÁCH NÀY CÓ THỂ THIẾU/LỖI THỜI — Google thêm bớt giọng theo thời gian. Chạy
# `python -m core.engines.tts --list-google` để lấy danh sách thật từ API bằng key của bạn.
GOOGLE_VOICES = {
    "gg_nam_wavenet":  {"id": "vi-VN-Wavenet-B",  "gender": "Nam", "desc": "Google WaveNet Nam"},
    "gg_nam_wavenet2": {"id": "vi-VN-Wavenet-D",  "gender": "Nam", "desc": "Google WaveNet Nam 2"},
    "gg_nu_wavenet":   {"id": "vi-VN-Wavenet-A",  "gender": "Nữ",  "desc": "Google WaveNet Nữ"},
    "gg_nu_wavenet2":  {"id": "vi-VN-Wavenet-C",  "gender": "Nữ",  "desc": "Google WaveNet Nữ 2"},
    "gg_nam_std":      {"id": "vi-VN-Standard-B", "gender": "Nam", "desc": "Google Standard Nam"},
    "gg_nu_std":       {"id": "vi-VN-Standard-A", "gender": "Nữ",  "desc": "Google Standard Nữ"},
}

# TIKTOK TTS voices
TIKTOK_VOICES = {
    "tiktok_nu_1": {"gender": "Nữ", "desc": "Giọng TikTok Nữ Review"},
    "tiktok_nu_2": {"gender": "Nữ", "desc": "Giọng TikTok Nữ Trẻ"},
    "tiktok_nam_1": {"gender": "Nam", "desc": "Giọng TikTok Kể chuyện bí ẩn"},
    "tiktok_nam_2": {"gender": "Nam", "desc": "Giọng TikTok Nam Đọc nhanh"},
}

# Tất cả giọng hợp lệ
ALL_VOICE_KEYS = list(EDGE_VOICES.keys()) + list(TIKTOK_VOICES.keys()) + list(GOOGLE_VOICES.keys())


def get_engine(voice: str) -> str:
    """Xác định engine dựa trên tên giọng đọc."""
    v_lower = voice.lower()
    if v_lower in EDGE_VOICES or voice in EDGE_VOICES.values() or any(v_lower in val.lower() for val in EDGE_VOICES.values()):
        return "edge"
    elif v_lower in GOOGLE_VOICES or v_lower.startswith("gg_") or v_lower.startswith("vi-vn-"):
        # Chấp nhận cả tên giọng Google truyền thẳng (vd "vi-VN-Chirp3-HD-Achernar") — danh sách
        # cứng GOOGLE_VOICES sẽ lỗi thời khi Google thêm giọng mới, không nên chặn người dùng.
        return "google"
    elif v_lower in TIKTOK_VOICES or v_lower.startswith("tiktok_"):
        return "tiktok"
    else:
        raise ValueError(
            f"Giọng '{voice}' không hợp lệ. Các giọng có sẵn:\n"
            f"  Edge-TTS: {', '.join(EDGE_VOICES.keys())}\n"
            f"  TikTok:   {', '.join(TIKTOK_VOICES.keys())}\n"
            f"  Google:   {', '.join(GOOGLE_VOICES.keys())}"
        )


def list_voices():
    """In danh sách tất cả giọng đọc có sẵn."""
    logger.info("\n📢 DANH SÁCH GIỌNG ĐỌC CÓ SẴN:")
    logger.info("=" * 60)

    logger.info("\n🎵 TIKTOK TTS (Trick 0đ - Chuẩn MMO):")
    for key, info in TIKTOK_VOICES.items():
        logger.info(f"   • {key:12s} → {info['gender']} | {info['desc']}")
    logger.info()


def parse_script(raw_text: str) -> str:
    """
    Parser thông minh: Tự động tách lời đọc từ kịch bản có format phức tạp.
    
    Hỗ trợ các format:
    1. Kịch bản có timestamp + chú thích:
       0s - 3s (Hook): (hành động) "Lời đọc thực sự"
    2. Kịch bản có bullet points:
       - Hook: "Lời đọc"
    3. Kịch bản plain text (không có ngoặc kép):
       Lời đọc bình thường sẽ được giữ nguyên.
    
    Returns:
        Chuỗi text sạch chỉ chứa lời đọc, sẵn sàng cho TTS.
    """
    # Bước 1: Làm sạch metadata cơ bản
    clean_text = raw_text
    
    # Xóa các mốc thời gian dạng "0s - 3s" hoặc "00:00 - 00:03"
    clean_text = re.sub(r'\d+s?\s*-\s*\d+s?', '', clean_text)
    clean_text = re.sub(r'\d{2}:\d{2}\s*-\s*\d{2}:\d{2}', '', clean_text)
    
    # Xóa các label dạng (Hook): hoặc (Nội dung): hoặc (CTA): hoặc [Cảnh 1]:
    clean_text = re.sub(r'\([^)]*\)\s*:?\s*', '', clean_text)
    clean_text = re.sub(r'\[[^\]]*\]\s*:?\s*', '', clean_text)
    
    # Xóa Speaker label nếu có (Ví dụ: "Người dẫn: ", "Bot: ")
    clean_text = re.sub(r'^[A-Z\w\s]+:\s*', '', clean_text, flags=re.MULTILINE)

    # Nếu sau khi xóa metadata vẫn còn ngoặc kép bao quanh cả đoạn thoại dài, 
    # ta có thể giữ lại toàn bộ text và chỉ xóa dấu ngoặc kép ở bước sau.
    logger.info(f"  [Script Parser] Processed text as plain/structured script")
    
    # Bước 2: Dọn dẹp chung
    # Xóa dấu - ở đầu dòng (bullet points)
    clean_text = re.sub(r'^\s*-\s*', '', clean_text, flags=re.MULTILINE)

    # Xóa các chú thích trong ngoặc vuông → giữ nội dung bên trong
    clean_text = re.sub(r'\[([^\]]*)\]', r'\1', clean_text)
    
    # Xóa khoảng trắng thừa ngang (giữ nguyên ngắt dòng \n để tạo khoảng ngắt nghỉ tự nhiên)
    clean_text = re.sub(r'[ \t\r\f\v]+', ' ', clean_text)
    clean_text = re.sub(r'\n\s*\n+', '\n\n', clean_text)
    clean_text = clean_text.strip()
    
    return clean_text


# ============================================================
# UTILITY: Trọng số thời gian đọc/ngừng theo từ (dùng khi phải NỘI SUY word timing,
# tức không có timestamp thật từ TTS engine cho từng từ)
# ============================================================

_DIGIT_RE = re.compile(r"\d")


def _estimate_number_syllables(token: str) -> int:
    """Ước lượng SỐ ÂM TIẾT THẬT khi đọc 1 số bằng tiếng Việt — vd "1994" chỉ 4 KÝ TỰ nhưng đọc
    thành "một nghìn chín trăm chín mươi tư" = 7 ÂM TIẾT. Đây là nguồn lệch phụ đề LỚN NHẤT đo
    được (xem _word_speak_and_pause_weight): trọng số cũ tính theo ĐỘ DÀI KÝ TỰ nên số bị coi
    ngắn ngang một từ thường, trong khi phát âm thật dài gấp nhiều lần — làm mọi từ SAU số đó
    trong cùng câu bị dồn sớm hơn thực tế. Ngách bí ẩn dùng số RẤT nhiều (năm, số người, số phút)
    nên gần như câu nào cũng dính. Không cần chính xác tuyệt đối (không convert đủ thành chữ),
    chỉ cần đủ tốt để không lệch hẳn theo cấp số nhân của độ dài số.
    """
    digits = re.sub(r"[^\d]", "", token)
    n = len(digits)
    if n == 0:
        return 0
    if n <= 2:
        return max(1, n)                      # "12" -> "mười hai" ~2, "5" -> "năm" ~1
    if n == 3:
        return 2 if digits[0] == "0" else 3   # "994" -> "chín trăm chín mươi tư" ~3 cụm
    if n == 4:
        return 6                              # năm/số 4 chữ số kiểu "1994" -> ~6-7 âm tiết
    return max(4, round(n * 1.6))              # số dài hơn (hiếm gặp) -> ước lượng theo tỉ lệ


def _word_speak_and_pause_weight(word: str) -> tuple:
    """Trả về (trọng số thời gian NÓI, trọng số thời gian NGỪNG ngay sau từ này).

    Tiếng Việt là ngôn ngữ đơn âm tiết theo nhịp gần đều — trọng số nói gần bằng nhau cho
    mọi từ, chỉ cộng thêm cho token dài bất thường (số/từ mượn tiếng Anh viết liền).

    Nếu chỉ chia đều theo độ dài mà bỏ qua dấu câu, các từ sau dấu phẩy/chấm sẽ bị gán thời
    điểm bắt đầu SỚM hơn thực tế — vì giọng đọc thật có ngừng hơi ở đó nhưng phép chia đều
    coi cả câu là nói liên tục không nghỉ. Hệ quả: phụ đề "nhảy" sang từ/cụm tiếp theo trước
    khi giọng đọc thật sự nói tới, và càng về cuối câu càng lệch nhiều (lỗi cộng dồn theo
    số dấu câu đã đi qua). Cộng thêm trọng số ngừng sau mỗi dấu câu để mô phỏng đúng quãng
    nghỉ đó, giữ từ tiếp theo không bị đẩy sớm.
    """
    if _DIGIT_RE.search(word):
        # Số: dùng ước lượng ÂM TIẾT THẬT thay vì độ dài ký tự — đo thực tế thấy "1994," trong
        # model cũ chỉ chiếm ~0.2s (bằng 1 từ thường) nhưng giọng đọc thật mất tới ~1,7s, làm
        # toàn bộ câu sau đó bị dồn sớm hơn thực tế gần 1 giây.
        speak_weight = max(1.0, float(_estimate_number_syllables(word)))
    else:
        speak_weight = 1.0 + max(0, len(word) - 6) * 0.15
    stripped = word.rstrip("\"'”’)]»")
    pause_weight = 0.0
    if stripped.endswith("...") or stripped.endswith("…"):
        pause_weight = 1.4  # ngừng dài nhất — bỏ lửng câu
    elif stripped.endswith((".", "!", "?")):
        pause_weight = 1.1  # ngừng hết câu
    elif stripped.endswith((",", ";", ":")):
        # Đo thực tế (silencedetect trên audio thật): quãng ngừng sau dấu phẩy giữa câu ~0.35s,
        # xấp xỉ 1 từ trọn vẹn chứ không phải 0,6 — nâng lên cho khớp, tránh dồn từ sau dấu phẩy
        # sớm hơn thực tế.
        pause_weight = 1.0
    return speak_weight, pause_weight


# ============================================================
# ENGINE 1: EDGE-TTS (Microsoft)
# ============================================================

async def _generate_edge_tts(text: str, output_audio: str, output_srt: str, rate: str, voice: str):
    """Sinh audio + subtitle bằng edge-tts."""
    voice_id = EDGE_VOICES.get(voice.lower(), voice)
    logger.info(f"  [TTS] Engine: edge-tts")
    logger.info(f"  [TTS] Voice: {voice_id} | Rate: {rate}")

    communicate = edge_tts.Communicate(text, voice_id, rate=rate)
    submaker = edge_tts.SubMaker()

    word_boundaries = []
    sentence_boundaries = []

    with open(output_audio, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)
                word_boundaries.append({
                    "text": chunk["text"],
                    "offset": chunk["offset"],
                    "duration": chunk["duration"]
                })
            elif chunk["type"] == "SentenceBoundary":
                submaker.feed(chunk)
                sentence_boundaries.append({
                    "text": chunk["text"],
                    "offset": chunk["offset"],
                    "duration": chunk["duration"]
                })
            else:
                # Feed WordBoundary và SentenceBoundary cho SubMaker
                submaker.feed(chunk)

    # Nếu không có WordBoundary (do giọng không hỗ trợ), ta nội suy (interpolate) từ SentenceBoundary.
    # Dùng trọng số nói gần-đều + trọng số ngừng sau dấu câu (_word_speak_and_pause_weight) thay vì
    # chia thẳng theo tỉ lệ ký tự — cách cũ làm highlight từ lệch khỏi nhịp giọng đọc thật, và các
    # từ sau dấu câu bị nhảy sub sớm hơn lúc giọng đọc thật sự nói tới.
    if not word_boundaries and sentence_boundaries:
        logger.info("  [TTS] WordBoundary not supported by this voice. Interpolating word timings...")
        for sb in sentence_boundaries:
            s_text = sb["text"]
            s_offset = sb["offset"]
            s_duration = sb["duration"]

            words_in_sentence = s_text.split()
            if not words_in_sentence:
                continue
            speak_weights, pause_weights = zip(*(_word_speak_and_pause_weight(w) for w in words_in_sentence))
            total_weight = sum(speak_weights) + sum(pause_weights) or 1
            unit = s_duration / total_weight
            current_offset = s_offset
            for w, speak_w, pause_w in zip(words_in_sentence, speak_weights, pause_weights):
                w_duration = int(speak_w * unit)

                word_boundaries.append({
                    "text": w,
                    "offset": current_offset,
                    "duration": w_duration
                })
                current_offset += w_duration + int(pause_w * unit)

    # Xuất file JSON chứa chi tiết từng từ
    words_data = _build_words_json(word_boundaries)
    words_json_path = output_srt.replace(".srt", "_words.json")
    with open(words_json_path, "w", encoding="utf-8") as f:
        json.dump(words_data, f, ensure_ascii=False, indent=2)

    # Xuất file SRT (SubRip format)
    # Tự sinh SRT từ words_data bằng _words_to_srt để tránh bị rỗng đối với tiếng Việt (do không có WordBoundary từ API)
    srt_content = _words_to_srt(words_data, words_per_group=5)
    with open(output_srt, "w", encoding="utf-8") as srt_file:
        srt_file.write(srt_content)

    return words_data


# ============================================================
# ENGINE 2: GOOGLE CLOUD TTS
# ============================================================

def _edge_rate_to_google_speed(rate: str) -> float:
    """Đổi '+50%' của edge-tts sang speakingRate của Google (1.0 = bình thường, dải 0.25-4.0)."""
    try:
        pct = float(str(rate).replace("%", "").strip())
    except (TypeError, ValueError):
        pct = 0.0
    return max(0.25, min(4.0, 1.0 + pct / 100.0))


def list_google_voices() -> list:
    """Lấy danh sách giọng tiếng Việt THẬT từ Google API (tên giọng thay đổi theo thời gian)."""
    api_key = os.getenv("GOOGLE_TTS_API_KEY")
    if not api_key:
        raise ValueError("Chưa cấu hình GOOGLE_TTS_API_KEY trong .env")
    r = requests.get(
        f"https://texttospeech.googleapis.com/v1/voices?languageCode=vi-VN&key={api_key}",
        timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"Google TTS lỗi khi lấy danh sách giọng: HTTP {r.status_code} - {r.text[:200]}")
    return r.json().get("voices", [])


def _generate_google_tts(text: str, output_audio: str, output_srt: str, rate: str, voice: str):
    """Sinh audio bằng Google Cloud TTS (REST + API key)."""
    import base64

    api_key = os.getenv("GOOGLE_TTS_API_KEY")
    if not api_key:
        raise ValueError(
            "❌ Chưa cấu hình GOOGLE_TTS_API_KEY!\n"
            "   Thêm vào .env: GOOGLE_TTS_API_KEY=your_key\n"
            "   Lấy key: console.cloud.google.com -> bật Cloud Text-to-Speech API -> Credentials."
        )

    info = GOOGLE_VOICES.get(voice.lower())
    voice_id = info["id"] if info else voice   # cho phép truyền thẳng tên giọng Google
    logger.info(f"  [TTS] Engine: Google Cloud TTS | Voice: {voice_id}")

    payload = {
        "input": {"text": text},
        "voice": {"languageCode": "vi-VN", "name": voice_id},
        "audioConfig": {"audioEncoding": "MP3", "speakingRate": _edge_rate_to_google_speed(rate)},
    }
    r = requests.post(
        f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}",
        json=payload, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Google TTS API error: HTTP {r.status_code} - {r.text[:300]}")

    audio_b64 = r.json().get("audioContent")
    if not audio_b64:
        raise RuntimeError(f"Google TTS không trả về audio. Phản hồi: {str(r.json())[:200]}")
    with open(output_audio, "wb") as f:
        f.write(base64.b64decode(audio_b64))

    # Google chỉ trả audio, không có mốc thời gian từng từ -> nội suy từ độ dài audio thật
    # (_interpolate_word_timing_from_audio, dùng trọng số âm tiết đã hiệu chỉnh — xem
    # _word_speak_and_pause_weight).
    words_data = _interpolate_word_timing_from_audio(text, output_audio)
    with open(output_srt, "w", encoding="utf-8") as f:
        f.write(_words_to_srt(words_data))
    with open(output_srt.replace(".srt", "_words.json"), "w", encoding="utf-8") as f:
        json.dump(words_data, f, ensure_ascii=False, indent=2)
    return words_data


# ============================================================
# UTILITY: Word Timing & SRT Generation
# ============================================================

def _get_audio_duration(audio_path: str) -> float:
    """Lấy thời lượng audio bằng mutagen hoặc ffprobe."""
    # Thử dùng ffprobe (có sẵn nếu đã cài ffmpeg)
    try:
        import subprocess
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True, timeout=10
        )
        duration = float(result.stdout.strip())
        return duration
    except Exception:
        pass

    # Fallback: ước tính từ file size (MP3 128kbps)
    file_size = os.path.getsize(audio_path)
    estimated_duration = file_size / (128 * 1024 / 8)  # 128kbps
    logger.info(f"  [TTS] ⚠️ Ước tính thời lượng audio từ file size: {estimated_duration:.1f}s")
    return estimated_duration


def _interpolate_word_timing_from_audio(text: str, audio_path: str) -> list:
    """
    Nội suy word timing từ thời lượng audio.

    Dùng trọng số nói gần-đều + trọng số ngừng sau dấu câu (_word_speak_and_pause_weight)
    thay vì chia thẳng theo tỉ lệ ký tự, để highlight từ bám sát nhịp giọng đọc thật hơn —
    và không bị nhảy sang từ kế tiếp trước khi giọng đọc thật sự nói tới sau mỗi dấu câu.
    """
    duration = _get_audio_duration(audio_path)
    words = text.split()

    if not words:
        return []

    speak_weights, pause_weights = zip(*(_word_speak_and_pause_weight(w) for w in words))
    total_weight = sum(speak_weights) + sum(pause_weights)
    if total_weight == 0:
        return []
    unit = duration / total_weight

    words_data = []
    current_time = 0.0

    for word, speak_w, pause_w in zip(words, speak_weights, pause_weights):
        word_duration = speak_w * unit
        words_data.append({
            "text": word,
            "start": round(current_time, 3),
            "end": round(current_time + word_duration, 3),
        })
        current_time += word_duration + pause_w * unit

    return words_data


def _words_to_srt(words_data: list, words_per_group: int = 5) -> str:
    """Chuyển đổi word timing thành định dạng SRT (nhóm 5 từ/dòng)."""
    if not words_data:
        return ""

    srt_lines = []
    idx = 1

    for i in range(0, len(words_data), words_per_group):
        group = words_data[i:i + words_per_group]
        start_time = group[0]["start"]
        end_time = group[-1]["end"]
        text = " ".join(w["text"] for w in group)

        srt_lines.append(str(idx))
        srt_lines.append(f"{_seconds_to_srt_time(start_time)} --> {_seconds_to_srt_time(end_time)}")
        srt_lines.append(text)
        srt_lines.append("")
        idx += 1

    return "\n".join(srt_lines)


def _seconds_to_srt_time(seconds: float) -> str:
    """Chuyển giây thành định dạng SRT (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _build_words_json(word_boundaries: list) -> list:
    """Chuyển word boundaries (edge-tts format) thành words_data JSON."""
    words_data = []
    for wb in word_boundaries:
        start_sec = wb["offset"] / 10000000.0
        end_sec = start_sec + (wb["duration"] / 10000000.0)
        words_data.append({
            "text": wb["text"],
            "start": start_sec,
            "end": end_sec
        })
    return words_data


def _audio_duration(path: str) -> float:
    """Đọc độ dài (giây) của file audio. Trả 0.0 nếu không đọc được."""
    try:
        return float(_get_audio_duration(path) or 0.0)
    except Exception as e:
        logger.info(f"  [TTS] ⚠️ Không đọc được độ dài audio {path}: {e}")
        return 0.0


def _rescale_timing(output_srt: str, scale: float):
    """Nhân (rescale) toàn bộ timestamp trong SRT + words.json theo hệ số scale.

    Dùng cho TikTok TTS: timing gốc lấy từ Edge-TTS (tốc độ đọc khác TikTok), rescale
    để khớp đúng độ dài audio TikTok thật → phụ đề không bị lệch dồn về cuối video.
    """
    if scale <= 0 or abs(scale - 1.0) < 1e-3:
        return

    # words.json
    words_json_path = output_srt.replace(".srt", "_words.json")
    if os.path.exists(words_json_path):
        try:
            with open(words_json_path, "r", encoding="utf-8") as f:
                words = json.load(f)
            for w in words:
                w["start"] = round(w.get("start", 0.0) * scale, 4)
                w["end"] = round(w.get("end", 0.0) * scale, 4)
            with open(words_json_path, "w", encoding="utf-8") as f:
                json.dump(words, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.info(f"  [TTS] ⚠️ Không rescale được words.json: {e}")

    # SRT (định dạng HH:MM:SS,mmm)
    if os.path.exists(output_srt):
        try:
            import re

            def _ts_to_sec(ts):
                h, m, rest = ts.split(":")
                s, ms = rest.split(",")
                return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

            def _sec_to_ts(sec):
                ms = int(round(sec * 1000))
                h, ms = divmod(ms, 3600000)
                m, ms = divmod(ms, 60000)
                s, ms = divmod(ms, 1000)
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

            with open(output_srt, "r", encoding="utf-8") as f:
                content = f.read()

            def _repl(match):
                a, b = match.group(1), match.group(2)
                return f"{_sec_to_ts(_ts_to_sec(a) * scale)} --> {_sec_to_ts(_ts_to_sec(b) * scale)}"

            content = re.sub(
                r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})",
                _repl, content,
            )
            with open(output_srt, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.info(f"  [TTS] ⚠️ Không rescale được SRT: {e}")


def _build_timing_from_chunks(chunk_durations: list, output_srt: str):
    """Dựng SRT + words.json từ độ dài audio TikTok thật của từng chunk.

    Mỗi chunk thành 1 block phụ đề; thời lượng chunk chia cho các từ theo độ dài ký tự.
    Vì timing lấy thẳng từ audio TikTok nên phụ đề khớp chính xác (kể cả chỗ ngắt nghỉ),
    không lệch như khi mượn timing của Edge.
    """
    import re as _re

    words_data = []
    srt_lines = []
    t = 0.0
    idx = 1
    for chunk_text, dur in chunk_durations:
        dur = max(0.0, float(dur))
        tokens = chunk_text.split()
        if dur <= 0 or not tokens:
            t += dur
            continue

        # TikTok TTS chỉ tách chunk tại dấu KẾT CÂU (.!?) và tự chèn silence đo thật giữa các
        # chunk — nhưng dấu phẩy/chấm phẩy giữa câu, hoặc trường hợp nhiều câu ngắn gộp chung 1
        # chunk (dưới MAX_CHUNK ký tự), thì bên trong 1 chunk vẫn cần trọng số ngừng sau dấu câu
        # (_word_speak_and_pause_weight) — nếu không, các từ sau dấu câu bị nhảy sub sớm hơn lúc
        # giọng đọc thật sự nói tới, và lệch cộng dồn tăng dần theo số dấu câu trong chunk.
        speak_weights, pause_weights = zip(*(_word_speak_and_pause_weight(w) for w in tokens))
        total_weight = sum(speak_weights) + sum(pause_weights) or 1
        unit = dur / total_weight
        block_start = t
        wt = t
        for w, speak_w, pause_w in zip(tokens, speak_weights, pause_weights):
            w_dur = speak_w * unit
            words_data.append({"text": w, "start": round(wt, 4), "end": round(wt + w_dur, 4)})
            wt += w_dur + pause_w * unit
        block_end = t + dur

        srt_lines.append(str(idx))
        srt_lines.append(f"{_seconds_to_srt_time(block_start)} --> {_seconds_to_srt_time(block_end)}")
        srt_lines.append(chunk_text.strip())
        srt_lines.append("")
        idx += 1
        t += dur

    with open(output_srt, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))

    words_json_path = output_srt.replace(".srt", "_words.json")
    with open(words_json_path, "w", encoding="utf-8") as f:
        json.dump(words_data, f, ensure_ascii=False, indent=2)


async def _generate_tiktok_api(text: str, output_audio: str, output_srt: str, rate: str, voice: str):
    """Sinh audio bằng TikTok TTS + phụ đề khớp đúng audio (theo độ dài từng chunk)."""
    from core.engines import tiktok_tts
    logger.info(f"  [TTS] Engine: TikTok TTS API")

    # 1. Sinh audio TikTok, nhận về độ dài thật từng chunk
    chunk_durations = tiktok_tts.generate_tiktok_tts(text, voice, output_audio)

    # 2. Dựng phụ đề thẳng từ độ dài audio TikTok (chính xác nhất, không cần Edge)
    summed_dur = sum(d for _, d in chunk_durations) if chunk_durations else 0.0
    if chunk_durations and summed_dur > 0:
        # Chống drift: tổng duration đo từng chunk lệch với duration file gộp
        # (MP3 frame padding tích lũy) → scale lại toàn bộ timing theo file thật.
        real_dur = _audio_duration(output_audio)
        if real_dur > 0 and abs(real_dur - summed_dur) > 0.05:
            scale = real_dur / summed_dur
            logger.info(f"  [TTS] Hiệu chỉnh drift phụ đề: {summed_dur:.2f}s (cộng dồn) → {real_dur:.2f}s (thật), scale={scale:.4f}")
            chunk_durations = [(txt, d * scale) for txt, d in chunk_durations]
        logger.info(f"  [TTS] Sync phụ đề theo {len(chunk_durations)} chunk audio TikTok thật.")
        _build_timing_from_chunks(chunk_durations, output_srt)
        return

    # 3. Fallback: nếu không đo được chunk (vd lỗi đọc mp3) → mượn timing Edge rồi rescale
    logger.info("  [TTS] Không đo được chunk, fallback Edge timing + rescale.")
    temp_audio = output_audio.replace(".mp3", "_temp.mp3")
    await _generate_edge_tts(text, temp_audio, output_srt, rate, "hoaimy")
    real_dur = _audio_duration(output_audio)
    edge_dur = _audio_duration(temp_audio)
    if real_dur > 0 and edge_dur > 0:
        _rescale_timing(output_srt, real_dur / edge_dur)
    if os.path.exists(temp_audio):
        os.remove(temp_audio)


# ============================================================
# MAIN ENTRY POINT
# ============================================================

async def generate_tts(text_file: str = None, output_audio: str = "temp/audio.mp3", output_srt: str = "temp/subtitles.srt", rate: str = "+50%", voice: str = "hoaimy", raw_text_input: str = None):
    """
    Đọc file kịch bản hoặc nhận text trực tiếp, sinh ra audio MP3 và subtitle SRT.

    Args:
        text_file: Đường dẫn tới file kịch bản (.txt)
        output_audio: Đường dẫn file audio đầu ra (.mp3)
        output_srt: Đường dẫn file subtitle đầu ra (.srt)
        rate: Tốc độ đọc. Ví dụ: "+0%" (bình thường), "+20%" (nhanh hơn 20%),
              "-15%" (chậm hơn 15%), "+50%" (nhanh gấp rưỡi).
        voice: Tên giọng đọc. Xem danh sách bằng --list-voices.
        raw_text_input: Nội dung text trực tiếp (nếu truyền thì bỏ qua text_file).
    """
    if raw_text_input:
        raw_text = raw_text_input
    else:
        if not text_file or not os.path.exists(text_file):
            raise FileNotFoundError(f"Cannot find script file: {text_file}")
        with open(text_file, "r", encoding="utf-8") as f:
            raw_text = f.read()

    # Parse kịch bản: tách lời đọc, bỏ chú thích
    text = parse_script(raw_text)

    if not text:
        raise ValueError("Script is empty after parsing!")

    logger.info(f"  [TTS] Clean script: {text[:100]}...")
    logger.info(f"  [TTS] Ký tự: {len(text)} chars")

    # Đảm bảo thư mục tồn tại
    for path in [output_audio, output_srt]:
        dirpath = os.path.dirname(path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)

    # Chọn engine dựa trên tên giọng
    engine = get_engine(voice)

    # KHÔNG fallback sang giọng khác khi lỗi. Đã thử cách đó và nó gây hiểu nhầm: trước đây FPT
    # bị 429 thì `leminh` âm thầm thành `namminh`, người dùng chọn 2 giọng khác nhau lại nghe y
    # hệt mà không biết vì sao. Thà hỏng job và báo rõ còn hơn ra sản phẩm sai giọng.
    if engine == "edge":
        voice_id = EDGE_VOICES.get(voice.lower(), voice)
        await _generate_edge_tts(text, output_audio, output_srt, rate, voice_id)
    elif engine == "google":
        _generate_google_tts(text, output_audio, output_srt, rate, voice)
    elif engine == "tiktok":
        await _generate_tiktok_api(text, output_audio, output_srt, rate, voice)

    logger.info(f"  [TTS] ✅ Audio saved: {output_audio}")
    logger.info(f"  [TTS] ✅ Subtitles saved: {output_srt}")
    words_json_path = output_srt.replace(".srt", "_words.json")
    logger.info(f"  [TTS] ✅ Word timing saved: {words_json_path}")
    return voice


def run_tts(text_file: str = None, output_audio: str = "temp/audio.mp3", output_srt: str = "temp/subtitles.srt", rate: str = "+50%", voice: str = "hoaimy", raw_text_input: str = None):
    """Wrapper đồng bộ cho generate_tts.

    Trả về `voice` y nguyên (KHÔNG fallback/đổi giọng khi lỗi — lỗi thì raise thẳng, xem
    generate_tts). Giữ giá trị trả về (thay vì None) để tương thích ngược với code gọi hàm này
    và lấy tên giọng đã dùng (vd app.py::run_pipeline).
    """
    return asyncio.run(generate_tts(text_file, output_audio, output_srt, rate=rate, voice=voice, raw_text_input=raw_text_input))


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--list-google":
        for v in list_google_voices():
            print(f"  {v['name']:34s} {v.get('ssmlGender',''):8s} {v.get('naturalSampleRateHertz','')}Hz")
    elif len(sys.argv) > 1 and sys.argv[1] == "--list-voices":
        list_voices()
    else:
        voice = sys.argv[2] if len(sys.argv) > 2 else "hoaimy"
        run_tts("script.txt", "temp/audio.mp3", "temp/subtitles.srt", voice=voice)
