"""Load cached vessel photo surfaces for the detail screen."""

from __future__ import annotations

import logging
import os

import pygame

try:
    from PIL import Image
except ImportError:
    Image = None

logger = logging.getLogger(__name__)

_cache: dict[tuple[str, int], pygame.Surface | None] = {}


def load_photo_surface(path: str, max_h: int, *, max_w: int | None = None) -> pygame.Surface | None:
    """Load a vessel photo scaled to fit max_h (and optional max_w)."""
    if not path or max_h <= 0 or Image is None:
        return None
    if not os.path.isfile(path):
        return None
    key = (path, max_h, max_w or 0)
    if key in _cache:
        return _cache[key]

    surface = None
    try:
        image = Image.open(path).convert("RGBA")
        src_w, src_h = image.size
        if src_h <= 0 or src_w <= 0:
            _cache[key] = None
            return None
        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = Image.LANCZOS
        scale = max_h / src_h
        new_w = max(1, int(round(src_w * scale)))
        new_h = max_h
        if max_w and new_w > max_w:
            scale = max_w / src_w
            new_w = max_w
            new_h = max(1, int(round(src_h * scale)))
        image = image.resize((new_w, new_h), resample)
        surface = pygame.image.frombuffer(
            image.tobytes(), image.size, "RGBA"
        ).convert_alpha()
    except OSError as exc:
        logger.debug("Vessel photo load failed %s: %s", path, exc)
        surface = None

    _cache[key] = surface
    return surface


def invalidate(path: str | None = None) -> None:
    if path is None:
        _cache.clear()
        return
    for key in list(_cache):
        if key[0] == path:
            _cache.pop(key, None)
