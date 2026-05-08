import os
import math
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

class DynamicStickman:
    def __init__(self, width=1080, height=1920):
        self.width = width
        self.height = height
        self.assets_dir = "assets/meme"
        # Mặc định thân và đầu
        self.default_body = "assets/meme/body_default.png" 
        self.meme_heads = {
            "neutral": "assets/meme/wojak.png",
            "happy": "assets/meme/pepe.png",
            "funny": "assets/meme/doge.png",
            "angry": "assets/meme/wojak_angry.png"
        }

    def render_pose(self, pose_params, face_path=None, bg_color=(255, 255, 255), offset_x=0, offset_y=0, scale=1.0, t=0, emotion="neutral"):
        """
        Meme Puppet v2: Render tách lớp Đầu và Thân để tạo chuyển động linh hoạt.
        """
        final_img = Image.new("RGB", (self.width, self.height), bg_color)
        
        # 1. Hiệu ứng Camera Shake
        shake = pose_params.get("shake", 0)
        cx = offset_x + random.randint(-shake, shake) if shake > 0 else offset_x
        cy = offset_y + random.randint(-shake, shake) if shake > 0 else offset_y

        # 2. Render THÂN (Body)
        # Giả lập thân nhún nhảy nhẹ theo nhịp
        body_y_bob = math.sin(t * 5) * 15 * pose_params.get("movement", 1)
        body_scale = scale * (1.0 + math.sin(t * 2) * 0.02)
        
        # (Ở đây ta dùng thân mặc định hoặc vẽ thân đơn giản nếu chưa có ảnh thân)
        body_path = self.default_body
        if os.path.exists(body_path):
            body = Image.open(body_path).convert("RGBA")
            bw = int(700 * body_scale)
            bh = int(bw * (body.height / body.width))
            body = body.resize((bw, bh), Image.Resampling.LANCZOS)
            final_img.paste(body, (int((self.width-bw)//2 + cx), int(self.height*0.5 + body_y_bob + cy)), body)
        else:
            # Vẽ thân Stickman cao cấp hơn nếu thiếu ảnh
            draw = ImageDraw.Draw(final_img)
            neck = (self.width//2 + cx, self.height//2 + body_y_bob + cy)
            hip = (self.width//2 + cx, self.height//2 + 400*body_scale + body_y_bob + cy)
            draw.line([neck, hip], fill=(0,0,0), width=int(20*body_scale))

        # 3. Render ĐẦU (Head) - Tách biệt và "Nhấp nhô" theo giọng nói
        head_path = face_path if face_path and os.path.exists(face_path) else self.meme_heads.get(emotion, self.meme_heads["neutral"])
        
        if os.path.exists(head_path):
            head = Image.open(head_path).convert("RGBA")
            
            # Hiệu ứng nhấp nhô đầu (Bobbing) - Mạnh hơn thân để tạo cảm giác đang nói
            head_bob = math.sin(t * 12) * 25 * pose_params.get("speaking", 1)
            # Hiệu ứng phóng to thu nhỏ đầu khi nhấn mạnh (Pulsing)
            head_pulse = 1.0 + abs(math.sin(t * 15)) * 0.1 * pose_params.get("speaking", 1)
            
            hw = int(550 * scale * head_pulse)
            hh = int(hw * (head.height / head.width))
            head = head.resize((hw, hh), Image.Resampling.LANCZOS)
            
            # Xoay đầu theo nhịp hài hước
            head_tilt = math.sin(t * 8) * 10 * pose_params.get("movement", 1)
            head = head.rotate(head_tilt, expand=True, resample=Image.Resampling.BICUBIC)
            
            # Vị trí dán đầu (luôn nằm trên thân)
            hx = (self.width - head.width) // 2 + int(cx)
            hy = (self.height // 2) - head.height + int(head_bob + cy) + 100
            
            final_img.paste(head, (int(hx), int(hy)), head)

        # 4. Hiệu ứng Overlay (Flash/Speed lines)
        if pose_params.get("speed_lines", False):
            self._draw_speed_lines(final_img, t)

        return np.array(final_img)

    def _draw_speed_lines(self, img, t):
        draw = ImageDraw.Draw(img)
        for _ in range(15):
            x = random.randint(0, self.width)
            y1 = random.randint(0, self.height)
            length = random.randint(200, 500)
            draw.line([(x, y1), (x, y1 + length)], fill=(0,0,0, 100), width=2)

    def get_preset_pose(self, name, t=0):
        if name == "idle":
            return {"shake": 0, "movement": 0.5, "speaking": 0.3, "speed_lines": False}
        elif name == "shout":
            return {"shake": 35, "movement": 2.0, "speaking": 2.5, "speed_lines": True}
        elif name == "run":
            return {"shake": 15, "movement": 3.0, "speaking": 0.5, "speed_lines": True}
        elif name == "thinking":
            return {"shake": 2, "movement": 0.2, "speaking": 0.8, "speed_lines": False}
        return self.get_preset_pose("idle")

if __name__ == "__main__":
    engine = DynamicStickman()
    os.makedirs("assets/meme", exist_ok=True)
    frame = engine.render_pose(engine.get_preset_pose("shout", t=1.0), t=1.0)
    Image.fromarray(frame).save("test_puppet_v2.jpg")
