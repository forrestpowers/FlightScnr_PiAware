"""Drawing helpers for round FlightScnr-style screens."""

import math
import pygame

from display.round_touch import theme


_font_cache = {}


def load_font(size: int, bold=False) -> pygame.font.Font:
    key = (size, bold)
    if key not in _font_cache:
        names = ["dejavusans", "dejavusansmono", "liberationsans", "arial", "sans"]
        font = None
        for name in names:
            path = pygame.font.match_font(name, bold=bold)
            if path:
                font = pygame.font.Font(path, size)
                break
        if font is None:
            font = pygame.font.SysFont(None, size, bold=bold)
        _font_cache[key] = font
    return _font_cache[key]


def circle_half_width_at_row(row_y: int, row_h: int) -> int:
    r = theme.CENTER_X - theme.BEZEL_INSET
    if r <= 0 or row_h <= 0:
        return 0
    row_center = row_y + row_h // 2
    dy = row_center - theme.CENTER_Y
    if abs(dy) >= r:
        return 0
    half = math.sqrt(r * r - dy * dy)
    usable = int(half) - theme.s(6)
    return max(0, usable)


def fit_text(text: str, font: pygame.font.Font, max_width: int) -> str:
    if max_width <= 0 or not text:
        return text
    if font.size(text)[0] <= max_width:
        return text
    for n in range(len(text), 0, -1):
        trial = text[:n] + "…"
        if font.size(trial)[0] <= max_width:
            return trial
    return "…"


def draw_center_line(
    surface: pygame.Surface,
    text: str,
    y: int,
    font: pygame.font.Font,
    color,
    bg=None,
) -> int:
    h = font.get_height()
    max_w = circle_half_width_at_row(y, h) * 2
    line = fit_text(text, font, max_w)
    rendered = font.render(line, True, color, bg)
    rect = rendered.get_rect(midtop=(theme.CENTER_X, y))
    surface.blit(rendered, rect)
    return y + h + theme.s(4)


def draw_dashed_circle(surface, center, radius, color, width=2):
    circumference = 2 * math.pi * radius
    dash = theme.GRID_DASH_LEN
    gap = theme.GRID_DASH_GAP
    step = dash + gap
    if step <= 0:
        return
    segments = max(8, int(circumference / step))
    for i in range(segments):
        if (i * step) % (dash + gap) >= dash:
            continue
        a0 = 2 * math.pi * i / segments
        a1 = 2 * math.pi * (i + 1) / segments
        x0 = int(center[0] + radius * math.cos(a0))
        y0 = int(center[1] + radius * math.sin(a0))
        x1 = int(center[0] + radius * math.cos(a1))
        y1 = int(center[1] + radius * math.sin(a1))
        pygame.draw.line(surface, color, (x0, y0), (x1, y1), width)


def draw_sweep_line(surface, angle_deg: float, color, width=2):
    cx, cy = theme.CENTER_X, theme.CENTER_Y
    rad = math.radians(angle_deg - 90)
    x1 = int(cx + theme.SWEEP_RADIUS * math.cos(rad))
    y1 = int(cy + theme.SWEEP_RADIUS * math.sin(rad))
    pygame.draw.line(surface, color, (cx, cy), (x1, y1), width)


def draw_error(surface: pygame.Surface, message: str):
    """Show a persistent error screen instead of closing the display."""
    fill_background(surface)
    title = load_font(theme.FONT_TITLE, bold=True)
    body = load_font(theme.FONT_BODY)
    detail = load_font(theme.FONT_DETAIL)
    y = theme.CENTER_Y - theme.s(100)
    y = draw_center_line(surface, "Display Error", y, title, theme.TAG_ALT_DESCEND)
    y += theme.s(12)
    for line in _wrap_message(message, 40):
        y = draw_center_line(surface, line, y, body, theme.LABEL)
    y += theme.s(20)
    draw_center_line(surface, "Check: journalctl -u plane-tracker -f", y, detail, theme.HINT)


def _wrap_message(text: str, width: int):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if len(trial) <= width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text[:width]]


def fill_background(surface: pygame.Surface):
    surface.fill(theme.BG)
