"""About / boot splash screen."""

import pygame

from display.round_touch import draw, theme

VERSION = "1.0.0"


def draw_details(surface, boot_splash=False):
    draw.fill_background(surface)
    title_font = draw.load_font(theme.FONT_TITLE, bold=True)
    body_font = draw.load_font(theme.FONT_BODY)
    detail_font = draw.load_font(theme.FONT_DETAIL)

    y = theme.CENTER_Y - theme.s(80)
    y = draw.draw_center_line(surface, f"Plane Tracker v{VERSION}", y, body_font, theme.LABEL)
    y += theme.s(20)
    y = draw.draw_center_line(surface, "UI by FlightScnr", y, body_font, theme.MUTED)
    y = draw.draw_center_line(surface, "Yash Mulgaonkar", y, body_font, theme.MUTED)
    if not boot_splash:
        y += theme.s(22)
        draw.draw_center_line(surface, "Swipe down — Radar", y, detail_font, theme.HINT)
