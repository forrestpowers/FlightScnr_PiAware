"""Clock screen with optional weather from plane-tracker APIs."""

from datetime import datetime
import time

import pygame

try:
    from config import CLOCK_FORMAT, TEMPERATURE_UNITS
except ImportError:
    CLOCK_FORMAT = "24hr"
    TEMPERATURE_UNITS = "metric"

from display.round_touch import draw, theme

_weather_cache = {"temp": None, "ts": 0}


def _fetch_temperature():
    now = time.time()
    if now - _weather_cache["ts"] < 1800 and _weather_cache["temp"] is not None:
        return _weather_cache["temp"]
    try:
        result = __import__("utilities.temperature", fromlist=["grab_temperature_and_humidity"]).grab_temperature_and_humidity()
        if result and result[0] is not None:
            _weather_cache["temp"] = result[0]
            _weather_cache["ts"] = now
            return result[0]
    except Exception:
        pass
    return _weather_cache["temp"]


def draw_clock(surface):
    draw.fill_background(surface)
    now = datetime.now()
    use_12 = CLOCK_FORMAT.strip().lower() == "12hr"

    if use_12:
        time_str = now.strftime("%I:%M").lstrip("0") or "12"
        ampm = now.strftime("%p")
    else:
        time_str = now.strftime("%H:%M")
        ampm = ""

    date_str = now.strftime("%a %b %d, %Y")
    tz_name = time.tzname[0] if time.tzname else "Local"

    temp = _fetch_temperature()
    temp_line = ""
    if temp is not None:
        unit = "°F" if TEMPERATURE_UNITS == "imperial" else "°C"
        temp_line = f"{int(round(temp))}{unit}"

    time_font = draw.load_font(theme.FONT_CLOCK, bold=True)
    ampm_font = draw.load_font(theme.FONT_BODY, bold=True)
    body_font = draw.load_font(theme.FONT_BODY)
    detail_font = draw.load_font(theme.FONT_DETAIL)

    block_h = theme.s(280)
    y = theme.CENTER_Y - block_h // 2

    if ampm:
        time_w = time_font.size(time_str)[0]
        ampm_w = ampm_font.size(ampm)[0]
        gap = theme.s(8)
        total_w = time_w + gap + ampm_w
        x = theme.CENTER_X - total_w // 2
        bottom = y + time_font.get_height()
        surface.blit(time_font.render(time_str, True, theme.SWEEP), (x, y))
        surface.blit(ampm_font.render(ampm, True, theme.SWEEP), (x + time_w + gap, bottom - ampm_font.get_height()))
        y = bottom + theme.s(14)
    else:
        rendered = time_font.render(time_str, True, theme.SWEEP)
        surface.blit(rendered, rendered.get_rect(midtop=(theme.CENTER_X, y)))
        y += time_font.get_height() + theme.s(14)

    y = draw.draw_center_line(surface, date_str, y, body_font, theme.LABEL)
    y += theme.s(4)
    y = draw.draw_center_line(surface, tz_name, y, detail_font, theme.HINT)
    if temp_line:
        y += theme.s(8)
        y = draw.draw_center_line(surface, temp_line, y, body_font, theme.ROUTE)
    y += theme.s(22)
    draw.draw_center_line(surface, "Swipe up — Radar", y, detail_font, theme.HINT)
