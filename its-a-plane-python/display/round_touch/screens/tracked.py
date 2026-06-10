"""Tracked flight screen — route, progress bar, and live stats."""

from __future__ import annotations

import socket

import pygame

try:
    from config import CLOCK_FORMAT, DISTANCE_UNITS
except ImportError:
    CLOCK_FORMAT = "24hr"
    DISTANCE_UNITS = "metric"

from display.round_touch import aircraft, draw, logos, nav, settings, theme
from utilities.overhead import load_tracked_callsign

# Nearest-city cache (matches scenes/trackedstats.py)
_city_cache = {"lat": None, "lon": None, "result": None}
_CITY_CACHE_THRESHOLD = 0.01

def tracking_active() -> bool:
    return bool(load_tracked_callsign())


def _delay_color(real, scheduled, *, is_arrival: bool = False):
    if real is None or scheduled in (None, 0):
        return theme.MUTED
    delay = (real - scheduled) / 60
    if is_arrival:
        if delay <= 0:
            return theme.SWEEP
        if delay <= 30:
            return theme.TAG_TYPE
        if delay <= 60:
            return theme.AIRCRAFT
        if delay <= 240:
            return theme.TAG_ALT_DESCEND
        return theme.ROUTE
    if delay <= 20:
        return theme.SWEEP
    if delay <= 40:
        return theme.TAG_TYPE
    if delay <= 60:
        return theme.AIRCRAFT
    if delay <= 240:
        return theme.TAG_ALT_DESCEND
    return theme.ROUTE


def _calc_progress(data) -> float:
    dist_remaining = data.get("dist_remaining")
    total_distance = data.get("total_distance")
    if dist_remaining is None:
        return 0.0
    if not total_distance or total_distance <= 0:
        return 0.0
    dist_flown = total_distance - dist_remaining
    return max(0.0, min(1.0, dist_flown / total_distance))


def _format_dep_time(dep_time_str: str) -> str:
    if not dep_time_str:
        return ""
    try:
        parts = dep_time_str.split(" ")
        if len(parts) < 2:
            return dep_time_str
        hm = parts[1].split(":")
        hour = int(hm[0])
        minute = int(hm[1]) if len(hm) > 1 else 0
        if CLOCK_FORMAT == "12hr":
            ampm = "a" if hour < 12 else "p"
            display_hour = hour % 12 or 12
            if minute:
                return f"{display_hour}:{minute:02d}{ampm}"
            return f"{display_hour}{ampm}"
        return f"{hour}:{minute:02d}"
    except (ValueError, IndexError):
        return dep_time_str


def _format_dist_remaining(dist) -> str | None:
    """Format distance remaining using display units from Settings → Display."""
    if dist is None:
        return None
    use_miles = settings.distance_in_miles()
    stored_km = DISTANCE_UNITS == "metric"
    value = float(dist)
    if stored_km and use_miles:
        value /= 1.609344
    elif not stored_km and not use_miles:
        value *= 1.609344
    unit = "mi" if use_miles else "km"
    return f"{int(value)}{unit}"


def _format_speed(ground_speed):
    """Format ground speed using display units from Settings → Display."""
    if ground_speed is None or ground_speed <= 0:
        return None
    kts = float(ground_speed)
    if settings.distance_in_miles():
        return f"{int(kts * 1.15078)} mph"
    return f"{int(kts * 1.852)} km/h"


def _nearest_city_label(data) -> str:
    lat = data.get("latitude")
    lon = data.get("longitude")
    if lat is None or lon is None:
        return ""
    if (
        _city_cache["lat"] is None
        or abs(lat - _city_cache["lat"]) > _CITY_CACHE_THRESHOLD
        or abs(lon - _city_cache["lon"]) > _CITY_CACHE_THRESHOLD
    ):
        _city_cache["lat"] = lat
        _city_cache["lon"] = lon
        try:
            from utilities.cities import get_nearest_city

            _city_cache["result"] = get_nearest_city(lat, lon)
        except Exception:
            _city_cache["result"] = None
    nearest = _city_cache["result"]
    if nearest:
        return f"nr {nearest['name']}"
    return ""


def _status_label(data) -> str:
    if data.get("is_scheduled"):
        return "SCHEDULED"
    if not data.get("is_live", True):
        return "ESTIMATED"
    return "LIVE"


def _format_vertical_speed(vs) -> str | None:
    if vs is None:
        return None
    try:
        rate = int(vs)
    except (TypeError, ValueError):
        return None
    if abs(rate) <= 64:
        return None
    return f"{rate:+d} fpm"


