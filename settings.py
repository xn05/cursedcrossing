import json
import os


def _load_settings():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    settings_path = os.path.join(base_dir, "config", "settings.json")
    with open(settings_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


_SETTINGS = _load_settings()

LOGICAL_WIDTH = int(_SETTINGS.get("logical_width", 320))
LOGICAL_HEIGHT = int(_SETTINGS.get("logical_height", 180))
SCALE = int(_SETTINGS.get("scale", 3))
WINDOW_WIDTH = LOGICAL_WIDTH * SCALE
WINDOW_HEIGHT = LOGICAL_HEIGHT * SCALE
FPS = int(_SETTINGS.get("fps", 60))

FOG_ALPHA = int(_SETTINGS.get("fog_alpha", 50))
RAIN_DROPS = int(_SETTINGS.get("rain_drops", 40))

_colors = _SETTINGS.get("colors", {})
COLORS = {
    "bg": tuple(_colors.get("bg", [10, 12, 16])),
    "track": tuple(_colors.get("track", [40, 42, 48])),
    "road": tuple(_colors.get("road", [24, 24, 28])),
    "fog": tuple(_colors.get("fog", [110, 120, 130])),
    "signal_red": tuple(_colors.get("signal_red", [200, 40, 40])),
    "signal_green": tuple(_colors.get("signal_green", [40, 180, 80])),
    "text": tuple(_colors.get("text", [230, 230, 230])),
    "warning": tuple(_colors.get("warning", [220, 100, 90])),
}
