"""Persisted UI settings for round touch display."""

import json
import os

DATA_DIR = os.environ.get("PLANE_TRACKER_DATA_DIR", "/var/lib/plane-tracker")
SETTINGS_PATH = os.path.join(DATA_DIR, "round_touch_settings.json")

_defaults = {
    "brightness_percent": 100,
    "distance_miles": False,
    "show_compass_rose": True,
    "scale_index": 1,
}


def _load():
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
            return {**_defaults, **data}
    except (OSError, json.JSONDecodeError, TypeError):
        return dict(_defaults)


def _save(data):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


_state = _load()


def brightness_percent():
    return int(_state.get("brightness_percent", 100))


def set_brightness_percent(value: int):
    _state["brightness_percent"] = max(10, min(100, int(value)))
    _save(_state)


def distance_in_miles():
    return bool(_state.get("distance_miles", False))


def toggle_distance_units():
    _state["distance_miles"] = not _state["distance_miles"]
    _save(_state)


def show_compass_rose():
    return bool(_state.get("show_compass_rose", True))


def toggle_compass_rose():
    _state["show_compass_rose"] = not _state["show_compass_rose"]
    _save(_state)


def scale_index():
    return int(_state.get("scale_index", 1))


def set_scale_index(index: int):
    _state["scale_index"] = index
    _save(_state)
