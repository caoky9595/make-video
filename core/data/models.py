"""
models.py - Cấu hình Config Entities và Dataclasses
===================================================
Chứa cấu hình cho Audio và Subtitle của một video job.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AudioConfig:
    voice: str = "vi-VN-HoaiMyNeural"
    rate: str = "+50%"
    bgm_path: Optional[str] = None
    bgm_volume: float = 0.22
    bgm_start_sec: float = 0.0


@dataclass
class SubtitleConfig:
    style: int = 1
    position: str = "bottom"
    font_path: Optional[str] = None
    overlay_opacity: float = 0.35


