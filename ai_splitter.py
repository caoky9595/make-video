import os
import json
import urllib.request

def load_env():
    # Simple manual .env loader
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ[k.strip()] = v.strip()

def split_story_script(script_text: str):
    load_env()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("\n❌ LỖI: THIẾU API KEY CỦA GOOGLE GEMINI!")
        print("   Để dùng tính năng Auto-Split (AI Cắt Truyện), hãy làm theo 2 bước sau:")
        print("   1. Lấy mã miễn phí tại: https://aistudio.google.com/app/apikey")
        print("   2. Tạo một file tên là `.env` cùng thư mục code, ghi nội dung:")
        print("      GEMINI_API_KEY=mã_của_bạn_ở_đây")
        return None

    print("\n🧠 [AI Splitter] Đang gọi Gemini AI để phân tích điểm cắt gay cấn nhất...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    prompt = f"""Bạn là một chuyên gia biên tập video kể chuyện (Reddit Stories, Tâm sự).
Nhiệm vụ: Chia kịch bản sau đây làm 2 hoặc tối đa 3 phần, mỗi phần độ dài ngang nhau.
LUẬT SỐNG CÒN (CLIFFHANGER): KHÔNG ĐƯỢC CẮT NGANG TÙY TIỆN dở chừng câu thoại. Khi kết thúc mỗi phần, bạn PHẢI tìm đúng khoảnh khắc gây cấn, bí ẩn nhất hoặc cao trào nhất để ngắt mạch truyện.
Cuối phần trước PHẢI dập thêm câu: "Nhấn follow để xem Phần tiếp theo nhé!".
Đầu phần sau phải bắt đầu liền mạch với chữ đầu tiên của vế sau.
Chú ý: Bạn KHÔNG được tóm tắt tắt, phải giữ NGUYÊN VĂN lời thoại của tác giả.

Hãy trả về DUY NHẤT một mảng JSON chuẩn chứa văn bản các phần. KHÔNG TẠO markdown ```json.
[
  "Nội dung nguyên văn phần 1... Nhấn follow để xem Phần tiếp theo nhé!",
  "Nội dung nguyên văn phần 2..."
]

Kịch bản cần cắt:
{script_text}
"""
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3}
    }
    
    req = urllib.request.Request(
        url, 
        data=json.dumps(payload).encode("utf-8"), 
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            text_response = result["candidates"][0]["content"]["parts"][0]["text"]
            
            # Xử lý markdown thừa nếu AI vô tình sinh ra
            text_response = text_response.strip()
            if text_response.startswith("```json"):
                text_response = text_response[7:]
            if text_response.startswith("```"):
                text_response = text_response[3:]
            if text_response.endswith("```"):
                text_response = text_response[:-3]
                
            parts = json.loads(text_response.strip())
            if isinstance(parts, list) and all(isinstance(p, str) for p in parts):
                return parts
            else:
                return [script_text]
    except Exception as e:
        print(f"❌ Lỗi khi gọi Gemini API: {e}")
        return [script_text]
