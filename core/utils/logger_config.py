import logging
import sys
import os

def setup_logger(name: str = "VideoMakerPro") -> logging.Logger:
    """
    Tạo và cấu hình logger chuẩn cho toàn bộ dự án.
    Ghi log ra console và có thể mở rộng ghi ra file.
    """
    logger = logging.getLogger(name)
    
    # Nếu logger đã được cấu hình, trả về luôn để tránh duplicate log
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # Cấu hình format log
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Log ra console (stdout) thay vì stderr cho INFO
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    # Tuỳ chọn: Ghi log lỗi ra file nếu cần
    log_dir = "logs"
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except Exception:
            pass
            
    if os.path.exists(log_dir):
        file_handler = logging.FileHandler(os.path.join(log_dir, "app.log"), encoding="utf-8")
        file_handler.setLevel(logging.WARNING) # Chỉ ghi WARNING trở lên vào file
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

# Tạo instance mặc định để các module khác có thể import trực tiếp
logger = setup_logger()
