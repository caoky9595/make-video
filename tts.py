"""
tts.py - Text-to-Speech Engine (edge-tts)
==========================================
Chuyển đổi kịch bản text thành file audio MP3 + file subtitle SRT.
Sử dụng giọng đọc tiếng Việt nữ HoaiMy từ Microsoft Edge (miễn phí).
"""

import asyncio
import os
import re

import edge_tts

VOICE = "vi-VN-HoaiMyNeural"

# Danh sách giọng đọc tiếng Việt có sẵn
VOICES = {
    "hoaimy": "vi-VN-HoaiMyNeural",    # Nữ - giọng nữ trẻ, tự nhiên
    "namminh": "vi-VN-NamMinhNeural",   # Nam - giọng nam trầm, chuyên nghiệp
}


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
    # Bước 1: Thử trích xuất text trong ngoặc kép "" hoặc ""
    # Nếu kịch bản có ngoặc kép → chỉ lấy phần trong ngoặc kép
    quoted_parts = re.findall(r'["""](.+?)["""]', raw_text)
    
    if quoted_parts:
        # Kịch bản có ngoặc kép → ghép tất cả lời thoại
        clean_text = " ".join(quoted_parts)
        print(f"  [Script Parser] Detected quoted script format → extracted {len(quoted_parts)} dialogue parts")
    else:
        # Kịch bản plain text → xử lý khác
        clean_text = raw_text
        
        # Xóa các mốc thời gian dạng "0s - 3s" hoặc "00:00 - 00:03"
        clean_text = re.sub(r'\d+s?\s*-\s*\d+s?', '', clean_text)
        clean_text = re.sub(r'\d{2}:\d{2}\s*-\s*\d{2}:\d{2}', '', clean_text)
        
        # Xóa các label dạng (Hook): hoặc (Nội dung): hoặc (CTA):
        clean_text = re.sub(r'\([^)]*\)\s*:?\s*', '', clean_text)
        
        # Xóa các chú thích trong ngoặc vuông [Tên miền] → giữ nguyên text bên trong
        clean_text = re.sub(r'\[([^\]]*)\]', r'\1', clean_text)
        
        print(f"  [Script Parser] Detected plain text format → cleaned metadata")
    
    # Bước 2: Dọn dẹp chung
    # Xóa các chú thích trong ngoặc vuông → giữ nội dung bên trong
    clean_text = re.sub(r'\[([^\]]*)\]', r'\1', clean_text)
    
    # Xóa khoảng trắng thừa
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    # Xóa dấu - ở đầu dòng (bullet points)
    clean_text = re.sub(r'^\s*-\s*', '', clean_text, flags=re.MULTILINE)
    
    return clean_text


async def generate_tts(text_file: str, output_audio: str, output_srt: str, rate: str = "+20%", voice: str = "hoaimy"):
    """
    Đọc file kịch bản, sinh ra audio MP3 và subtitle SRT.

    Args:
        text_file: Đường dẫn tới file kịch bản (.txt)
        output_audio: Đường dẫn file audio đầu ra (.mp3)
        output_srt: Đường dẫn file subtitle đầu ra (.srt)
        rate: Tốc độ đọc. Ví dụ: "+0%" (bình thường), "+20%" (nhanh hơn 20%),
              "-15%" (chậm hơn 15%), "+50%" (nhanh gấp rưỡi).
        voice: Tên giọng đọc. "hoaimy" (nữ) hoặc "namminh" (nam).
    """
    if not os.path.exists(text_file):
        raise FileNotFoundError(f"Cannot find script file: {text_file}")

    with open(text_file, "r", encoding="utf-8") as f:
        raw_text = f.read()

    # Parse kịch bản: tách lời đọc, bỏ chú thích
    text = parse_script(raw_text)

    if not text:
        raise ValueError("Script is empty after parsing!")

    # Resolve voice name
    voice_id = VOICES.get(voice.lower(), voice)
    print(f"  [TTS] Clean script: {text[:100]}...")
    print(f"  [TTS] Voice: {voice_id} | Rate: {rate}")

    communicate = edge_tts.Communicate(text, voice_id, rate=rate)
    submaker = edge_tts.SubMaker()

    # Đảm bảo thư mục tồn tại
    for path in [output_audio, output_srt]:
        dirpath = os.path.dirname(path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)

    with open(output_audio, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            else:
                # Feed WordBoundary và SentenceBoundary cho SubMaker
                submaker.feed(chunk)

    # Xuất file SRT (SubRip format)
    srt_content = submaker.get_srt()
    with open(output_srt, "w", encoding="utf-8") as srt_file:
        srt_file.write(srt_content)

    print(f"  [TTS] ✅ Audio saved: {output_audio}")
    print(f"  [TTS] ✅ Subtitles saved: {output_srt}")


def run_tts(text_file: str, output_audio: str, output_srt: str, rate: str = "+20%", voice: str = "hoaimy"):
    """Wrapper đồng bộ cho generate_tts."""
    asyncio.run(generate_tts(text_file, output_audio, output_srt, rate=rate, voice=voice))


if __name__ == "__main__":
    run_tts("script.txt", "temp/audio.mp3", "temp/subtitles.srt")
