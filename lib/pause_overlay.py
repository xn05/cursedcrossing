from lib.geometry import Rect
from lib.settings import LOGICAL_HEIGHT, LOGICAL_WIDTH


class PauseOverlay:
    def __init__(self, font):
        self.font = font

    def get_button_rects(self):
        button_w = 120
        button_h = 18
        button_gap = 8
        center_x = LOGICAL_WIDTH // 2 - button_w // 2
        center_y = LOGICAL_HEIGHT // 2
        return {
            "resume": Rect(center_x, center_y - button_h - button_gap, button_w, button_h),
            "settings": Rect(center_x, center_y, button_w, button_h),
            "title": Rect(center_x, center_y + button_h + button_gap, button_w, button_h),
        }

    def get_button_label(self, key):
        if key == "resume":
            return "RESUME"
        if key == "settings":
            return "SETTINGS"
        return "EXIT TO TITLE"
