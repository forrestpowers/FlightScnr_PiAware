"""
Configuration — all values sourced exclusively from environment variables.

NO user-configurable defaults are stored in this file.
All configuration must be provided via:
  - /etc/plane-tracker.env (systemd EnvironmentFile for production)
  - .env file in the project root (for local development via python-dotenv)

See .env.example for documentation of all available variables and their defaults.
"""
import math
import os

# Load .env file if present (for local dev; systemd uses EnvironmentFile instead)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
except ImportError:
    pass


def _bool(val: str) -> bool:
    return val.strip().lower() in ("true", "1", "yes", "on")


def _require(name: str) -> str:
    """Return env var value or empty string (caller decides how to handle missing)."""
    return os.environ.get(name, "")


def _float_env(name: str):
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    return float(raw)


def _zone_from_home(lat: float, lon: float, radius_nm: float) -> dict:
    """Build a square bounding box from home coordinates and radius in nautical miles."""
    lat_delta = radius_nm / 60.0
    lon_delta = radius_nm / (60.0 * max(0.01, math.cos(math.radians(lat))))
    return {
        "tl_y": lat + lat_delta,
        "tl_x": lon - lon_delta,
        "br_y": lat - lat_delta,
        "br_x": lon + lon_delta,
    }


def _resolve_location():
    """Resolve home point and search zone from env vars."""
    zone = {
        "tl_y": _float_env("ZONE_TL_LAT"),
        "tl_x": _float_env("ZONE_TL_LON"),
        "br_y": _float_env("ZONE_BR_LAT"),
        "br_x": _float_env("ZONE_BR_LON"),
    }
    home_lat = _float_env("HOME_LAT")
    home_lon = _float_env("HOME_LON")
    radius_nm = float(os.environ.get("SEARCH_RADIUS_NM", "15"))

    if all(v is not None for v in zone.values()):
        if home_lat is None or home_lon is None:
            home_lat = (zone["tl_y"] + zone["br_y"]) / 2
            home_lon = (zone["tl_x"] + zone["br_x"]) / 2
        return [home_lat, home_lon], zone, "zone_corners"

    if home_lat is not None and home_lon is not None:
        return [home_lat, home_lon], _zone_from_home(home_lat, home_lon, radius_nm), "home_radius"

    return [0.0, 0.0], {"tl_y": 0.0, "tl_x": 0.0, "br_y": 0.0, "br_x": 0.0}, "unset"


# --- API Keys ---
FR24_API_KEY = _require("FR24_API_KEY")
TOMORROW_API_KEY = _require("TOMORROW_API_KEY")
AIRLABS_API_KEY = os.environ.get("AIRLABS_API_KEY", "")

# --- Location (zone + home) ---
LOCATION_HOME, ZONE_HOME, LOCATION_SOURCE = _resolve_location()
SEARCH_RADIUS_NM = float(os.environ.get("SEARCH_RADIUS_NM", "15"))
ADSB_ENABLED = _bool(os.environ.get("ADSB_ENABLED", "True"))
DATA_REFRESH_SECONDS = float(os.environ.get("DATA_REFRESH_SECONDS", "2"))


def location_configured() -> bool:
    return LOCATION_SOURCE != "unset"


def location_status() -> str:
    if not location_configured():
        return "Location not set — edit /etc/plane-tracker.env"
    if LOCATION_SOURCE == "home_radius":
        return f"Searching {SEARCH_RADIUS_NM:g}nm around home"
    return "Searching configured zone"

# --- Weather ---
TEMPERATURE_LOCATION = _require("TEMPERATURE_LOCATION")
if not TEMPERATURE_LOCATION and location_configured():
    TEMPERATURE_LOCATION = f"{LOCATION_HOME[0]},{LOCATION_HOME[1]}"
TEMPERATURE_UNITS = os.environ.get("TEMPERATURE_UNITS", "metric")
FORECAST_DAYS = int(os.environ.get("FORECAST_DAYS", "3"))

# --- Display & units ---
DISPLAY_WIDTH = int(os.environ.get("DISPLAY_WIDTH", "1080"))
DISPLAY_HEIGHT = int(os.environ.get("DISPLAY_HEIGHT", "1080"))
DISPLAY_FULLSCREEN = _bool(os.environ.get("DISPLAY_FULLSCREEN", "True"))
SDL_VIDEODRIVER = os.environ.get("SDL_VIDEODRIVER", "")

DISTANCE_UNITS = os.environ.get("DISTANCE_UNITS", "metric")
CLOCK_FORMAT = os.environ.get("CLOCK_FORMAT", "24hr")
BRIGHTNESS = int(os.environ.get("BRIGHTNESS", "100"))
BRIGHTNESS_NIGHT = int(os.environ.get("BRIGHTNESS_NIGHT", "50"))
NIGHT_BRIGHTNESS = _bool(os.environ.get("NIGHT_BRIGHTNESS", "False"))
NIGHT_START = os.environ.get("NIGHT_START", "22:00")
NIGHT_END = os.environ.get("NIGHT_END", "06:00")

# --- Flight filtering (altitude in feet) ---
MAX_ALTITUDE_FT = 100000
_raw_min_alt = os.environ.get("MIN_HEIGHT", os.environ.get("MIN_ALTITUDE", "0"))
MIN_ALTITUDE = int(_raw_min_alt)
MIN_HEIGHT = MIN_ALTITUDE  # alias used in .env / UI wording


def passes_altitude_filter(alt_ft) -> bool:
    """True if aircraft altitude is at or above MIN_HEIGHT and within max."""
    if alt_ft is None:
        return MIN_ALTITUDE <= 0
    try:
        alt = int(alt_ft)
    except (TypeError, ValueError):
        return MIN_ALTITUDE <= 0
    return MIN_ALTITUDE <= alt < MAX_ALTITUDE_FT
JOURNEY_CODE_SELECTED = _require("JOURNEY_CODE_SELECTED")
_raw_filler = os.environ.get("JOURNEY_BLANK_FILLER", "").strip()
JOURNEY_BLANK_FILLER = f" {_raw_filler} " if _raw_filler else " ? "
SPEED_UNITS = os.environ.get("SPEED_UNITS", "metric")

# --- Logging & notifications ---
EMAIL = os.environ.get("EMAIL", "")
MAX_FARTHEST = int(os.environ.get("MAX_FARTHEST", "3"))
MAX_CLOSEST = int(os.environ.get("MAX_CLOSEST", "3"))
