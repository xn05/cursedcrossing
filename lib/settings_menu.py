import json
import os

import pygame

from lib.settings import COLORS, LOGICAL_WIDTH, LOGICAL_HEIGHT, SHOW_FPS, SHOW_RAIN


class SettingsMenu:
    def __init__(self, settings_path):
        self.settings_path = settings_path
        self.show_fps, self.show_rain = self.load_settings_flags()
        self.hovered_setting = None

    def load_settings_flags(self):
        defaults = {"show_fps": SHOW_FPS, "show_rain": SHOW_RAIN}
        try:
            with open(self.settings_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return defaults["show_fps"], defaults["show_rain"]
        return bool(data.get("show_fps", defaults["show_fps"])), bool(
            data.get("show_rain", defaults["show_rain"])
        )

    def save_settings_flags(self):
        try:
            with open(self.settings_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            data = {}
        data["show_fps"] = bool(self.show_fps)
        data["show_rain"] = bool(self.show_rain)
        with open(self.settings_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)

    def toggle_fps(self):
        self.show_fps = not self.show_fps
        self.save_settings_flags()

    def toggle_rain(self):
        self.show_rain = not self.show_rain
        self.save_settings_flags()

    def get_settings_layout(self, menu_font):
        title_surface = menu_font.render("SETTINGS", False, COLORS["text"])
        title_h = title_surface.get_height()
        title_gap = 12
        button_h = 18
        button_gap = 8
        buttons_h = button_h * 3 + button_gap * 2
        total_h = title_h + title_gap + buttons_h
        top_y = (LOGICAL_HEIGHT - total_h) // 2
        title_y = top_y
        buttons_top = title_y + title_h + title_gap
        return {"title_y": title_y, "buttons_top": buttons_top}

    def settings_buttons(self, menu_font):
        layout = self.get_settings_layout(menu_font)
        button_w = 160
        button_h = 18
        button_gap = 8
        center_x = LOGICAL_WIDTH // 2 - button_w // 2
        top_y = layout["buttons_top"]
        fps_rect = pygame.Rect(center_x, top_y, button_w, button_h)
        rain_rect = pygame.Rect(center_x, top_y + button_h + button_gap, button_w, button_h)
        back_rect = pygame.Rect(center_x, top_y + (button_h + button_gap) * 2, button_w, button_h)
        return {"show_fps": fps_rect, "show_rain": rain_rect, "back": back_rect}

    def draw(self, surface, menu_font):
        layout = self.get_settings_layout(menu_font)
        title_surface = menu_font.render("SETTINGS", False, COLORS["text"])
        title_pos = (LOGICAL_WIDTH // 2 - title_surface.get_width() // 2, layout["title_y"])
        surface.blit(title_surface, title_pos)

        buttons = self.settings_buttons(menu_font)
        for key, rect in buttons.items():
            color = COLORS["warning"] if self.hovered_setting == key else COLORS["track"]
            pygame.draw.rect(surface, color, rect, border_radius=3)
            if key == "show_fps":
                label = f"SHOW FPS: {'ON' if self.show_fps else 'OFF'}"
            elif key == "show_rain":
                label = f"SHOW RAIN: {'ON' if self.show_rain else 'OFF'}"
            else:
                label = "BACK"
            label_surface = menu_font.render(label, False, COLORS["text"])
            label_pos = (
                rect.centerx - label_surface.get_width() // 2,
                rect.centery - label_surface.get_height() // 2,
            )
            surface.blit(label_surface, label_pos)

    def handle_input(self, event, menu_font):
        buttons = self.settings_buttons(menu_font)
        if event.type == pygame.MOUSEMOTION:
            pos = event.pos
            self.hovered_setting = None
            for key, rect in buttons.items():
                if rect.collidepoint(pos):
                    self.hovered_setting = key
                    break
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if buttons["show_fps"].collidepoint(pos):
                self.toggle_fps()
            elif buttons["show_rain"].collidepoint(pos):
                self.toggle_rain()
            elif buttons["back"].collidepoint(pos):
                return "menu"
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "menu"
        return "settings"

