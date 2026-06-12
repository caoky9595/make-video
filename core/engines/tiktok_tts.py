import requests
import base64
import os
import re
from dotenv import load_dotenv
from core.utils.logger_config import logger
load_dotenv()


def _save_session_to_env(session_id: str):
    """Cập nhật TIKTOK_SESSION_ID trong bộ nhớ tiến trình hiện tại.
    Không ghi vào .env (tránh race condition khi nhiều thread cùng login).
    Session đã được lưu vào tiktok_session.txt bởi login_and_get_tiktok_session().
    """
    os.environ["TIKTOK_SESSION_ID"] = session_id


def _get_silent_mp3_bytes(duration: float) -> bytes:
    """Tạo bytes im lặng (silence) định dạng MP3 bằng FFmpeg."""
    import subprocess
    import shutil
    
    # Tìm file ffmpeg
    ff = shutil.which("ffmpeg")
    if not ff:
        try:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            pass
            
    if not ff:
        # Fallback nếu không có ffmpeg: trả về chuỗi rỗng
        return b""
        
    cmd = [
        ff, "-y",
        "-f", "lavfi", "-i", "anullsrc=r=24000:c=1",
        "-t", str(duration),
        "-f", "mp3", "-"
    ]
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        out, _ = process.communicate()
        return out
    except Exception as e:
        logger.error(f"  [TTS] ⚠️ Không thể tạo silent MP3 bytes bằng FFmpeg: {e}")
        return b""


