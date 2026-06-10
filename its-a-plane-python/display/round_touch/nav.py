"""Navigation chrome — breadcrumbs, page dots, scroll regions, footer hints."""

from __future__ import annotations

import pygame

from display.round_touch import draw, theme

# Settings sub-page labels (must match info.py page constants)
SETTINGS_PAGES = ("Main", "Display", "Theme")


class ScrollState:
    def __init__(self):
        self.offset = 0
        self.max_offset = 0

    def reset(self):
        self.offset = 0
        self.max_offset = 0

    def clamp(self):
        self.offset = max(0, min(self.offset, self.max_offset))

    def step(self, delta: int):
        self.offset += delta
        self.clamp()


def _top_y() -> int:
    # Top of the round dial — stay off the rim where horizontal space is tight.
    return theme.CENTER_Y - int(theme.VISIBLE_RADIUS * 0.68)


def _footer_top_y() -> int:
    return theme.CENTER_Y + int(theme.VISIBLE_RADIUS * 0.59)


def _max_text_width(y: int, font_height: int) -> int:
    return max(40, draw.circle_half_width_at_row(y, font_height) * 2 - theme.s(8))


def _fit_breadcrumb_parts(parts: list[str], font: pygame.font.Font, max_w: int) -> list[str]:
    sep = " › "
    if not parts:
        return parts
    for start in range(len(parts)):
        trial = parts[start:]
        while trial:
            line = sep.join(trial)
            if font.size(line)[0] <= max_w:
                return trial
            if len(trial) <= 1:
                return [draw.fit_text(trial[0], font, max_w)]
            trial = trial[1:]
    return [draw.fit_text(parts[-1], font, max_w)]


def content_top_y(has_dots: bool = False) -> int:
    if has_dots:
        return _top_y() + theme.s(28) + theme.s(10)
    return _top_y() + theme.s(36)


def content_bottom_y() -> int:
    font = draw.load_font(theme.FONT_DETAIL)
    return _footer_top_y() - font.get_height() - theme.s(6)


def scroll_step() -> int:
    return theme.s(36)


def draw_breadcrumb(surface: pygame.Surface, parts: list[str]):
    if not parts:
        return
    font = draw.load_font(theme.FONT_DETAIL)
    sep_str = " › "
    sep = font.render(sep_str, True, theme.HINT)
    y = _top_y()
    h = font.get_height()
    max_w = _max_text_width(y, h)
    display = _fit_breadcrumb_parts(parts, font, max_w)

    rendered = []
    total_w = 0
    for i, part in enumerate(display):
        color = theme.SWEEP if i == len(display) - 1 else theme.MUTED
        used = total_w + (sep.get_width() if rendered else 0)
        remaining = max(20, max_w - used)
        text = draw.fit_text(part, font, remaining)
        img = font.render(text, True, color)
        rendered.append(img)
        total_w += img.get_width()
        if i < len(display) - 1:
            total_w += sep.get_width()

    if total_w > max_w:
        line = draw.fit_text(sep_str.join(parts), font, max_w)
        img = font.render(line, True, theme.MUTED)
        surface.blit(img, img.get_rect(midtop=(theme.CENTER_X, y)))
        return

    x = theme.CENTER_X - total_w // 2
    for i, img in enumerate(rendered):
        surface.blit(img, (x, y))
        x += img.get_width()
        if i < len(rendered) - 1:
            surface.blit(sep, (x, y))
            x += sep.get_width()


def draw_page_dots(surface: pygame.Surface, active: int, total: int, y: int | None = None):
    if total <= 1:
        return
    if y is None:
        y = _top_y() + theme.s(30)
    gap = theme.s(14)
    r = max(2, theme.s(4))
    span = (total - 1) * gap
    x0 = theme.CENTER_X - span // 2
    for i in range(total):
        cx = x0 + i * gap
        color = theme.SWEEP if i == active else theme.GRID
        pygame.draw.circle(surface, color, (cx, y), r)


def draw_footer(surface: pygame.Surface, hints: list[str]):
    if not hints:
        return
    font = draw.load_font(theme.FONT_DETAIL)
    y = _footer_top_y()
    h = font.get_height()
    max_w = _max_text_width(y, h)
    slot_w = max_w // len(hints)
    rendered = []
    for hint in hints:
        text = draw.fit_text(hint, font, max(20, slot_w - theme.s(4)))
        rendered.append(font.render(text, True, theme.HINT))
    total_w = sum(img.get_width() for img in rendered)
    spacing = max(theme.s(8), (max_w - total_w) // max(1, len(hints) - 1))
    x = theme.CENTER_X - (total_w + spacing * (len(hints) - 1)) // 2
    for img in rendered:
        surface.blit(img, (x, y))
        x += img.get_width() + spacing


def breadcrumb_rect() -> pygame.Rect:
    font = draw.load_font(theme.FONT_DETAIL)
    y = _top_y()
    h = font.get_height()
    half_w = draw.circle_half_width_at_row(y, h)
    return pygame.Rect(
        theme.CENTER_X - half_w,
        y - theme.s(4),
        half_w * 2,
        h + theme.s(8),
    )


def tap_breadcrumb(x: int, y: int) -> bool:
    """Tap the breadcrumb bar to go back toward Radar."""
    return breadcrumb_rect().collidepoint(x, y)


def measure_lines(lines: list[str], font: pygame.font.Font, gap: int | None = None) -> int:
    if not lines:
        return 0
    gap = theme.s(4) if gap is None else gap
    return len(lines) * (font.get_height() + gap) - gap


def draw_lines_scrolled(
    surface: pygame.Surface,
    lines: list[str],
    font: pygame.font.Font,
    color,
    scroll_offset: int,
    *,
    start_y: int | None = None,
    top: int | None = None,
    bottom: int | None = None,
    gap: int | None = None,
    center: bool = True,
) -> int:
    """Draw lines in the content band; return max scroll offset."""
    gap = theme.s(4) if gap is None else gap
    top = content_top_y() if top is None else top
    bottom = content_bottom_y() if bottom is None else bottom
    start_y = top if start_y is None else start_y
    viewport_h = max(0, bottom - top)
    total_h = measure_lines(lines, font, gap)
    max_scroll = max(0, total_h - viewport_h)

    y = start_y - scroll_offset
    row_h = font.get_height() + gap
    for line in lines:
        if top - row_h <= y <= bottom:
            if center:
                draw.draw_center_line(surface, line, y, font, color)
            else:
                max_w = draw.circle_half_width_at_row(y, font.get_height()) * 2
                text = draw.fit_text(line, font, max_w)
                rendered = font.render(text, True, color)
                surface.blit(rendered, rendered.get_rect(midtop=(theme.CENTER_X, y)))
        y += row_h
    return max_scroll
