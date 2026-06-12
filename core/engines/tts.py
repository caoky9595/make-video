"""
tts.py - Text-to-Speech Engine (edge-tts + FPT.AI)
====================================================
Chuyển đổi kịch bản text thành file audio MP3 + file subtitle SRT.

Hỗ trợ 2 engine:
  - edge-tts: Miễn phí, không giới hạn, 2 giọng Việt (HoaiMy, NamMinh)
  - FPT.AI:   Miễn phí 100k ký tự/tháng, 7 giọng Việt đa vùng miền
"""

import asyncio
import json
import os
import re
import time

import edge_tts
import requests
from dotenv import load_dotenv
from core.utils.logger_config import logger

load_dotenv()

# ============================================================
# DANH SÁCH GIỌNG ĐỌC
# ============================================================

# Edge-TTS voices (Microsoft)
EDGE_VOICES = {
    "hoaimy":  "vi-VN-HoaiMyNeural",     # Nữ - giọng nữ trẻ, tự nhiên
    "namminh": "vi-VN-NamMinhNeural",     # Nam - giọng nam trầm, chuyên nghiệp
}

# FPT.AI voices
FPT_VOICES = {
    "banmai":   {"id": "banmai",   "gender": "Nữ",  "region": "Bắc",   "desc": "Nữ Bắc - trẻ trung"},
    "thuminh":  {"id": "thuminh",  "gender": "Nữ",  "region": "Bắc",   "desc": "Nữ Bắc - dịu dàng"},
    "leminh":   {"id": "leminh",   "gender": "Nam",  "region": "Bắc",   "desc": "Nam Bắc - trầm ấm"},
    "myan":     {"id": "myan",     "gender": "Nữ",  "region": "Trung",  "desc": "Nữ Trung Bộ"},
    "giahuy":   {"id": "giahuy",   "gender": "Nam",  "region": "Trung",  "desc": "Nam Trung Bộ"},
    "lannhi":   {"id": "lannhi",   "gender": "Nữ",  "region": "Nam",    "desc": "Nữ Nam Bộ"},
    "linhsan":  {"id": "linhsan",  "gender": "Nữ",  "region": "Nam",    "desc": "Nữ Nam - mềm mại"},
}

# TIKTOK TTS voices
TIKTOK_VOICES = {
    "tiktok_nu_1": {"gender": "Nữ", "desc": "Giọng TikTok Nữ Review"},
    "tiktok_nu_2": {"gender": "Nữ", "desc": "Giọng TikTok Nữ Trẻ"},
    "tiktok_nam_1": {"gender": "Nam", "desc": "Giọng TikTok Kể chuyện bí ẩn"},
    "tiktok_nam_2": {"gender": "Nam", "desc": "Giọng TikTok Nam Đọc nhanh"},
}

# Tất cả giọng hợp lệ
ALL_VOICE_KEYS = list(EDGE_VOICES.keys()) + list(FPT_VOICES.keys()) + list(TIKTOK_VOICES.keys())

# Map tốc độ edge-tts (+20%) sang FPT.AI scale (-3 to +3)
EDGE_RATE_TO_FPT_SPEED = {
    "-50%": "-3", "-40%": "-3", "-30%": "-2", "-20%": "-2",
    "-15%": "-1", "-10%": "-1", "+0%": "0", "0%": "0",
    "+10%": "1", "+15%": "1", "+20%": "2", "+25%": "2",
    "+30%": "3", "+40%": "3", "+50%": "3",
}


def get_engine(voice: str) -> str:
    """Xác định engine dựa trên tên giọng đọc."""
    v_lower = voice.lower()
    if v_lower in EDGE_VOICES or voice in EDGE_VOICES.values() or any(v_lower in val.lower() for val in EDGE_VOICES.values()):
        return "edge"
    elif v_lower in FPT_VOICES:
        return "fpt"
    elif v_lower in TIKTOK_VOICES or v_lower.startswith("tiktok_"):
        return "tiktok"
    else:
        raise ValueError(
            f"Giọng '{voice}' không hợp lệ. Các giọng có sẵn:\n"
            f"  FPT.AI:   {', '.join(FPT_VOICES.keys())}\n"
            f"  TikTok:   {', '.join(TIKTOK_VOICES.keys())}"
        )


def list_voices():
    """In danh sách tất cả giọng đọc có sẵn."""
    logger.info("\n📢 DANH SÁCH GIỌNG ĐỌC CÓ SẴN:")
    logger.info("=" * 60)

    logger.info("\n🔶 FPT.AI (miễn phí 100k ký tự/tháng, giọng rất tự nhiên):")
    for key, info in FPT_VOICES.items():
        logger.info(f"   • {key:12s} → {info['gender']} {info['region']:5s} | {info['desc']}")

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

    # Nếu không có WordBoundary (do giọng không hỗ trợ), ta nội suy (interpolate) từ SentenceBoundary
    if not word_boundaries and sentence_boundaries:
        logger.info("  [TTS] WordBoundary not supported by this voice. Interpolating word timings...")
        for sb in sentence_boundaries:
            s_text = sb["text"]
            s_offset = sb["offset"]
            s_duration = sb["duration"]
            s_len = len(s_text)
            
            words_in_sentence = s_text.split()
            current_offset = s_offset
            for w in words_in_sentence:
                w_len = len(w)
                if s_len > 0:
                    w_duration = int(s_duration * (w_len / s_len))
                    space_duration = int(s_duration * (1 / s_len))
                else:
                    w_duration = 0
                    space_duration = 0
                
                word_boundaries.append({
                    "text": w,
                    "offset": current_offset,
                    "duration": w_duration
                })
                current_offset += w_duration + space_duration

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
# ENGINE 2: FPT.AI
# ============================================================