def _playwright_login_worker(result: list, error: list):
    """Chạy trong thread riêng để tránh xung đột với asyncio event loop."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        error.append(RuntimeError(
            "Thiếu thư viện playwright. Chạy: pip install playwright && playwright install chromium"
        ))
        return

    session_id = None
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        page.goto("https://www.tiktok.com/login")

        for _ in range(90):  # tối đa 3 phút
            cookies = context.cookies("https://www.tiktok.com")
            for c in cookies:
                if c["name"] == "sessionid" and c.get("value"):
                    session_id = c["value"]
                    break
            if session_id:
                break
            page.wait_for_timeout(2000)

        browser.close()

    result.append(session_id)


def login_and_get_tiktok_session() -> str:
    """
    Mở trình duyệt TikTok cho user đăng nhập, tự động bắt cookie sessionid.
    Lưu vào .env và tiktok_session.txt rồi trả về session_id.
    Chạy playwright trong thread riêng để tương thích với asyncio event loop.
    """
    import threading

    logger.info("  [TikTok] Mở trình duyệt để đăng nhập TikTok...")
    logger.info("  [TikTok] Hãy đăng nhập vào TikTok trong cửa sổ trình duyệt vừa mở.")
    logger.info("  [TikTok] Session sẽ được tự động lưu sau khi đăng nhập thành công.")

    result, error = [], []
    t = threading.Thread(target=_playwright_login_worker, args=(result, error), daemon=True)
    t.start()
    t.join(timeout=200)

    if error:
        raise error[0]

    session_id = result[0] if result else None
    if not session_id:
        raise TimeoutError(
            "Không bắt được session TikTok sau 3 phút. Hãy thử lại hoặc điền thủ công vào .env."
        )

    session_file = os.path.join(os.path.dirname(__file__), "tiktok_session.txt")
    with open(session_file, "w", encoding="utf-8") as f:
        f.write(session_id)

    _save_session_to_env(session_id)  # cập nhật os.environ cho phiên hiện tại
    logger.info("  [TikTok] ✅ Đăng nhập thành công! Session đã được lưu vào tiktok_session.txt.")
    return session_id

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


def _load_session() -> str:
    """Đọc session từ file local, rồi fallback sang .env."""
    session_file = os.path.join(os.path.dirname(__file__), "tiktok_session.txt")
    if os.path.exists(session_file):
        val = open(session_file, "r", encoding="utf-8").read().strip()
        if val:
            return val
    return os.getenv("TIKTOK_SESSION_ID", "")


def generate_tiktok_tts(text: str, voice: str, output_file: str):
    """
    Gọi TikTok TTS API không chính thức để lấy file MP3.
    Hỗ trợ kịch bản siêu dài bằng cách tự động chia nhỏ text.

    Trả về danh sách [(chunk_text, duration_giây), ...] theo từng đoạn đã đọc,
    dùng để dựng phụ đề khớp chính xác với audio TikTok.
    """
    voice_code = TIKTOK_VOICES.get(voice, "BV074_streaming")
    
    session_id = _load_session()
    if not session_id:
        logger.warning("  [TikTok TTS] Chưa có session — mở trình duyệt để đăng nhập...")
        session_id = login_and_get_tiktok_session()

    import time
    
    # Giới hạn ký tự/chunk: 150 chars đủ cho 1 câu tiếng Việt hoàn chỉnh mà
    # không vượt quá giới hạn URL của TikTok API (~450 bytes UTF-8).
    MAX_CHUNK = 150

    def split_by_length(text_part, max_len=MAX_CHUNK):
        """Split by word boundary, không bao giờ cắt giữa chừng."""
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

    # Chỉ tách tại dấu câu KẾT THÚC CÂU (.!?\n) — KHÔNG tách tại dấu phẩy/chấm phẩy.
    # Tách tại dấu phẩy sẽ khiến TikTok đọc mỗi fragment với ngữ điệu riêng,
    # tạo ra cảm giác ngập ngừng khi ghép lại.
    sentences = re.split(r'([.!?\n]+)', text)
    chunks = []
    current_chunk = ""
    for piece in sentences:
        if len(current_chunk) + len(piece) > MAX_CHUNK:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            if len(piece) > MAX_CHUNK:
                sub_pieces = split_by_length(piece, MAX_CHUNK)
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

    # Silence ngắn giữa các câu kết thúc (.) — không chèn giữa các chunk mid-sentence
    silence_bytes = _get_silent_mp3_bytes(0.3)

    session_refreshed = False  # Chỉ cho phép re-login tối đa 1 lần/job

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
        response = None
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
            
        seg = None
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
                else:
                    raise Exception(f"Phản hồi thành công nhưng v_str trống ở đoạn {idx+1}.")
            else:
                # Session hết hạn → thử login lại 1 lần
                session_expired = status_code in (4, 10) or any(
                    kw in (status_msg or "").lower()
                    for kw in ("session", "login", "auth", "token", "unauthorized", "invalid user")
                )
                if session_expired and not session_refreshed:
                    logger.warning(f"  [TikTok TTS] Session hết hạn ở đoạn {idx+1} (mã {status_code}) — mở trình duyệt để đăng nhập lại...")
                    session_id = login_and_get_tiktok_session()
                    headers["Cookie"] = f"sessionid={session_id}"
                    session_refreshed = True
                    # Retry chunk này với session mới
                    response = requests.post(url, headers=headers, params=params, timeout=15)
                    data = response.json()
                    status_code = data.get("status_code")
                    if status_code == 0:
                        vstr = data.get("data", {}).get("v_str")
                        if vstr:
                            seg = base64.b64decode(vstr)
                if not seg:
                    raise Exception(f"TikTok API báo lỗi ở đoạn {idx+1}: {status_msg} (Mã lỗi: {status_code}).")
        else:
            raise Exception(f"TikTok TTS API trả về HTTP code {response.status_code} ở đoạn {idx+1}: {response.text}")
            
        if seg:
            all_audio_bytes += seg
            chunk_dur = _mp3_bytes_duration(seg)
            chunk_durations.append((chunk, chunk_dur))
            
            # Chèn silence 0.3s chỉ khi chunk này kết thúc câu (.!?)
            # Mid-sentence chunks (kết thúc bằng chữ) không cần khoảng ngắt.
            ends_sentence = bool(re.search(r'[.!?]\s*$', chunk))
            has_next_valid_chunk = any(
                c.strip() and re.search(r'\w', c) for c in chunks[idx+1:]
            )
            if ends_sentence and has_next_valid_chunk and silence_bytes:
                all_audio_bytes += silence_bytes
                chunk_durations.append(("", 0.3))
            
        if idx < len(chunks) - 1:
            time.sleep(0.5) # Tránh bị rate limit
            
    with open(output_file, "wb") as f:
        f.write(all_audio_bytes)

    return chunk_durations
