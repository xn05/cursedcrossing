import json

from lib.geometry import Rect
from lib.settings import LOGICAL_HEIGHT, LOGICAL_WIDTH, SHOW_FPS, SHOW_RAIN, BORDERLESS_FULLSCREEN, DEVELOPER_OPTIONS


class SettingsMenu:
    def __init__(self, settings_path):
        self.settings_path = settings_path
        (
            self.show_fps,
            self.show_rain,
            self.borderless_fullscreen,
            self.developer_options,
            self.show_block_id_overlay,
            self.show_hitboxes,
        ) = self.load_settings_flags()
        self.hovered_setting = None

    def load_settings_flags(self):
        defaults = {
            "show_fps": SHOW_FPS,
            "show_rain": SHOW_RAIN,
            "borderless_fullscreen": BORDERLESS_FULLSCREEN,
            "developer_options": DEVELOPER_OPTIONS,
            "show_block_id_overlay": False,
            "show_hitboxes": False,
        }
        try:
            with open(self.settings_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            data = {}
        return (
            bool(data.get("show_fps", defaults["show_fps"])),
            bool(data.get("show_rain", defaults["show_rain"])),
            bool(data.get("borderless_fullscreen", defaults["borderless_fullscreen"])),
            bool(data.get("developer_options", defaults["developer_options"])),
            bool(data.get("show_block_id_overlay", defaults["show_block_id_overlay"])),
            bool(data.get("show_hitboxes", defaults["show_hitboxes"])),
        )

    def save_settings_flags(self):
        try:
            with open(self.settings_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            data = {}
        data["show_fps"] = bool(self.show_fps)
        data["show_rain"] = bool(self.show_rain)
        data["borderless_fullscreen"] = bool(self.borderless_fullscreen)
        data["developer_options"] = bool(self.developer_options)
        data["show_block_id_overlay"] = bool(self.show_block_id_overlay)
        data["show_hitboxes"] = bool(self.show_hitboxes)
        with open(self.settings_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)

    def toggle_fps(self):
        self.show_fps = not self.show_fps
        self.save_settings_flags()

    def toggle_rain(self):
        self.show_rain = not self.show_rain
        self.save_settings_flags()

    def toggle_borderless_fullscreen(self):
        self.borderless_fullscreen = not self.borderless_fullscreen
        self.save_settings_flags()

    def toggle_block_id_overlay(self):
        self.show_block_id_overlay = not self.show_block_id_overlay
        self.save_settings_flags()

    def toggle_hitboxes(self):
        self.show_hitboxes = not self.show_hitboxes
        self.save_settings_flags()

    def get_settings_layout(self, menu_font):
        title_h = menu_font.render("SETTINGS", False, (255, 255, 255)).get_height()
        title_gap = 12
        button_h = 18
        button_gap = 8
        num_buttons = 6 if self.developer_options else 4
        buttons_h = button_h * num_buttons + button_gap * (num_buttons - 1)
        total_h = title_h + title_gap + buttons_h
        title_y = (LOGICAL_HEIGHT - total_h) // 2
        return {"title_y": title_y, "buttons_top": title_y + title_h + title_gap}

    def settings_buttons(self, menu_font):
        layout = self.get_settings_layout(menu_font)
        button_w = 160
        button_h = 18
        button_gap = 8
        center_x = LOGICAL_WIDTH // 2 - button_w // 2
        top_y = layout["buttons_top"]
        buttons = {
            "show_fps": Rect(center_x, top_y, button_w, button_h),
            "show_rain": Rect(center_x, top_y + button_h + button_gap, button_w, button_h),
            "borderless_fullscreen": Rect(center_x, top_y + (button_h + button_gap) * 2, button_w, button_h),
        }
        if self.developer_options:
            buttons["show_block_id_overlay"] = Rect(center_x, top_y + (button_h + button_gap) * 3, button_w, button_h)
            buttons["show_hitboxes"] = Rect(center_x, top_y + (button_h + button_gap) * 4, button_w, button_h)
            buttons["back"] = Rect(center_x, top_y + (button_h + button_gap) * 5, button_w, button_h)
        else:
            buttons["back"] = Rect(center_x, top_y + (button_h + button_gap) * 3, button_w, button_h)
        return buttons
