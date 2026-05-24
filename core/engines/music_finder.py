"""
music_finder.py - Auto Music Resolver for Studio
===============================================
Finds suitable background music from local library or online free-to-use API.
"""

import os
import re
import time
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from core.utils.logger_config import logger

load_dotenv()


MOOD_MAP = {
    r"\bbuon\b|\bbuồn\b|\btam su\b|\btâm sự\b": "sad piano emotional",
    r"\bkinh di\b|\bkinh dị\b|\bso\b|\bsợ\b": "dark suspense cinematic",
    r"\bhai\b|\bfunny\b|\bvui\b": "happy upbeat",
    r"\bchill\b|\blofi\b": "lofi chill",
    r"\binspire\b|\bdong luc\b|\bđộng lực\b": "inspiring motivational",
}


def _extract_music_query(script_text: str, custom_query: str = "") -> str:
    if custom_query.strip():
        return custom_query.strip()

    script_lower = script_text.lower()
    for pattern, query in MOOD_MAP.items():
        if re.search(pattern, script_lower):
            return query

    return "cinematic background instrumental"


def _normalize_track_items(payload):
    """Accept multiple API schemas and normalize into (title, audio_url)."""
    candidates = []

    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        for key in ("tracks", "results", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                candidates = value
                break
            if isinstance(value, dict):
                nested = value.get("items") or value.get("results")
                if isinstance(nested, list):
                    candidates = nested
                    break

    normalized = []
    for item in candidates:
        if not isinstance(item, dict):
            continue

        title = item.get("title") or item.get("name") or "track"

        audio_url = (
            item.get("download_url")
            or item.get("audio_url")
            or item.get("preview_url")
            or item.get("url")
        )

        if not audio_url and isinstance(item.get("file"), dict):
            audio_url = item["file"].get("url")

        if not audio_url or not isinstance(audio_url, str):
            continue

        normalized.append({"title": title, "audio_url": audio_url})

    return normalized


def _search_freetouse_tracks(query: str, limit: int = 8):
    """
    Search track candidates from a configurable free-to-use music API.

    Required env:
      - FREETOUSE_API_URL
      - FREETOUSE_API_KEY (optional, depends on provider)

    Notes:
      The parser is schema-tolerant so users can plug in API providers with
      minor response differences.
    """
    base_url = (os.getenv("FREETOUSE_API_URL") or "").strip()
    api_key = (os.getenv("FREETOUSE_API_KEY") or "").strip()

    if not base_url:
        logger.info("  [Music AI] FREETOUSE_API_URL chưa cấu hình. Bỏ qua AI online.")
        return []

    headers = {}
    if api_key:
        # Set common auth headers to support multiple providers.
        headers["Authorization"] = f"Bearer {api_key}"
        headers["X-API-Key"] = api_key

    params = {
        "q": query,
        "query": query,
        "limit": limit,
    }

    try:
        resp = requests.get(base_url, headers=headers, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return _normalize_track_items(data)
    except Exception as e:
        logger.info(f"  [Music AI] API search failed: {e}")
        return []


def _infer_extension(url: str) -> str:
    path = urlparse(url).path.lower()
    for ext in (".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac", ".webm"):
        if path.endswith(ext):
            return ext
    return ".mp3"


def _download_track(track: dict, output_dir: str = "audio_bg"):
    os.makedirs(output_dir, exist_ok=True)
    ext = _infer_extension(track["audio_url"])
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", track.get("title", "track")).strip("_")[:40]
    filename = f"auto_{slug}_{int(time.time())}{ext}"
    out_path = os.path.join(output_dir, filename)

    try:
        r = requests.get(track["audio_url"], timeout=30)
        r.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(r.content)

        logger.info(f"  [Music AI] Downloaded: {filename}")
        return out_path
    except Exception as e:
        logger.info(f"  [Music AI] Download failed: {e}")
        return None


def pick_local_music_for_script(script_text: str, music_dir: str = "audio_bg"):
    """Pick local music for script."""
    if not os.path.isdir(music_dir):
        return None

    supported = (".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac", ".webm")
    tracks = [f for f in os.listdir(music_dir) if f.lower().endswith(supported)]
    if not tracks:
        return None

    query = _extract_music_query(script_text)
    query_tokens = {t for t in re.split(r"[^a-zA-Z0-9]+", query.lower()) if len(t) > 2}

    scored = []
    for t in tracks:
        file_tokens = {x for x in re.split(r"[^a-zA-Z0-9]+", t.lower()) if len(x) > 2}
        score = len(query_tokens.intersection(file_tokens))
        scored.append((score, t))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_name = scored[0][1]
    best_path = os.path.join(music_dir, best_name)
    logger.info(f"  [Music AI] Local selected: {best_name}")
    return best_path


def resolve_music_for_script(
    script_text: str,
    output_dir: str = "audio_bg",
    music_query: str = "",
    provider: str = "freetouse",
):
    """Resolve music for script."""
    query = _extract_music_query(script_text, custom_query=music_query)
    logger.info(f"  [Music AI] Query: {query}")

    if provider != "freetouse":
        logger.info(f"  [Music AI] Provider '{provider}' chưa hỗ trợ.")
        return None

    tracks = _search_freetouse_tracks(query)
    if not tracks:
        return None

    for track in tracks:
        path = _download_track(track, output_dir=output_dir)
        if path:
            return path

    return None