def _progress_parts(data) -> list[str]:
    parts: list[str] = []
    if data.get("time_remaining"):
        parts.append(str(data["time_remaining"]))
    dist_str = _format_dist_remaining(data.get("dist_remaining"))
    if dist_str:
        parts.append(dist_str)
    landmark = _nearest_city_label(data)
    if landmark:
        parts.append(landmark)
    return parts


def _telemetry_parts(data) -> list[str]:
    parts: list[str] = []
    aircraft_type = data.get("aircraft_type", "")
    if aircraft_type and aircraft_type not in ("", "N/A"):
        parts.append(aircraft_type)

    alt_str = aircraft.format_altitude(data.get("altitude"))
    if alt_str != "—":
        vs = data.get("vertical_speed", 0) or 0
        if vs > 64:
            alt_str += " ↑"
        elif vs < -64:
            alt_str += " ↓"
        parts.append(alt_str)

    vs_str = _format_vertical_speed(data.get("vertical_speed"))
    if vs_str:
        parts.append(vs_str)

    speed_str = _format_speed(data.get("ground_speed"))
    if speed_str:
        parts.append(speed_str)

    heading = data.get("heading")
    if heading is not None and int(heading) > 0:
        parts.append(f"HDG {int(heading)}°")
    return parts


def _scheduled_rows(data) -> list[tuple[str, tuple[int, int, int]]]:
    dep = _format_dep_time(data.get("dep_time", ""))
    origin = data.get("origin", "")
    dest = data.get("destination", "")
    if dep:
        return [(f"Departs {dep}  {origin} → {dest}", theme.ROUTE)]
    return [(f"Scheduled  {origin} → {dest}", theme.ROUTE)]


def _build_stats_rows_compact(data) -> list[tuple[str, tuple[int, int, int]]]:
    """Two rows: status+progress, then aircraft+telemetry."""
    if data.get("is_scheduled"):
        return _scheduled_rows(data)

    rows: list[tuple[str, tuple[int, int, int]]] = []
    status = _status_label(data)
    status_color = theme.SWEEP if status == "LIVE" else theme.TAG_TYPE
    head = [status, *_progress_parts(data)]
    rows.append(("  ·  ".join(head), status_color))

    telemetry = _telemetry_parts(data)
    if telemetry:
        rows.append(("  ·  ".join(telemetry), theme.LABEL))
    return rows


def _build_stats_rows_scroll(data) -> list[tuple[str, tuple[int, int, int]]]:
    """Four rows: status, progress, aircraft type, telemetry."""
    if data.get("is_scheduled"):
        return _scheduled_rows(data)

    rows: list[tuple[str, tuple[int, int, int]]] = []
    status = _status_label(data)
    status_color = theme.SWEEP if status == "LIVE" else theme.TAG_TYPE
    rows.append((status, status_color))

    progress = _progress_parts(data)
    if progress:
        rows.append(("  ·  ".join(progress), theme.LABEL))

    aircraft_type = data.get("aircraft_type", "")
    if aircraft_type and aircraft_type not in ("", "N/A"):
        rows.append((aircraft_type, theme.TAG_TYPE))

    telemetry = _telemetry_parts(data)
    if telemetry:
        rows.append(("  ·  ".join(telemetry), theme.LABEL))
    return rows


def _build_stats_rows(data) -> list[tuple[str, tuple[int, int, int]]]:
    if settings.tracked_stats_mode() == settings.TRACKED_STATS_SCROLL:
        return _build_stats_rows_scroll(data)
    return _build_stats_rows_compact(data)


def _draw_logo(surface, callsign: str, y: int) -> int:
    size = theme.s(36)
    logo = logos.load_logo_surface(
        logos.icao_for_flight({"callsign": callsign}),
        size,
    )
    if logo is None:
        return y
    rect = logo.get_rect(midtop=(theme.CENTER_X, y))
    surface.blit(logo, rect)
    return y + rect.height + theme.s(4)


def _stats_row_gap(*, compact: bool) -> int:
    return theme.s(1) if compact else theme.s(6)


def _stats_rows_height(rows, font, *, compact: bool) -> int:
    if not rows:
        return 0
    gap = _stats_row_gap(compact=compact)
    h = font.get_height()
    return len(rows) * (h + gap) - gap


def _draw_stats_rows_at(surface, rows, y: int, font, *, compact: bool) -> int:
    gap = _stats_row_gap(compact=compact)
    h = font.get_height()
    for text, color in rows:
        max_w = draw.circle_half_width_at_row(int(y), h) * 2
        line = draw.fit_text(text, font, max_w)
        rendered = font.render(line, True, color)
        surface.blit(rendered, rendered.get_rect(midtop=(theme.CENTER_X, int(y))))
        y += h + gap
    return y


