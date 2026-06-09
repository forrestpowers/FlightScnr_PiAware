"""Settings / info screens."""

import socket

import pygame

try:
    from config import LOCATION_HOME, MIN_HEIGHT
except ImportError:
    LOCATION_HOME = [0.0, 0.0]
    MIN_HEIGHT = 0

from display.round_touch import draw, settings, theme

PAGE_MAIN = 0
PAGE_DISPLAY = 1
PAGE_COLORS = 2


def _hostname():
    return socket.gethostname().split(".")[0]


def _local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "Not connected"


def draw_info(surface, page: int):
    draw.fill_background(surface)
    title_font = draw.load_font(theme.FONT_TITLE, bold=True)
    body_font = draw.load_font(theme.FONT_BODY)
    detail_font = draw.load_font(theme.FONT_DETAIL)

    y = theme.CENTER_Y - theme.s(200)

    if page == PAGE_MAIN:
        y = draw.draw_center_line(surface, "Settings", y, title_font, theme.LABEL)
        y += theme.s(8)
        lines = [
            f"IP: {_local_ip()}",
            f"Host: {_hostname()}.local",
            f"Lat: {LOCATION_HOME[0]:.5f}",
            f"Lon: {LOCATION_HOME[1]:.5f}",
            f"Min height: {MIN_HEIGHT} ft" if MIN_HEIGHT else "Min height: off",
            f"Web: http://{_hostname()}.local:8080",
        ]
        for line in lines:
            y = draw.draw_center_line(surface, line, y, body_font, theme.MUTED)
        y += theme.s(16)
        draw.draw_center_line(surface, "Swipe left — Display settings", y, detail_font, theme.HINT)
        y = draw.draw_center_line(surface, "Swipe right — Radar", y, detail_font, theme.HINT)

    elif page == PAGE_DISPLAY:
        y = draw.draw_center_line(surface, "Display", y, title_font, theme.LABEL)
        y += theme.s(8)
        units = "miles" if settings.distance_in_miles() else "km"
        rose = "on" if settings.show_compass_rose() else "off"
        lines = [
            f"Brightness: {settings.brightness_percent()}%",
            f"Units: {units}",
            f"Compass Rose: {rose}",
        ]
        for line in lines:
            y = draw.draw_center_line(surface, line, y, body_font, theme.LABEL)
        y += theme.s(16)
        draw.draw_center_line(surface, "Scroll — adjust brightness", y, detail_font, theme.HINT)
        y = draw.draw_center_line(surface, "Tap — toggle focused row", y, detail_font, theme.HINT)
        y = draw.draw_center_line(surface, "Swipe left — Colors", y, detail_font, theme.HINT)

    else:
        y = draw.draw_center_line(surface, "Colors", y, title_font, theme.LABEL)
        y += theme.s(8)
        swatches = [
            ("Background", theme.BG),
            ("Grid", theme.GRID),
            ("Sweep", theme.SWEEP),
            ("Aircraft", theme.AIRCRAFT),
            ("Route", theme.ROUTE),
        ]
        for name, color in swatches:
            label = body_font.render(name, True, theme.MUTED)
            rect = pygame.Rect(theme.CENTER_X - theme.s(120), y, theme.s(24), theme.s(24))
            surface.blit(label, (rect.right + theme.s(12), y))
            pygame.draw.rect(surface, color, rect)
            pygame.draw.rect(surface, theme.GRID, rect, 1)
            y += theme.s(32)
        y += theme.s(8)
        draw.draw_center_line(surface, "FlightScnr palette", y, detail_font, theme.HINT)
        y = draw.draw_center_line(surface, "Swipe right — Display", y, detail_font, theme.HINT)
