from PIL import Image, ImageDraw, ImageFont
import os
import platform
from core.utils.logger_config import logger

# Lấy font
def _get_font(size):
    system = platform.system()
    if system == "Darwin":
        candidates = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf", 
            "/System/Library/Fonts/Supplemental/Arial.ttf"
        ]
    else:
        candidates = ["C:\\Windows\\Fonts\\arialbd.ttf"]
    
    for font_path in candidates:
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, size)
    return ImageFont.load_default()

bg_color = (30, 30, 30, 255)

def save_sample(name, draw_func):
    """Save sample."""
    img = Image.new("RGBA", (1000, 250), bg_color)
    draw_func(ImageDraw.Draw(img), img.size[0], img.size[1])
    path = os.path.join(os.getcwd(), 'output', f'{name}.png')
    img.save(path)

# 1. Ali Abdaal (Tối giản)
def draw_ali(draw, w, h):
    """Draw ali."""
    font_ali = _get_font(60)
    words = ["Khách", "hàng", "gõ", "đúng", "tên"]
    x = 100
    y = 90
    for i, word in enumerate(words):
        color = (135, 206, 250) if i == 3 else (230, 230, 230)
        # soft shadow
        draw.text((x+3, y+3), word, font=font_ali, fill=(0,0,0,150))
        draw.text((x, y), word, font=font_ali, fill=color+(255,))
        try:
            x += int(draw.textlength(word, font=font_ali)) + 20
        except Exception:
            x += draw.textbbox((0,0), word, font=font_ali)[2] + 20

# 2. Marker Box
def draw_marker(draw, w, h):
    """Draw marker."""
    font_b = _get_font(70)
    words = ["KHÁCH", "HÀNG", "GÕ", "ĐÚNG", "TÊN"]
    x = 100
    y = 80
    for i, word in enumerate(words):
        try:
            tw = int(draw.textlength(word, font=font_b))
        except Exception:
            tw = draw.textbbox((0,0), word, font=font_b)[2]
        
        if i == 3:
            # draw box
            draw.rectangle([x-10, y-5, x+tw+10, y+80], fill=(57, 255, 20, 255)) # green box
            fill = (0,0,0,255)
        else:
            fill = (255,255,255,255)
            # stroke
            draw.text((x+3, y+3), word, font=font_b, fill=(0,0,0,255))
            
        draw.text((x, y), word, font=font_b, fill=fill)
        x += tw + 25

# 3. MrBeast
def draw_beast(draw, w, h):
    """Draw beast."""
    font_b = _get_font(70)
    font_big = _get_font(95)
    words = ["KHÁCH", "HÀNG", "GÕ", "ĐÚNG", "TÊN"]
    x = 80
    y = 80
    for i, word in enumerate(words):
        f = font_big if i == 3 else font_b
        try:
            tw = int(draw.textlength(word, font=f))
        except Exception:
            tw = draw.textbbox((0,0), word, font=f)[2]
        c_y = y - 20 if i == 3 else y
        stroke_w = 6 if i == 3 else 4
        # thick stroke
        for dx in range(-stroke_w, stroke_w+1):
            for dy in range(-stroke_w, stroke_w+1):
                if dx*dx + dy*dy <= stroke_w*stroke_w:
                    draw.text((x+dx, c_y+dy), word, font=f, fill=(0,0,0,255))
                    
        # Fill
        fill = (255, 50, 50, 255) if i == 3 else (255,255,255,255)
        draw.text((x, c_y), word, font=f, fill=fill)
        x += tw + 20

# 4. Fade In / Gõ chữ
def draw_type(draw, w, h):
    # backdrop
    """Draw type."""
    draw.rectangle([50, 70, 950, 180], fill=(0,0,0, 150))
    font_t = _get_font(60)
    words = ["Khách", "hàng", "gõ", "đúng"]
    x = 80
    y = 95
    for word in words:
        draw.text((x, y), word, font=font_t, fill=(255,255,255,255))
        try:
            x += int(draw.textlength(word, font=font_t)) + 20
        except Exception:
            x += draw.textbbox((0,0), word, font=font_t)[2] + 20

os.makedirs(os.path.join(os.getcwd(), 'output'), exist_ok=True)
save_sample("s_ali", draw_ali)
save_sample("s_box", draw_marker)
save_sample("s_beast", draw_beast)
save_sample("s_type", draw_type)
logger.info("Done")
