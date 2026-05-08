import os
from PIL import Image, ImageDraw

def create_stickman_body(name, pose="idle"):
    """Tạo thân người que cơ bản (không đầu) bằng PIL."""
    width, height = 400, 600
    img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    color = (0, 0, 0, 255) # Đen
    thickness = 8
    
    # Tọa độ cổ (gốc để gắn đầu)
    neck = (200, 150)
    # Tọa độ hông
    hip = (200, 350)
    
    # 1. Vẽ xương sống
    draw.line([neck, hip], fill=color, width=thickness)
    
    if pose == "idle":
        # Hai tay buông xuôi
        draw.line([neck, (130, 250)], fill=color, width=thickness) # Tay trái
        draw.line([neck, (270, 250)], fill=color, width=thickness) # Tay phải
        # Hai chân đứng thẳng
        draw.line([hip, (150, 550)], fill=color, width=thickness) # Chân trái
        draw.line([hip, (250, 550)], fill=color, width=thickness) # Chân phải
        
    elif pose == "explaining":
        # Một tay chỉ lên, một tay chống hông
        draw.line([neck, (100, 100)], fill=color, width=thickness) # Tay chỉ lên
        draw.line([neck, (250, 250), (280, 350)], fill=color, width=thickness) # Tay chống hông
        draw.line([hip, (170, 550)], fill=color, width=thickness)
        draw.line([hip, (230, 550)], fill=color, width=thickness)

    elif pose == "angry":
        # Hai tay dang rộng, chân đứng choãi
        draw.line([neck, (100, 180)], fill=color, width=thickness)
        draw.line([neck, (300, 180)], fill=color, width=thickness)
        draw.line([hip, (120, 550)], fill=color, width=thickness)
        draw.line([hip, (280, 550)], fill=color, width=thickness)

    elif pose == "thinking":
        # Tay chạm cằm
        draw.line([neck, (180, 200), (190, 140)], fill=color, width=thickness)
        draw.line([neck, (250, 300)], fill=color, width=thickness)
        draw.line([hip, (180, 550)], fill=color, width=thickness)
        draw.line([hip, (220, 550)], fill=color, width=thickness)

    output_path = f"assets/stickman/bodies/{name}.png"
    img.save(output_path)
    print(f"Generated {output_path}")

if __name__ == "__main__":
    os.makedirs("assets/stickman/bodies", exist_ok=True)
    create_stickman_body("idle", "idle")
    create_stickman_body("explaining", "explaining")
    create_stickman_body("angry", "angry")
    create_stickman_body("thinking", "thinking")