def _draw_stats_rows_clipped(
    surface,
    rows,
    stats_top: int,
    bottom: int,
    font,
) -> None:
    """Compact mode — clip stats at the content bottom."""
    gap = _stats_row_gap(compact=True)
    h = font.get_height()
    y = stats_top
    for text, color in rows:
        if y + h > bottom:
            break
        max_w = draw.circle_half_width_at_row(int(y), h) * 2
        line = draw.fit_text(text, font, max_w)
        rendered = font.render(line, True, color)
        surface.blit(rendered, rendered.get_rect(midtop=(theme.CENTER_X, int(y))))
        y += h + gap


def _live_content_height(data, title_font, body_font, detail_font, *, compact: bool) -> int:
    h = theme.s(2)
    h += theme.s(36) + theme.s(4)
    h += title_font.get_height() + (theme.s(2) if compact else theme.s(4))
    h += body_font.get_height() + (theme.s(2) if compact else theme.s(4))
    if not data.get("is_scheduled"):
        icon_pad = theme.s(5 if compact else 8)
        bar_h = theme.s(5 if compact else 6)
        h += icon_pad + bar_h + icon_pad + (theme.s(1) if compact else theme.s(2))
    else:
        h += theme.s(4 if compact else 6)
    h += _stats_rows_height(_build_stats_rows(data), detail_font, compact=compact)
    return h


def _draw_route_header(surface, data, y: int, title_font, body_font, *, compact: bool) -> int:
    airline_name = data.get("airline_name", "")
    number = data.get("number", data.get("callsign", ""))
    flight_num = "".join(ch for ch in number if ch.isnumeric())
    display_name = f"{airline_name} {flight_num}".strip() if airline_name else number
    origin = data.get("origin", "???")
    destination = data.get("destination", "???")

    y = draw.draw_center_line(surface, display_name, y, title_font, theme.LABEL)

    origin_color = _delay_color(
        data.get("time_real_departure"),
        data.get("time_scheduled_departure"),
    )
    dest_color = _delay_color(
        data.get("time_estimated_arrival"),
        data.get("time_scheduled_arrival"),
        is_arrival=True,
    )

    h = body_font.get_height()
    max_w = draw.circle_half_width_at_row(y, h) * 2
    sep = "  →  "
    origin_img = body_font.render(origin, True, origin_color)
    sep_img = body_font.render(sep, True, theme.MUTED)
    dest_img = body_font.render(destination, True, dest_color)
    total_w = origin_img.get_width() + sep_img.get_width() + dest_img.get_width()
    if total_w > max_w:
        y = draw.draw_center_line(surface, f"{origin}{sep}{destination}", y, body_font, theme.ROUTE)
        return y + (theme.s(2) if compact else theme.s(4))

    x = theme.CENTER_X - total_w // 2
    surface.blit(origin_img, (x, y))
    x += origin_img.get_width()
    surface.blit(sep_img, (x, y))
    x += sep_img.get_width()
    surface.blit(dest_img, (x, y))
    return y + h + (theme.s(2) if compact else theme.s(4))


def _draw_progress_bar(surface, data, y: int, *, compact: bool) -> int:
    bar_h = theme.s(5 if compact else 6)
    icon_pad = theme.s(5 if compact else 8)
    half_w = draw.circle_half_width_at_row(y, bar_h + icon_pad * 2)
    bar_w = max(theme.s(80), half_w * 2 - theme.s(16))
    x0 = theme.CENTER_X - bar_w // 2
    bar_y = y + icon_pad
    bar_rect = pygame.Rect(x0, bar_y, bar_w, bar_h)
    pygame.draw.rect(surface, theme.GRID, bar_rect, 1)

    progress = _calc_progress(data)
    is_live = data.get("is_live", True)
    flown_color = theme.SWEEP if is_live else theme.TAG_ALT_DESCEND

    flown_w = int(bar_w * progress)
    if flown_w > 0:
        pygame.draw.rect(surface, flown_color, pygame.Rect(x0, bar_y, flown_w, bar_h))

    if flown_w < bar_w:
        pygame.draw.rect(
            surface,
            theme.GRID,
            pygame.Rect(x0 + flown_w, bar_y, bar_w - flown_w, bar_h),
            1,
        )

    # Aircraft icon on the bar — nose points toward destination (right).
    margin = theme.s(6)
    usable = max(1, bar_w - margin * 2)
    plane_x = x0 + margin + int(usable * progress)
    plane_y = bar_y + bar_h // 2
    plane_color = theme.AIRCRAFT if is_live else theme.TAG_ALT_DESCEND
    aircraft.draw_progress_plane(surface, plane_x, plane_y, plane_color)

    return bar_y + bar_h + icon_pad


