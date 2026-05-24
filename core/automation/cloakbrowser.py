import os
import sys
import glob
from pathlib import Path
from core.utils.logger_config import logger

def find_cloak_binary():
    """
    Tìm đường dẫn binary của CloakBrowser trên MacOS.
    """
    if sys.platform != "darwin":
        return None

    # Các vị trí phổ biến
    search_paths = [
        "/Applications/CloakBrowser.app/Contents/MacOS/CloakBrowser",
        os.path.expanduser("~/.cloakbrowser/*/Chromium.app/Contents/MacOS/Chromium"),
        os.path.expanduser("~/.cloakbrowser/*/CloakBrowser.app/Contents/MacOS/CloakBrowser"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" # Fallback
    ]

    for pattern in search_paths:
        matches = glob.glob(pattern)
        if matches:
            # Ưu tiên bản mới nhất hoặc bản đầu tiên tìm thấy
            path = sorted(matches, reverse=True)[0]
            if os.path.exists(path):
                return path
    
    return None

def ensure_binary():
    """Ensure binary."""
    path = find_cloak_binary()
    if not path:
        raise ImportError("CloakBrowser binary not found")
    return path

if __name__ == "__main__":
    path = find_cloak_binary()
    if path:
        logger.info(f"Found: {path}")
    else:
        logger.info("Not found")
