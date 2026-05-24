import os
import urllib.parse
import urllib.request
import uuid
from core.utils.logger_config import logger

def generate_pollinations_image(prompt: str, output_dir: str = "uploaded_images") -> str:
    """
    Sinh ảnh tĩnh 0 đồng qua Pollinations.ai API.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Pollinations prompt format
    encoded_prompt = urllib.parse.quote(prompt + " masterpiece, high quality, highly detailed, vertical portrait, 9:16 aspect ratio, cinematic lighting")
    
    # Add random seed to avoid cache
    seed = uuid.uuid4().hex[:8]
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&nologo=true&seed={seed}"
    
    output_path = os.path.join(output_dir, f"ai_gen_{seed}.jpg")
    
    logger.info(f"[AI Visuals] Sinh ảnh từ prompt: '{prompt}'")
    try:
        urllib.request.urlretrieve(url, output_path)
        logger.info(f"[AI Visuals] ✅ Lưu ảnh thành công: {output_path}")
        return output_path
    except Exception as e:
        logger.info(f"[AI Visuals] ❌ Lỗi sinh ảnh: {e}")
        return None

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        generate_pollinations_image(sys.argv[1])
    else:
        logger.info("Sử dụng: python ai_visuals.py 'Mô tả hình ảnh'")
