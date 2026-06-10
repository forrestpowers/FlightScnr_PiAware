"""Settings / info screens."""

import socket

import pygame

try:
    from config import LOCATION_HOME
except ImportError:
    LOCATION_HOME = [0.0, 0.0]

from display.round_touch import color_presets, draw, nav, settings, theme

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


def _breadcrumb(page: int) -> list[str]:
    trail = ["Radar", "Settings"]
    if page == PAGE_DISPLAY:
        trail.append("Display")
    elif page == PAGE_COLORS:
        trail.append("Theme")
    return trail


def _footer_hints(page: int, *, scrollable: bool = False) -> list[str]:
    if page == PAGE_MAIN:
        if scrollable:
            return ["← page", "↕ scroll", "radar →"]
        return ["← page", "radar →"]
    if page == PAGE_DISPLAY:
        return ["tap to change", "← back"]
    if page == PAGE_COLORS:
        if scrollable:
            return ["tap to change", "↕ scroll", "← back"]
        return ["tap to change", "← back"]
    return ["tap to change", "← back"]


def _theme_layout(scroll_offset: int) -> tuple[int, int, int]:
    top = nav.content_top_y(has_dots=True)
    title_font = draw.load_font(theme.FONT_TITLE, bold=True)
    title_h = title_font.get_height() + theme.s(6)
    body_font = draw.load_font(theme.FONT_BODY)
    row_h = max(theme.s(24), body_font.get_height()) + theme.s(4)
    return top + title_h - scroll_offset, row_h, color_presets.THEME_COUNT


def theme_row_at(x: int, y: int, scroll_offset: int = 0) -> int | None:
    row_y, row_h, count = _theme_layout(scroll_offset)
    body_font = draw.load_font(theme.FONT_BODY)
    for i in range(count):
        ry = row_y + i * row_h
        half = draw.circle_half_width_at_row(int(ry), body_font.get_height())
        rect = pygame.Rect(
            theme.CENTER_X - half,
            ry - theme.s(2),
            half * 2,
            body_font.get_height() + theme.s(4),
        )
        if rect.collidepoint(x, y):
            return i
    return None


def _display_layout() -> tuple[int, int, int]:
    top = nav.content_top_y(has_dots=True)
    title_font = draw.load_font(theme.FONT_TITLE, bold=True)
    body_font = draw.load_font(theme.FONT_BODY)
    row_y = top + title_font.get_height() + theme.s(12)
    row_h = body_font.get_height() + theme.s(8)
    return row_y, row_h, 5


def display_row_at(x: int, y: int) -> int | None:
    """Return Display settings row index for a tap, or None."""
    row_y, row_h, count = _display_layout()
    body_font = draw.load_font(theme.FONT_BODY)
    for i in range(count):
        ry = row_y + i * row_h
        half = draw.circle_half_width_at_row(int(ry), body_font.get_height())
        rect = pygame.Rect(
            theme.CENTER_X - half,
            ry - theme.s(2),
            half * 2,
            body_font.get_height() + theme.s(4),
        )
        if rect.collidepoint(x, y):
            return i
    return None