def _edge_rate_to_fpt_speed(rate: str) -> str:
    """Chuyển đổi tốc độ edge-tts sang FPT.AI speed."""
    return EDGE_RATE_TO_FPT_SPEED.get(rate, "0")


def _generate_fpt_tts(text: str, output_audio: str, output_srt: str, rate: str, voice: str):
    """Sinh audio + subtitle bằng FPT.AI API."""
    api_key = os.getenv("FPT_AI_API_KEY")
    if not api_key:
        raise ValueError(
            "❌ FPT_AI_API_KEY chưa được cấu hình!\n"
            "   Thêm vào file .env: FPT_AI_API_KEY=your_key_here\n"
            "   Đăng ký miễn phí tại: https://console.fpt.ai/"
        )

    voice_info = FPT_VOICES[voice.lower()]
    fpt_speed = _edge_rate_to_fpt_speed(rate)

    logger.info(f"  [TTS] Engine: FPT.AI (v5)")
    logger.info(f"  [TTS] Voice: {voice_info['id']} ({voice_info['desc']}) | Speed: {fpt_speed}")

    # Gọi FPT.AI API
    headers = {
        "api-key": api_key,
        "voice": voice_info["id"],
        "speed": fpt_speed,
        "format": "mp3",
    }

    response = requests.post(
        "https://api.fpt.ai/hmi/tts/v5",
        headers=headers,
        data=text.encode("utf-8"),
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(f"FPT.AI API error: HTTP {response.status_code} - {response.text}")

    result = response.json()

    if result.get("error") and result["error"] != 0:
        raise RuntimeError(f"FPT.AI API error: {result.get('message', 'Unknown error')}")

    # FPT.AI trả về async link → cần đợi audio sẵn sàng
    audio_url = result.get("async")
    if not audio_url:
        raise RuntimeError(f"FPT.AI API không trả về audio URL. Response: {result}")

    logger.info(f"  [TTS] Audio đang được xử lý bởi FPT.AI...")

    # Đợi và tải file audio (FPT.AI xử lý async, cần retry)
    max_retries = 20
    for attempt in range(max_retries):
        time.sleep(1.5)  # Đợi 1.5s giữa mỗi lần thử
        try:
            audio_response = requests.get(audio_url, timeout=15)
            if audio_response.status_code == 200 and len(audio_response.content) > 1000:
                with open(output_audio, "wb") as f:
                    f.write(audio_response.content)
                logger.info(f"  [TTS] ✅ Audio tải xong ({len(audio_response.content) / 1024:.1f} KB)")
                break
        except requests.exceptions.RequestException:
            pass

        if attempt == max_retries - 1:
            raise RuntimeError("❌ Timeout: FPT.AI không trả về audio sau 30 giây.")
        
        logger.info(f"  [TTS] Đang đợi FPT.AI xử lý... ({attempt + 1}/{max_retries})")

    # Tạo word timing bằng phương pháp nội suy từ audio duration
    words_data = _interpolate_word_timing_from_audio(text, output_audio)

    # Xuất SRT từ word timing
    srt_content = _words_to_srt(words_data)
    with open(output_srt, "w", encoding="utf-8") as f:
        f.write(srt_content)

    # Xuất JSON word timing
    words_json_path = output_srt.replace(".srt", "_words.json")
    with open(words_json_path, "w", encoding="utf-8") as f:
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
    Chia đều thời gian cho mỗi từ dựa trên độ dài ký tự.
    """
    duration = _get_audio_duration(audio_path)
    words = text.split()
    
    if not words:
        return []

    total_chars = sum(len(w) for w in words)
    if total_chars == 0:
        return []

    words_data = []
    current_time = 0.0

    for word in words:
        word_duration = duration * (len(word) / total_chars)
        words_data.append({
            "text": word,
            "start": round(current_time, 3),
            "end": round(current_time + word_duration, 3),
        })
        current_time += word_duration

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
        from moviepy.editor import AudioFileClip
        clip = AudioFileClip(path)
        try:
            return float(clip.duration or 0.0)
        finally:
            clip.close()
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

        total_chars = sum(len(w) for w in tokens) or 1
        block_start = t
        wt = t
        for w in tokens:
            w_dur = dur * (len(w) / total_chars)
            words_data.append({"text": w, "start": round(wt, 4), "end": round(wt + w_dur, 4)})
            wt += w_dur
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

    if engine == "edge":
        voice_id = EDGE_VOICES.get(voice.lower(), voice)
        await _generate_edge_tts(text, output_audio, output_srt, rate, voice_id)
    elif engine == "tiktok":
        await _generate_tiktok_api(text, output_audio, output_srt, rate, voice)
    elif engine == "fpt":
        _generate_fpt_tts(text, output_audio, output_srt, rate, voice)

    logger.info(f"  [TTS] ✅ Audio saved: {output_audio}")
    logger.info(f"  [TTS] ✅ Subtitles saved: {output_srt}")
    words_json_path = output_srt.replace(".srt", "_words.json")
    logger.info(f"  [TTS] ✅ Word timing saved: {words_json_path}")


def run_tts(text_file: str = None, output_audio: str = "temp/audio.mp3", output_srt: str = "temp/subtitles.srt", rate: str = "+50%", voice: str = "hoaimy", raw_text_input: str = None):
    """Wrapper đồng bộ cho generate_tts."""
    asyncio.run(generate_tts(text_file, output_audio, output_srt, rate=rate, voice=voice, raw_text_input=raw_text_input))


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--list-voices":
        list_voices()
    else:
        voice = sys.argv[2] if len(sys.argv) > 2 else "hoaimy"
        run_tts("script.txt", "temp/audio.mp3", "temp/subtitles.srt", voice=voice)
