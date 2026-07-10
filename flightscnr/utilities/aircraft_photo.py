"""
Aircraft photos via planespotters.net (free, non-commercial, attribution).

Same approach as Capsule Radar (MIT):
  https://github.com/socquique/capsule-radar
  GET https://api.planespotters.net/pub/photos/hex/{icao}
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

PLANESPOTTERS_UA = (
    "FlightScnrPi/1.0 (+https://github.com/yashmulgaonkar/FlightScnr_Pi)"
)
API_BASE = "https://api.planespotters.net/pub/photos/hex"
SEARCH_TIMEOUT_S = 8
DOWNLOAD_TIMEOUT_S = 12
META_TTL_S = 14 * 24 * 3600  # hits/misses remembered two weeks
THUMB_WIDTH = 480

_DATA_DIR = os.environ.get("FLIGHTSCNR_DATA_DIR", "/var/lib/flightscnr")
_CACHE_DIR = os.path.join(_DATA_DIR, "aircraft_photos")
_META_PATH = os.path.join(_CACHE_DIR, "index.json")

_lock = threading.RLock()
_meta: dict[str, Any] | None = None


def _ensure_cache_dir() -> None:
    os.makedirs(_CACHE_DIR, exist_ok=True)


def _load_meta() -> dict[str, Any]:
    global _meta
    with _lock:
        if _meta is not None:
            return _meta
        _ensure_cache_dir()
        try:
            with open(_META_PATH, encoding="utf-8") as fh:
                data = json.load(fh)
            _meta = data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError, TypeError):
            _meta = {}
        return _meta


def _save_meta() -> None:
    with _lock:
        _ensure_cache_dir()
        tmp = _META_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(_meta or {}, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, _META_PATH)


def normalize_icao_hex(value) -> str:
    """Return a 6-char lowercase ICAO hex, or empty string."""
    if value is None:
        return ""
    hex_id = re.sub(r"[^0-9a-fA-F]", "", str(value).strip())
    if len(hex_id) < 6:
        return ""
    return hex_id[-6:].lower()


def _headers() -> dict[str, str]:
    return {"User-Agent": PLANESPOTTERS_UA, "Accept": "application/json"}


def _download(url: str, dest_path: str) -> bool:
    resp = requests.get(
        url,
        headers={"User-Agent": PLANESPOTTERS_UA},
        timeout=DOWNLOAD_TIMEOUT_S,
        stream=True,
    )
    resp.raise_for_status()
    tmp = dest_path + ".tmp"
    with open(tmp, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                fh.write(chunk)
    os.replace(tmp, dest_path)
    return os.path.isfile(dest_path) and os.path.getsize(dest_path) > 100


def _pick_image_url(photo: dict) -> str:
    """Prefer a reasonably sized thumbnail."""
    for key in ("thumbnail_large", "thumbnail", "thumbnail_large_src"):
        block = photo.get(key)
        if isinstance(block, dict):
            src = (block.get("src") or "").strip()
            if src:
                return src
        elif isinstance(block, str) and block.strip():
            return block.strip()
    # Some responses nest under "link"
    link = photo.get("link")
    if isinstance(link, str) and link.startswith("http"):
        return link
    return ""


def lookup_aircraft_photo(icao_hex: str, *, force: bool = False) -> dict | None:
    """
    Fetch/cache a planespotters photo for an ICAO hex.

    Returns dict with path, photographer, page_url, source — or None on miss.
    """
    hex_id = normalize_icao_hex(icao_hex)
    if not hex_id:
        return None

    meta = _load_meta()
    now = time.time()
    with _lock:
        entry = meta.get(hex_id)
        if entry and not force:
            if now - float(entry.get("ts") or 0) < META_TTL_S:
                if entry.get("miss"):
                    return None
                path = entry.get("path") or ""
                if path and os.path.isfile(path):
                    out = dict(entry)
                    out["cached"] = True
                    return out

    url = f"{API_BASE}/{hex_id}"
    try:
        logger.info("[photo] planespotters lookup %s", hex_id)
        resp = requests.get(url, headers=_headers(), timeout=SEARCH_TIMEOUT_S)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError, TypeError) as exc:
        logger.warning("[photo] %s request failed: %s", hex_id, exc)
        return None

    photos = data.get("photos") if isinstance(data, dict) else None
    if not photos:
        with _lock:
            meta[hex_id] = {"miss": True, "ts": now, "hex": hex_id}
            _save_meta()
        logger.info("[photo] %s: no photo available", hex_id)
        return None

    photo = photos[0] if isinstance(photos[0], dict) else {}
    img_url = _pick_image_url(photo)
    photographer = str(photo.get("photographer") or "").strip()
    page_url = str(photo.get("link") or f"https://www.planespotters.net/hex/{hex_id.upper()}").strip()
    if not img_url:
        with _lock:
            meta[hex_id] = {"miss": True, "ts": now, "hex": hex_id}
            _save_meta()
        return None

    # Optional resize via weserv (baseline JPEG) — same as Capsule Radar. Fall
    # back to the original URL if the proxy is unavailable.
    bare = img_url
    if bare.startswith("https://"):
        bare = bare[8:]
    elif bare.startswith("http://"):
        bare = bare[7:]
    proxied = (
        f"https://images.weserv.nl/?url={bare}"
        f"&w={THUMB_WIDTH}&fit=inside&output=jpg"
    )

    _ensure_cache_dir()
    dest = os.path.join(_CACHE_DIR, f"{hex_id}.jpg")
    downloaded = False
    for candidate in (proxied, img_url):
        try:
            if _download(candidate, dest):
                downloaded = True
                break
        except requests.RequestException as exc:
            logger.debug("[photo] download via %s failed: %s", candidate[:48], exc)
    if not downloaded:
        logger.warning("[photo] %s: image download failed", hex_id)
        return None

    result = {
        "miss": False,
        "ts": now,
        "hex": hex_id,
        "path": dest,
        "photographer": photographer,
        "page_url": page_url,
        "thumb_url": img_url,
        "source": "planespotters",
        "cached": False,
    }
    with _lock:
        meta[hex_id] = {k: v for k, v in result.items() if k != "cached"}
        _save_meta()
    logger.info(
        "[photo] %s: cached (%s)",
        hex_id,
        photographer or "unknown photographer",
    )
    return result


def get_cached_aircraft_photo(icao_hex: str) -> dict | None:
    hex_id = normalize_icao_hex(icao_hex)
    if not hex_id:
        return None
    meta = _load_meta()
    with _lock:
        entry = meta.get(hex_id)
        if not entry or entry.get("miss"):
            return None
        path = entry.get("path") or ""
        if path and os.path.isfile(path):
            out = dict(entry)
            out["cached"] = True
            return out
    return None


def fetch_aircraft_photo_for(flight: dict, *, force: bool = False) -> dict | None:
    if not flight:
        return None
    hex_id = normalize_icao_hex(flight.get("icao_hex") or flight.get("hex"))
    if not hex_id:
        return None
    return lookup_aircraft_photo(hex_id, force=force)


def photo_credit_line(photo: dict | None) -> str:
    if not photo:
        return ""
    photographer = (photo.get("photographer") or "").strip()
    if photographer:
        line = f"© {photographer}"
    else:
        line = "planespotters.net"
    if len(line) > 40:
        line = line[:37] + "…"
    return line
