"""Airline logo loading for round touch display."""

from __future__ import annotations

import os

import pygame

try:
    from PIL import Image
except ImportError:
    Image = None

_DEFAULT = "default"
_cache: dict[tuple[str, int], pygame.Surface | None] = {}


def _package_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _logo_dir() -> str:
    base = _package_root()
    ref = os.path.join(base, "logos")
    if os.path.isdir(ref):
        return ref
    if os.path.isfile(ref):
        try:
            with open(ref, encoding="utf-8") as fh:
                rel = fh.read().strip()
            candidate = os.path.normpath(os.path.join(base, rel))
            if os.path.isdir(candidate):
                return candidate
        except OSError:
            pass
    return ref


def _logo_path(icao: str) -> str | None:
    code = (icao or "").strip().upper()
    if not code or code == "N/A":
        code = _DEFAULT
    path = os.path.join(_logo_dir(), f"{code}.png")
    if os.path.isfile(path):
        return path
    fallback = os.path.join(_logo_dir(), f"{_DEFAULT}.png")
    return fallback if os.path.isfile(fallback) else None


def icao_for_flight(flight: dict) -> str:
    icao = (flight.get("owner_icao") or "").strip().upper()
    if icao and icao != "N/A":
        return icao
    callsign = (flight.get("callsign") or "").strip().upper()
    if len(callsign) >= 3 and callsign[:3].isalpha():
        return callsign[:3]
    return _DEFAULT


def load_logo_surface(icao: str, size: int) -> pygame.Surface | None:
    if size <= 0 or Image is None:
        return None
    key = ((icao or "").upper(), size)
    if key in _cache:
        return _cache[key]

    surface = None
    path = _logo_path(icao)
    if path:
        try:
            image = Image.open(path).convert("RGBA")
            try:
                resample = Image.Resampling.LANCZOS
            except AttributeError:
                resample = Image.LANCZOS
            # thumbnail() never upscales; source PNGs are 16×16 matrix assets.
            image = image.resize((size, size), resample)
            surface = pygame.image.frombuffer(image.tobytes(), image.size, "RGBA").convert_alpha()
        except OSError:
            surface = None

    _cache[key] = surface
    return surface
