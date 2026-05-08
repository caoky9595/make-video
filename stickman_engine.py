import os
import random
import numpy as np
from dynamic_stickman import DynamicStickman

class StickmanEngine:
    def __init__(self):
        self.faces_dir = "assets/stickman/faces"
        self.ds = DynamicStickman()
        
        # Mapping cảm xúc sang danh sách các face index (dựa trên sprite sheet 6x6)
        # Lưu ý: Đây là phán đoán sơ bộ dựa trên ảnh đã generate
        self.emotion_pools = {
            "fun": ["face_0.png", "face_2.png", "face_24.png", "face_32.png"],
            "angry": ["face_1.png", "face_19.png", "face_33.png"],
            "sad": ["face_12.png", "face_25.png", "face_31.png"],
            "explaining": ["face_7.png", "face_15.png", "face_23.png"],
            "neutral": ["face_3.png", "face_21.png", "face_27.png"],
            "surprised": ["face_5.png", "face_11.png", "face_17.png"]
        }

    def _analyze_emotion(self, text):
        """Phân tích sơ bộ cảm xúc từ text để chọn meme."""
        text = text.lower()
        if any(w in text for w in ["hả", "sao", "tại sao", "giải thích", "vấn đề"]):
            return "explaining"
        if any(w in text for w in ["điên", "giận", "chửi", "tức", "vãi", "thế quái"]):
            return "angry"
        if any(w in text for w in ["buồn", "khóc", "thất bại", "tiếc", "haizz"]):
            return "sad"
        if any(w in text for w in ["vui", "hài", "cười", "biết ngay", "lol"]):
            return "fun"
        if any(w in text for w in ["wow", "kinh", "bất ngờ", "ố mài gót"]):
            return "surprised"
        return "neutral"

    def render_frame_to_array(self, text, width=1080, height=1920, bg_color=(255, 255, 255), t=0, seed=None, offset_x=0, offset_y=0, scale=1.0):
        """Trả về frame dưới dạng numpy array (RGB) để dùng với MoviePy."""
        emotion = self._analyze_emotion(text)
        
        # Sử dụng local Random với seed để cố định face cho cùng một câu thoại
        rnd = random.Random(seed)
        pool = self.emotion_pools.get(emotion, self.emotion_pools["neutral"])
        face_file = rnd.choice(pool)
        face_path = os.path.join(self.faces_dir, face_file)
        
        # Chọn pose dựa trên cảm xúc và từ khóa
        text_l = text.lower()
        pose_name = "idle"
        if any(w in text_l for w in ["chạy", "nhanh", "flash", "phóng"]):
            pose_name = "run"
        elif any(w in text_l for w in ["haizz", "thất bại", "tiếc", "ấn nút hoãn"]):
            pose_name = "facepalm"
        elif emotion in ["fun", "neutral"]: 
            pose_name = "wave"
        elif emotion == "angry": 
            pose_name = "shout"
        elif emotion == "explaining": 
            pose_name = "thinking"
        
        pose_params = self.ds.get_preset_pose(pose_name, t=t)
        
        # Truyền thêm t và emotion vào để kích hoạt hiệu ứng động trong DynamicStickman
        return self.ds.render_pose(
            pose_params, face_path=face_path, bg_color=bg_color,
            offset_x=offset_x, offset_y=offset_y, scale=scale,
            t=t, emotion=emotion
        )

    def create_frame(self, text, output_path, bg_color=(255, 255, 255)):
        """Tạo một khung hình gồm Người que + Meme Face + Subtitle."""
        emotion = self._analyze_emotion(text)
        assets = self.emotion_map[emotion]
        
        # 1. Tạo canvas nền (9:16 cho TikTok)
        width, height = 1080, 1920
        canvas = Image.new("RGB", (width, height), bg_color)
        
        # 2. Load Body
        body_img = Image.open(os.path.join(self.bodies_dir, assets["body"])).convert("RGBA")
        # Resize body cho vừa màn hình
        body_img = body_img.resize((600, 900))
        
        # 3. Load Face
        face_img = Image.open(os.path.join(self.faces_dir, assets["face"])).convert("RGBA")
        # Resize face cho khớp với đầu (khoảng 300x300)
        face_img = face_img.resize((350, 350))
        
        # 4. Ghép Face lên Body
        # Vị trí cổ trong body (sau khi resize) khoảng x=300, y=225
        # Chúng ta dán face sao cho tâm của nó khớp với đầu
        canvas.paste(body_img, (240, 600), body_img)
        canvas.paste(face_img, (365, 500), face_img)
        
        # 5. Vẽ Text (Subtitle)
        draw = ImageDraw.Draw(canvas)
        # Tìm font tiếng Việt (thường là /Library/Fonts/Arial.ttf trên Mac)
        font_path = "/Library/Fonts/Arial Unicode.ttf"
        if not os.path.exists(font_path):
            font_path = "/System/Library/Fonts/Cache/STHeiti Light.ttc" # Fallback Mac
            
        try:
            font = ImageFont.truetype(font_path, 60)
        except:
            font = ImageFont.load_default()
            
        # Wrap text đơn giản
        lines = self._wrap_text(text, 25)
        y_text = 1500
        for line in lines:
            # draw.textbbox is newer, use it if available
            w = draw.textlength(line, font=font)
            draw.text(((width - w) / 2, y_text), line, font=font, fill=(0, 0, 0))
            y_text += 80
            
        canvas.save(output_path)
        return output_path

    def _wrap_text(self, text, max_chars):
        words = text.split()
        lines = []
        current_line = []
        for word in words:
            if len(" ".join(current_line + [word])) <= max_chars:
                current_line.append(word)
            else:
                lines.append(" ".join(current_line))
                current_line = [word]
        lines.append(" ".join(current_line))
        return lines

if __name__ == "__main__":
    engine = StickmanEngine()
    engine.create_frame("Chào các bạn, hôm nay mình sẽ kể một câu chuyện cực kỳ hài hước!", "test_stickman.jpg")
    print("Test frame created: test_stickman.jpg")
