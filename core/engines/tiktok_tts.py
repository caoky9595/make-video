import requests
import base64
import os
from dotenv import load_dotenv
from core.utils.logger_config import logger
load_dotenv()

TIKTOK_VOICES = {
    # Nữ
    "tiktok_nu_1": "BV074_streaming", # Giọng nữ ấm áp (thay thế vi_vn_001)
    "tiktok_nu_2": "BV074_streaming", 
    # Nam
    "tiktok_nam_1": "BV075_streaming", # Giọng nam trầm (thay thế vi_vn_003)
    "tiktok_nam_2": "BV075_streaming", 
}

def _mp3_bytes_duration(seg_bytes: bytes) -> float:
    """Đo độ dài (giây) của một đoạn mp3 từ bytes. Trả 0.0 nếu lỗi."""
    import tempfile
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(seg_bytes)
            tmp = f.name
        from moviepy.editor import AudioFileClip
        clip = AudioFileClip(tmp)
        try:
            return float(clip.duration or 0.0)
        finally:
            clip.close()
    except Exception:
        return 0.0
    finally:
        if tmp and os.path.exists(tmp):
            try: os.remove(tmp)
            except OSError: pass


def generate_tiktok_tts(text: str, voice: str, output_file: str):
    """
    Gọi TikTok TTS API không chính thức để lấy file MP3.
    Hỗ trợ kịch bản siêu dài bằng cách tự động chia nhỏ text.

    Trả về danh sách [(chunk_text, duration_giây), ...] theo từng đoạn đã đọc,
    dùng để dựng phụ đề khớp chính xác với audio TikTok.
    """
    voice_code = TIKTOK_VOICES.get(voice, "BV074_streaming")
    
    session_id = ""
    session_file = os.path.join(os.path.dirname(__file__), "tiktok_session.txt")
    if os.path.exists(session_file):
        with open(session_file, "r", encoding="utf-8") as f:
            session_id = f.read().strip()
            
    if not session_id:
        session_id = os.getenv("TIKTOK_SESSION_ID", "")
        
    if not session_id:
        raise Exception(
            "Chưa cấu hình TIKTOK_SESSION_ID. Cách lấy: đăng nhập tiktok.com trên trình duyệt "
            "→ mở DevTools (F12) → Application → Cookies → copy giá trị 'sessionid' → "
            "dán vào file .env dạng TIKTOK_SESSION_ID=xxxxx (hoặc giọng dự phòng FPT 'banmai')."
        )

    import re
    import time
    
    def split_by_length(text_part, max_len=50):
        """Split by length."""
        words = text_part.split(' ')
        parts = []
        curr = ""
        for w in words:
            if len(w) > max_len:
                if curr:
                    parts.append(curr.strip())
                    curr = ""
                for i in range(0, len(w), max_len):
                    parts.append(w[i:i+max_len])
                continue

            if len(curr) + len(w) + 1 > max_len:
                if curr:
                    parts.append(curr.strip())
                curr = w
            else:
                curr += " " + w if curr else w
        if curr:
            parts.append(curr.strip())
        return parts

    # Tách câu dựa trên dấu câu để không làm đứt giữa chừng
    sentences = re.split(r'([.,;!?\n]+)', text)
    chunks = []
    current_chunk = ""
    for piece in sentences:
        if len(current_chunk) + len(piece) > 50:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            
            if len(piece) > 50:
                sub_pieces = split_by_length(piece, 50)
                if sub_pieces:
                    for sp in sub_pieces[:-1]:
                        chunks.append(sp)
                    current_chunk = sub_pieces[-1]
                else:
                    current_chunk = ""
            else:
                current_chunk = piece
        else:
            current_chunk += piece
            
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
        
    url = "https://api16-normal-v6.tiktokv.com/media/api/text/speech/invoke/"
    headers = {
        "User-Agent": "com.zhiliaoapp.musically/2022600030 (Linux; U; Android 7.1.2; vi_VN; SM-G988N; Build/NRD90M;tt-ok/3.12.13.1)",
        "Cookie": f"sessionid={session_id}"
    }
    
    all_audio_bytes = b""
    chunk_durations = []  # [(chunk_text, duration_giây), ...] để dựng phụ đề khớp audio

    for idx, chunk in enumerate(chunks):
        chunk = chunk.strip()
        if not chunk: continue
        
        # Bỏ qua các chunk chỉ chứa dấu câu/khoảng trắng (sẽ làm TikTok báo lỗi mã 1)
        if not re.search(r'\w', chunk):
            logger.info(f"  [TikTok TTS] Skipping chunk {idx+1}/{len(chunks)}: '{chunk}' (no readable words)")
            continue
            
        # TikTok TTS seems to throw random errors for text encoding issues.
        # We safely pass it as params so the requests library handles url encoding securely.
        req_text = chunk.replace("+", "plus")
        
        params = {
            "text_speaker": voice_code,
            "req_text": req_text,
            "speaker_map_type": 0,
            "aid": 1233
        }
        
        logger.info(f"  [TikTok TTS] Sending chunk {idx+1}/{len(chunks)}: length={len(chunk)} chars")
        
        max_retries = 3
        retry_delay = 2
        for attempt in range(max_retries):
            try:
                # Tăng timeout lên 15s để tránh Request Timeout
                response = requests.post(url, headers=headers, params=params, timeout=15)
                if response.status_code >= 500:
                    if attempt < max_retries - 1:
                        logger.info(f"  [TikTok TTS] ⚠️ Server quá tải (HTTP {response.status_code}), thử lại lần {attempt+1}/{max_retries}...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        raise Exception(f"TikTok TTS API trả về HTTP code {response.status_code} ở đoạn {idx+1} sau {max_retries} lần thử.")
                break # Status code < 500 (Thành công hoặc lỗi 4xx)
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.info(f"  [TikTok TTS] ⚠️ Kết nối lỗi ({type(e).__name__}), thử lại lần {attempt+1}/{max_retries}...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    raise Exception(f"Kết nối tới TikTok TTS API thất bại ở đoạn {idx+1} sau {max_retries} lần thử: {e}")
            
        if response.status_code == 200:
            try:
                data = response.json()
            except Exception as e:
                raise Exception(f"Không thể parse JSON từ phản hồi TikTok (Đoạn {idx+1}): {response.text}")
                
            status_code = data.get("status_code")
            status_msg = data.get("status_msg") or data.get("message") or "Lỗi không xác định"
            
            if status_code == 0:
                vstr = data.get("data", {}).get("v_str")
                if vstr:
                    seg = base64.b64decode(vstr)
                    all_audio_bytes += seg
                    chunk_durations.append((chunk, _mp3_bytes_duration(seg)))
                else:
                    raise Exception(f"Phản hồi thành công nhưng v_str trống ở đoạn {idx+1}.")
            else:
                raise Exception(f"TikTok API báo lỗi ở đoạn {idx+1}: {status_msg} (Mã lỗi: {status_code}). Vui lòng kiểm tra lại TIKTOK_SESSION_ID.")
        else:
            raise Exception(f"TikTok TTS API trả về HTTP code {response.status_code} ở đoạn {idx+1}: {response.text}")
            
        if idx < len(chunks) - 1:
            time.sleep(0.5) # Tránh bị rate limit
            
    with open(output_file, "wb") as f:
        f.write(all_audio_bytes)

    return chunk_durations
