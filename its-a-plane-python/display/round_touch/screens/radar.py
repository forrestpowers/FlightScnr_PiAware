"""Radar screen — FlightScnr-style sweep and aircraft markers."""

import math
import time

import pygame

from display.round_touch import aircraft, draw, geo, scale, settings, theme


_sweep_angle = 0.0
_sweep_last_ms = 0


def _init_sweep():
    global _sweep_angle, _sweep_last_ms
    _sweep_angle = 0.0
    _sweep_last_ms = time.time() * 1000


def tick_sweep():
    global _sweep_angle, _sweep_last_ms
    now = time.time() * 1000
    if _sweep_last_ms == 0:
        _sweep_last_ms = now
        return
    dt = now - _sweep_last_ms
    _sweep_last_ms = now
    _sweep_angle = (_sweep_angle + 360.0 * dt / theme.SWEEP_PERIOD_MS) % 360.0


def _draw_grid(surface):
    center = (theme.CENTER_X, theme.CENTER_Y)
    for ring in range(1, theme.RING_COUNT + 1):
        r = theme.GRID_OUTER_RADIUS * ring // theme.RING_COUNT
        draw.draw_dashed_circle(surface, center, r, theme.GRID, width=max(1, theme.s(2)))

    if settings.show_compass_rose():
        font = draw.load_font(theme.FONT_CARDINAL, bold=True)
        labels = [
            ("N", theme.CENTER_X, theme.CARDINAL_NORTH_OFFSET_Y),
            ("S", theme.CENTER_X, theme.SIZE - theme.CARDINAL_SOUTH_OFFSET_Y - font.get_height()),
            ("W", theme.s(10), theme.CENTER_Y - font.get_height() // 2),
            ("E", theme.SIZE - theme.s(10) - font.size("E")[0], theme.CENTER_Y - font.get_height() // 2),
        ]
        for text, x, y in labels:
            rendered = font.render(text, True, theme.LABEL)
            if text in ("N", "S"):
                rect = rendered.get_rect(midtop=(x, y))
            elif text == "W":
                rect = rendered.get_rect(midleft=(x, y))
            else:
                rect = rendered.get_rect(topleft=(x, y))
            surface.blit(rendered, rect)

        diag_r = theme.GRID_OUTER_RADIUS - theme.CARDINAL_DIAGONAL_INSET
        for label, angle in (("NE", 45), ("SE", 135), ("SW", 225), ("NW", 315)):
            rad = math.radians(angle - 90)
            x = theme.CENTER_X + int(diag_r * math.cos(rad))
            y = theme.CENTER_Y + int(diag_r * math.sin(rad))
            rendered = font.render(label, True, theme.LABEL)
            rect = rendered.get_rect(center=(x, y))
            surface.blit(rendered, rect)

    use_miles = settings.distance_in_miles()
    scale_font = draw.load_font(theme.FONT_DETAIL)
    outer_km = scale.active_band()["label_km"]
    for ring in range(1, theme.RING_COUNT + 1):
        ring_km = outer_km * ring / theme.RING_COUNT
        label = scale.format_scale_tag(ring_km, use_miles)
        r = theme.GRID_OUTER_RADIUS * ring // theme.RING_COUNT
        gap = theme.SCALE_GAP_OUTER_RING_KM if ring == theme.RING_COUNT and not use_miles else theme.SCALE_GAP_FROM_OUTER_RING
        label_r = r - gap
        rad = math.radians(theme.SCALE_LABEL_BEARING_DEG - 90)
        x = theme.CENTER_X + int(label_r * math.cos(rad))
        y = theme.CENTER_Y + int(label_r * math.sin(rad))
        rendered = scale_font.render(label, True, theme.LABEL)
        surface.blit(rendered, rendered.get_rect(center=(x, y)))


def _draw_aircraft_tag(surface, x, y, flight):
    tag_font = draw.load_font(theme.FONT_TAG, bold=True)
    callsign = flight.get("callsign") or "—"
    plane_type = flight.get("plane") or ""
    alt = aircraft.format_altitude(flight.get("altitude"))
    alt_color = aircraft.altitude_tag_color(flight.get("vertical_speed"))

    line_h = tag_font.get_height()
    block_h = line_h * 3
    ly = y - block_h // 2
    tag_on_right = x < theme.CENTER_X
    symbol_half = theme.AIRCRAFT_ICON_RADIUS

    if tag_on_right:
        anchor_x = min(x + symbol_half + theme.AIRCRAFT_LABEL_GAP, theme.SIZE - 200)
        align = "left"
    else:
        anchor_x = max(x - symbol_half - theme.AIRCRAFT_LABEL_GAP, 200)
        align = "right"

    lines = [
        (callsign, theme.LABEL),
        (plane_type, theme.TAG_TYPE),
        (alt, alt_color),
    ]
    for i, (text, color) in enumerate(lines):
        if not text or text == "—" and i == 1:
            continue
        rendered = tag_font.render(text, True, color)
        if align == "left":
            surface.blit(rendered, (anchor_x, ly + i * line_h))
        else:
            surface.blit(rendered, rendered.get_rect(topright=(anchor_x, ly + i * line_h)))


def _above_min_height(flight) -> bool:
    try:
        from config import passes_altitude_filter
        return passes_altitude_filter(flight.get("altitude"))
    except ImportError:
        return True


def _visible_flights(flights):
    return [f for f in flights if _above_min_height(f)]


def _draw_flights(surface, flights):
    for flight in _visible_flights(flights):
        lat = flight.get("plane_latitude")
        lon = flight.get("plane_longitude")
        if lat is None or lon is None:
            continue
        heading = flight.get("heading") or 0
        _, _, dist_km = geo.local_offset_km(lat, lon)
        if dist_km <= geo.inner_ring_max_km():
            x, y = geo.lat_lon_to_screen(lat, lon)
            aircraft.draw_plane_icon(surface, x, y, heading, theme.AIRCRAFT)
            _draw_aircraft_tag(surface, x, y, flight)
        else:
            pos = geo.beyond_ring_position(lat, lon)
            if pos:
                aircraft.draw_plane_icon(surface, pos[0], pos[1], heading, theme.AIRCRAFT, compact=True)


def _draw_status(surface, flights):
    try:
        from config import location_configured, location_status
    except ImportError:
        return

    font = draw.load_font(theme.FONT_DETAIL)
    if not location_configured():
        lines = [
            "No location configured",
            "Set HOME_LAT & HOME_LON",
            "in /etc/plane-tracker.env",
        ]
        color = theme.TAG_ALT_DESCEND
    visible = _visible_flights(flights)
    if not visible:
        try:
            from config import MIN_HEIGHT
            min_line = f"Min height: {MIN_HEIGHT} ft" if MIN_HEIGHT else ""
        except ImportError:
            min_line = ""
        lines = [
            location_status(),
            "No aircraft in range",
        ]
        if min_line:
            lines.append(min_line)
        else:
            lines.append("Waiting for ADS-B / FR24…")
        color = theme.HINT
    else:
        lines = [f"{len(visible)} aircraft"]
        color = theme.SWEEP
        y = theme.s(20)
        for line in lines:
            rendered = font.render(line, True, color)
            surface.blit(rendered, rendered.get_rect(midtop=(theme.CENTER_X, y)))
        return

    y = theme.CENTER_Y - theme.s(30)
    for line in lines:
        y = draw.draw_center_line(surface, line, y, font, color)


def draw_radar(surface, flights, full_redraw=True):
    if full_redraw:
        draw.fill_background(surface)
        _draw_grid(surface)
    else:
        # Redraw grid area only (simple full redraw each sweep frame is fine at 1080)
        draw.fill_background(surface)
        _draw_grid(surface)

    _draw_flights(surface, flights)
    draw.draw_sweep_line(surface, _sweep_angle, theme.SWEEP, width=max(2, theme.s(2)))

    tag_font = draw.load_font(theme.FONT_DETAIL)
    scale_label = scale.format_active_tag(settings.distance_in_miles())
    tag = tag_font.render(scale_label, True, theme.SWEEP)
    surface.blit(tag, tag.get_rect(bottomright=(theme.SIZE - theme.s(16), theme.SIZE - theme.s(12))))
    _draw_status(surface, flights)


def pick_flight_at(flights, tap_x, tap_y):
    best = None
    best_d2 = theme.TAP_PICK_RADIUS ** 2
    for flight in _visible_flights(flights):
        lat = flight.get("plane_latitude")
        lon = flight.get("plane_longitude")
        if lat is None or lon is None:
            continue
        x, y = geo.lat_lon_to_screen(lat, lon)
        d2 = (x - tap_x) ** 2 + (y - tap_y) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best = flight
    return best


def flights_by_distance(flights):
    def dist_key(f):
        lat = f.get("plane_latitude")
        lon = f.get("plane_longitude")
        if lat is None or lon is None:
            return 1e9
        return geo.local_offset_km(lat, lon)[2]

    return sorted(_visible_flights(flights), key=dist_key)
