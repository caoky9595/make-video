"""
jobs_db.py - Quản lý trạng thái Job bằng SQLite
===============================================
Lưu trữ và cập nhật trạng thái của từng Job tạo video vào SQLite database.
"""

import sqlite3
import os
from typing import Optional
from core.utils.logger_config import logger

DB_PATH = "data/jobs.db"


def get_db_connection() -> sqlite3.Connection:
    """Tạo kết nối tới SQLite Database."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Khởi tạo bảng video_jobs nếu chưa tồn tại."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS video_jobs (
        job_id TEXT PRIMARY KEY,
        status TEXT NOT NULL,       -- "queued", "processing", "completed", "failed"
        progress INTEGER DEFAULT 0,
        message TEXT,
        output_file TEXT,
        error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()


def create_job(job_id: str, status: str = "queued", message: str = "Đang chờ...") -> bool:
    """Tạo mới một Job.

    Args:
        job_id: ID duy nhất dạng UUID.
        status: Trạng thái ban đầu.
        message: Tin nhắn khởi tạo.

    Returns:
        True nếu thành công, False nếu thất bại.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO video_jobs (job_id, status, message) VALUES (?, ?, ?)",
            (job_id, status, message)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Lỗi create_job: {e}")
        return False


def update_job_status(
    job_id: str,
    status: str,
    progress: int,
    message: str,
    output_file: Optional[str] = None,
    error: Optional[str] = None
) -> bool:
    """Cập nhật trạng thái và tiến độ của một Job.

    Args:
        job_id: ID của Job cần cập nhật.
        status: Trạng thái mới ("queued", "processing", "completed", "failed").
        progress: Tiến độ (0-100).
        message: Tin nhắn mô tả bước hiện tại.
        output_file: Path dẫn tới file video đầu ra (nếu hoàn tất).
        error: Chi tiết lỗi (nếu thất bại).

    Returns:
        True nếu thành công, False nếu thất bại.
    """
    # Job đã ở trạng thái cuối (completed/failed) thì không cho 1 update "queued"/"processing"
    # đến trễ (race giữa thread render và request /stop chạy song song) ghi đè ngược lại —
    # tránh job đã xong/đã bị huỷ lại hiện nhầm "đang xử lý" trên UI.
    guard = " AND status NOT IN ('completed', 'failed')" if status not in ("completed", "failed") else ""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if output_file is not None and error is not None:
            cursor.execute(f"""
                UPDATE video_jobs
                SET status = ?, progress = ?, message = ?, output_file = ?, error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ?{guard}
            """, (status, progress, message, output_file, error, job_id))
        elif output_file is not None:
            cursor.execute(f"""
                UPDATE video_jobs
                SET status = ?, progress = ?, message = ?, output_file = ?, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ?{guard}
            """, (status, progress, message, output_file, job_id))
        elif error is not None:
            cursor.execute(f"""
                UPDATE video_jobs
                SET status = ?, progress = ?, message = ?, error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ?{guard}
            """, (status, progress, message, error, job_id))
        else:
            cursor.execute(f"""
                UPDATE video_jobs
                SET status = ?, progress = ?, message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ?{guard}
            """, (status, progress, message, job_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Lỗi update_job_status: {e}")
        return False


def get_job(job_id: str) -> Optional[dict]:
    """Lấy thông tin chi tiết của một Job theo ID.

    Args:
        job_id: ID của Job cần lấy.

    Returns:
        Dict chứa thông tin của Job hoặc None nếu không thấy.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM video_jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None
    except Exception as e:
        logger.error(f"Lỗi get_job: {e}")
        return None


def get_latest_job() -> Optional[dict]:
    """Lấy Job được tạo mới nhất.

    Returns:
        Dict chứa thông tin của Job mới nhất hoặc None nếu không có.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM video_jobs ORDER BY created_at DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None
    except Exception as e:
        logger.error(f"Lỗi get_latest_job: {e}")
        return None


def clean_stuck_jobs() -> bool:
    """Đánh dấu tất cả các job đang ở trạng thái 'queued' hoặc 'processing' thành 'failed' khi khởi động server.

    Returns:
        True nếu thành công, False nếu thất bại.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE video_jobs 
            SET status = 'failed', error = 'Server restarted, job terminated.', updated_at = CURRENT_TIMESTAMP 
            WHERE status IN ('queued', 'processing')
        """)
        conn.commit()
        conn.close()
        logger.info("✅ Đã dọn dẹp các job bị treo khi khởi động.")
        return True
    except Exception as e:
        logger.error(f"Lỗi clean_stuck_jobs: {e}")
        return False
