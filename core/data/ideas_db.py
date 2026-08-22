"""
ideas_db.py - Quản lý Ngân hàng Ý tưởng bằng SQLite
====================================================
Lưu trữ ý tưởng video do AI gợi ý hoặc tự nhập, chống trùng lặp giữa các lần sinh ý tưởng.
"""

import sqlite3
from typing import Optional
from core.utils.logger_config import logger
from core.data.jobs_db import get_db_connection

VALID_STATUSES = ("new", "used", "skipped")


def init_ideas_table() -> None:
    """Khởi tạo bảng ideas nếu chưa tồn tại."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ideas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL,
        category TEXT,
        format TEXT,
        mode TEXT DEFAULT 'viral',
        status TEXT DEFAULT 'new',      -- new | used | skipped
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        used_at TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()


def create_idea(text: str, category: Optional[str] = None, format: Optional[str] = None, mode: str = "viral") -> Optional[int]:
    """Thêm 1 ý tưởng mới vào ngân hàng.

    Returns:
        id của ý tưởng vừa tạo, hoặc None nếu thất bại.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO ideas (text, category, format, mode) VALUES (?, ?, ?, ?)",
            (text, category, format, mode)
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return new_id
    except Exception as e:
        logger.error(f"Lỗi create_idea: {e}")
        return None


def list_ideas(status: Optional[str] = None, category: Optional[str] = None, mode: Optional[str] = None, limit: int = 200) -> list:
    """Lấy danh sách ý tưởng, mới nhất trước, có thể lọc theo status/category/mode."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM ideas WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if category:
            query += " AND category = ?"
            params.append(category)
        if mode:
            query += " AND mode = ?"
            params.append(mode)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Lỗi list_ideas: {e}")
        return []


def update_idea_status(idea_id: int, status: str) -> bool:
    """Cập nhật trạng thái 1 ý tưởng (new/used/skipped)."""
    if status not in VALID_STATUSES:
        logger.error(f"Lỗi update_idea_status: status không hợp lệ '{status}'")
        return False
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if status == "used":
            cursor.execute(
                "UPDATE ideas SET status = ?, used_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, idea_id)
            )
        else:
            cursor.execute("UPDATE ideas SET status = ? WHERE id = ?", (status, idea_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Lỗi update_idea_status: {e}")
        return False


def delete_idea(idea_id: int) -> bool:
    """Xoá 1 ý tưởng khỏi ngân hàng."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ideas WHERE id = ?", (idea_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Lỗi delete_idea: {e}")
        return False


def get_recent_idea_texts(limit: int = 30) -> list:
    """Lấy text của các ý tưởng gần đây (mọi trạng thái) để nhét vào prompt Gemini chống lặp."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT text FROM ideas ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [row["text"] for row in rows]
    except Exception as e:
        logger.error(f"Lỗi get_recent_idea_texts: {e}")
        return []
