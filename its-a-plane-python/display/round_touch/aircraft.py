"""Top-down aircraft icon (FlightScnr aircraft_symbol)."""

import math
import pygame

from display.round_touch import theme


def _rotate(x, y, heading_deg):
    rad = math.radians(heading_deg)
    sin_h = math.sin(rad)
    cos_h = math.cos(rad)
    rx = x * cos_h - y * sin_h
    ry = x * sin_h + y * cos_h
    return rx, ry


def _map_local(lx, ly, cx, cy, heading_deg):
    rx, ry = _rotate(lx, ly, heading_deg)
    return int(round(cx + rx)), int(round(cy + ry))


def draw_plane_icon(surface, cx, cy, heading_deg, color, compact=False):
    scale = 0.55 if compact else 1.0
    nose_y = int(-11 * scale)
    wing_y = int(-1 * scale)
    wing_x = int(7 * scale)
    tail_y = int(5 * scale)
    fin_y = int(7 * scale)

    def line(x0, y0, x1, y1, w=2):
        p0 = _map_local(x0, y0, cx, cy, heading_deg)
        p1 = _map_local(x1, y1, cx, cy, heading_deg)
        pygame.draw.line(surface, color, p0, p1, w)

    line(0, nose_y, 0, tail_y, 3)
    line(-wing_x, wing_y, 0, nose_y, 2)
    line(wing_x, wing_y, 0, nose_y, 2)
    line(-2, fin_y, 2, fin_y, 2)

    nose_pts = [
        _map_local(0, nose_y, cx, cy, heading_deg),
        _map_local(-2, nose_y + 2, cx, cy, heading_deg),
        _map_local(2, nose_y + 2, cx, cy, heading_deg),
    ]
    pygame.draw.polygon(surface, color, nose_pts)

    tail_pts = [
        _map_local(0, fin_y, cx, cy, heading_deg),
        _map_local(-2, tail_y, cx, cy, heading_deg),
        _map_local(2, tail_y, cx, cy, heading_deg),
    ]
    pygame.draw.polygon(surface, color, tail_pts)


def format_altitude(alt_ft) -> str:
    if alt_ft is None:
        return "—"
    try:
        alt = int(alt_ft)
    except (TypeError, ValueError):
        return "—"
    if alt <= 0:
        return "—"
    if alt >= 18000:
        return f"FL{round(alt / 100)}"
    return f"{alt:,}ft"


def altitude_tag_color(vertical_speed):
    if vertical_speed is not None and vertical_speed < -64:
        return theme.TAG_ALT_DESCEND
    return theme.TAG_ALT_ASCEND