def draw_info(surface, page: int, scroll_offset: int = 0, display_focus: int = 0) -> int:
    draw.fill_background(surface)
    nav.draw_breadcrumb(surface, _breadcrumb(page))
    nav.draw_page_dots(surface, page, len(nav.SETTINGS_PAGES))

    title_font = draw.load_font(theme.FONT_TITLE, bold=True)
    body_font = draw.load_font(theme.FONT_BODY)
    top = nav.content_top_y(has_dots=True)
    bottom = nav.content_bottom_y()
    max_scroll = 0

    if page == PAGE_MAIN:
        lines = [
            f"IP: {_local_ip()}",
            f"Host: {_hostname()}.local",
            f"Lat: {LOCATION_HOME[0]:.5f}",
            f"Lon: {LOCATION_HOME[1]:.5f}",
            f"Min height: {settings.min_height_ft()} ft",
            f"Web: http://{_hostname()}.local:8080",
        ]
        detail_font = draw.load_font(theme.FONT_DETAIL)
        gap = theme.s(2)
        title_h = title_font.get_height() + theme.s(4)
        title_y = top
        title = title_font.render("Settings", True, theme.LABEL)
        surface.blit(title, title.get_rect(midtop=(theme.CENTER_X, title_y)))
        body_top = top + title_h
        max_scroll = nav.draw_lines_scrolled(
            surface,
            lines,
            detail_font,
            theme.MUTED,
            scroll_offset,
            start_y=body_top,
            top=body_top,
            bottom=bottom,
            gap=gap,
        )

    elif page == PAGE_DISPLAY:
        units = "miles" if settings.distance_in_miles() else "km"
        rose = "on" if settings.show_compass_rose() else "off"
        track_mode = (
            "scroll"
            if settings.tracked_stats_mode() == settings.TRACKED_STATS_SCROLL
            else "compact"
        )
        rows = [
            f"Brightness: {settings.brightness_percent()}%",
            f"Units: {units}",
            f"Compass Rose: {rose}",
            f"Min height: {settings.min_height_ft()} ft",
            f"Track stats: {track_mode}",
        ]
        y0 = top
        title = title_font.render("Display", True, theme.LABEL)
        surface.blit(title, title.get_rect(midtop=(theme.CENTER_X, y0)))
        y = y0 + title_font.get_height() + theme.s(12)
        row_h = body_font.get_height() + theme.s(8)
        for i, line in enumerate(rows):
            ry = y + i * row_h
            half = draw.circle_half_width_at_row(int(ry), body_font.get_height())
            rect = pygame.Rect(
                theme.CENTER_X - half,
                ry - theme.s(2),
                half * 2,
                body_font.get_height() + theme.s(4),
            )
            if i == display_focus:
                pygame.draw.rect(surface, theme.GRID, rect, 1)
            draw.draw_center_line(surface, line, int(ry), body_font, theme.LABEL)

    else:
        active = settings.theme_index()
        title_h = title_font.get_height() + theme.s(6)
        row_h = max(theme.s(24), body_font.get_height()) + theme.s(4)
        total_h = title_h + color_presets.THEME_COUNT * row_h
        max_scroll = max(0, total_h - (bottom - top))

        y = top - scroll_offset
        if top <= y <= bottom:
            title = title_font.render("Theme", True, theme.LABEL)
            surface.blit(title, title.get_rect(midtop=(theme.CENTER_X, y)))
        y += title_h

        swatch_size = theme.s(20)
        for i, name in enumerate(color_presets.THEME_NAMES):
            ry = y + i * row_h
            if ry + body_font.get_height() < top or ry > bottom:
                continue
            palette = color_presets.THEMES[i]
            accent = palette["sweep"]
            half = draw.circle_half_width_at_row(int(ry), body_font.get_height())
            row_rect = pygame.Rect(
                theme.CENTER_X - half,
                ry - theme.s(2),
                half * 2,
                body_font.get_height() + theme.s(4),
            )
            if i == active:
                pygame.draw.rect(surface, theme.GRID, row_rect, 1)
            label = body_font.render(name, True, theme.LABEL if i == active else theme.MUTED)
            swatch_gap = theme.s(10)
            block_w = swatch_size + swatch_gap + label.get_width()
            sx = theme.CENTER_X - block_w // 2
            swatch_rect = pygame.Rect(sx, int(ry), swatch_size, swatch_size)
            surface.blit(label, (swatch_rect.right + swatch_gap, int(ry)))
            pygame.draw.rect(surface, accent, swatch_rect)
            pygame.draw.rect(surface, palette["grid"], swatch_rect, max(1, theme.s(2)))

    nav.draw_footer(surface, _footer_hints(page, scrollable=max_scroll > 0))
    return max_scroll