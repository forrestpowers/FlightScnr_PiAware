"""Flight detail screen."""

import pygame

from display.round_touch import aircraft, draw, geo, theme


def draw_flight_detail(surface, flights, selected_index):
    draw.fill_background(surface)
    title_font = draw.load_font(theme.FONT_TITLE, bold=True)
    body_font = draw.load_font(theme.FONT_BODY)
    detail_font = draw.load_font(theme.FONT_DETAIL)
    hint_font = detail_font

    if not flights:
        y = theme.CENTER_Y - theme.s(40)
        y = draw.draw_center_line(surface, "Flight", y, title_font, theme.LABEL)
        y = draw.draw_center_line(surface, "No aircraft", y, body_font, theme.MUTED)
        draw.draw_center_line(surface, "Swipe right for radar", y, hint_font, theme.HINT)
        return

    idx = max(0, min(selected_index, len(flights) - 1))
    f = flights[idx]
    callsign = f.get("callsign") or "—"
    airline = f.get("airline") or "Airline unknown"
    origin = f.get("origin") or "—"
    dest = f.get("destination") or "—"
    plane_type = f.get("plane") or "—"
    alt = aircraft.format_altitude(f.get("altitude"))
    speed = f.get("ground_speed") or 0
    speed_line = f"Speed: {int(round(speed))} kt" if speed > 0 else "Speed: —"
    index_line = f"{idx + 1} / {len(flights)}"

    lat = f.get("plane_latitude")
    lon = f.get("plane_longitude")
    dist_line = ""
    if lat is not None and lon is not None:
        _, _, dist_km = geo.local_offset_km(lat, lon)
        if dist_km >= 1:
            dist_line = f"Distance: {dist_km:.1f} km"
        else:
            dist_line = f"Distance: {dist_km * 1000:.0f} m"

    y = theme.CENTER_Y - theme.s(180)
    y = draw.draw_center_line(surface, "Flight Detail", y, title_font, theme.LABEL)
    y += theme.s(6)
    y = draw.draw_center_line(surface, callsign, y, body_font, theme.LABEL)
    y = draw.draw_center_line(surface, airline, y, body_font, theme.MUTED)
    y += theme.s(6)
    route = f"{origin} > {dest}"
    y = draw.draw_center_line(surface, route, y, body_font, theme.ROUTE)
    y = draw.draw_center_line(surface, plane_type, y, detail_font, theme.TAG_TYPE)
    y = draw.draw_center_line(surface, alt, y, detail_font, theme.TAG_ALT_ASCEND)
    y = draw.draw_center_line(surface, speed_line, y, detail_font, theme.LABEL)
    if dist_line:
        y = draw.draw_center_line(surface, dist_line, y, detail_font, theme.MUTED)
    y += theme.s(12)
    draw.draw_center_line(surface, index_line, y, detail_font, theme.HINT)
    y += theme.s(16)
    draw.draw_center_line(surface, "Scroll / swipe — cycle flights", y, hint_font, theme.HINT)
    y = draw.draw_center_line(surface, "Swipe right — radar", y, hint_font, theme.HINT)