def _draw_empty(surface, top: int, bottom: int):
    title_font = draw.load_font(theme.FONT_TITLE, bold=True)
    body_font = draw.load_font(theme.FONT_BODY)
    detail_font = draw.load_font(theme.FONT_DETAIL)

    y = top + theme.s(12)
    y = draw.draw_center_line(surface, "No tracked flight.", y, title_font, theme.LABEL)
    y += theme.s(6)
    if y + body_font.get_height() <= bottom:
        y = draw.draw_center_line(
            surface,
            "Select a flight on the web portal.",
            y,
            body_font,
            theme.MUTED,
        )
        y += theme.s(6)
    if y + detail_font.get_height() <= bottom:
        host = socket.gethostname().split(".")[0]
        draw.draw_center_line(surface, f"http://{host}.local:8080", y, detail_font, theme.HINT)


def _draw_pending(surface, callsign: str, top: int, bottom: int):
    title_font = draw.load_font(theme.FONT_TITLE, bold=True)
    body_font = draw.load_font(theme.FONT_BODY)
    detail_font = draw.load_font(theme.FONT_DETAIL)

    y = top + theme.s(8)
    y = _draw_logo(surface, callsign, y)
    y = draw.draw_center_line(surface, callsign, y, title_font, theme.LABEL)
    y += theme.s(10)
    if y + body_font.get_height() <= bottom:
        y = draw.draw_center_line(surface, "Waiting for flight data", y, body_font, theme.MUTED)
        y += theme.s(8)
    if y + detail_font.get_height() <= bottom:
        y = draw.draw_center_line(surface, "Starts when flight goes live", y, detail_font, theme.HINT)


def draw_tracked(
    surface,
    tracked_data,
    callsign: str | None = None,
    scroll_offset: int = 0,
) -> int:
    draw.fill_background(surface)
    callsign = (callsign or load_tracked_callsign() or "").strip().upper()
    trail = ["Radar", "Track"]
    if callsign:
        trail.append(callsign)
    nav.draw_breadcrumb(surface, trail)

    top = nav.content_top_y()
    compact = settings.tracked_stats_mode() == settings.TRACKED_STATS_COMPACT
    title_font = draw.load_font(theme.s(20) if compact else theme.FONT_TITLE, bold=True)
    body_font = draw.load_font(theme.s(16) if compact else theme.FONT_BODY)
    detail_font = draw.load_font(theme.s(15) if compact else theme.FONT_DETAIL)
    compact_bottom = nav.content_bottom_y() + theme.s(22)
    scroll_bottom = nav.content_bottom_y()

    if not callsign:
        _draw_empty(surface, top, compact_bottom)
        nav.draw_footer(surface, ["← radar"])
        return 0

    if not tracked_data:
        _draw_pending(surface, callsign, top, compact_bottom)
        nav.draw_footer(surface, ["← radar"])
        return 0

    stats_rows = _build_stats_rows(tracked_data)
    max_scroll = 0

    if compact:
        y = top + theme.s(2)
        y = _draw_logo(surface, tracked_data.get("callsign") or callsign, y)
        y = _draw_route_header(surface, tracked_data, y, title_font, body_font, compact=True)
        if not tracked_data.get("is_scheduled"):
            y = _draw_progress_bar(surface, tracked_data, y, compact=True)
            y += theme.s(1)
        else:
            y += theme.s(4)
        if stats_rows:
            _draw_stats_rows_clipped(surface, stats_rows, y, compact_bottom, detail_font)
        nav.draw_footer(surface, ["← radar"])
        return 0

    viewport_h = scroll_bottom - top
    content_h = _live_content_height(tracked_data, title_font, body_font, detail_font, compact=False)
    max_scroll = max(0, content_h - viewport_h)

    y = top - scroll_offset
    y = _draw_logo(surface, tracked_data.get("callsign") or callsign, y)
    y = _draw_route_header(surface, tracked_data, y, title_font, body_font, compact=False)
    if not tracked_data.get("is_scheduled"):
        y = _draw_progress_bar(surface, tracked_data, y, compact=False)
        y += theme.s(2)
    else:
        y += theme.s(6)
    if stats_rows:
        _draw_stats_rows_at(surface, stats_rows, y, detail_font, compact=False)

    footer = ["↕ scroll", "← radar"] if max_scroll > 0 else ["← radar"]
    nav.draw_footer(surface, footer)
    return max_scroll
