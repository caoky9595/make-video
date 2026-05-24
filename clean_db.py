import sqlite3
from core.utils.logger_config import logger
DB_PATH = "data/jobs.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute(
    "UPDATE video_jobs SET status='failed', error='Server crash', message='Lỗi: Tiến trình bị gián đoạn' WHERE status='processing'"
)
conn.commit()
conn.close()
logger.info("Cleaned!")
