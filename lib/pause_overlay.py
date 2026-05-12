import pygame

from lib.settings import COLORS, LOGICAL_HEIGHT, LOGICAL_WIDTH


class PauseOverlay:
    def __init__(self, font):
        self.font = font

    def get_button_rects(self):
        button_w = 120
        button_h = 18
        button_gap = 8
        center_x = LOGICAL_WIDTH // 2 - button_w // 2
        center_y = LOGICAL_HEIGHT // 2
        resume_rect = pygame.Rect(center_x, center_y - button_h - button_gap, button_w, button_h)
        settings_rect = pygame.Rect(center_x, center_y, button_w, button_h)
        title_rect = pygame.Rect(center_x, center_y + button_h + button_gap, button_w, button_h)
        return {"resume": resume_rect, "settings": settings_rect, "title": title_rect}

    def get_button_label(self, key):
        if key == "resume":
            return "RESUME"
        if key == "settings":
            return "SETTINGS"
        return "EXIT TO TITLE"

    def draw(self, surface, hovered_button):
        overlay = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT))
        overlay.fill((0, 0, 0))
        overlay.set_alpha(100)
        surface.blit(overlay, (0, 0))

        pause_text_surface = self.font.render("PAUSED", False, COLORS["warning"])
        pause_text_pos = (
            LOGICAL_WIDTH // 2 - pause_text_surface.get_width() // 2,
            LOGICAL_HEIGHT // 2 - 40,
        )
        surface.blit(pause_text_surface, pause_text_pos)

        buttons = self.get_button_rects()
        for key, rect in buttons.items():
            color = COLORS["warning"] if hovered_button == key else COLORS["track"]
            pygame.draw.rect(surface, color, rect, border_radius=3)
            label = self.get_button_label(key)
            label_surface = self.font.render(label, False, COLORS["text"])
            label_pos = (
                rect.centerx - label_surface.get_width() // 2,
                rect.centery - label_surface.get_height() // 2,
            )
            surface.blit(label_surface, label_pos)

    def draw_high_res(self, display, hovered_button):
        overlay = pygame.Surface(display.window_size)
        overlay.fill((0, 0, 0))
        overlay.set_alpha(100)
        display.screen.blit(overlay, (0, 0))

        pause_text_surface = self.font.render("PAUSED", False, COLORS["warning"])
        pause_text_pos = (
            LOGICAL_WIDTH // 2 - pause_text_surface.get_width() // 2,
            LOGICAL_HEIGHT // 2 - 40,
        )
        display.blit_logical(pause_text_surface, pause_text_pos, pause_text_surface.get_size(), smooth=False)

        buttons = self.get_button_rects()
        for key, rect in buttons.items():
            color = COLORS["warning"] if hovered_button == key else COLORS["track"]

            button_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            pygame.draw.rect(button_surface, color, (0, 0, rect.width, rect.height), border_radius=3)
            label = self.get_button_label(key)
            label_surface = self.font.render(label, False, COLORS["text"])
            label_rect = label_surface.get_rect(center=(rect.width // 2, rect.height // 2))
            button_surface.blit(label_surface, label_rect)

            display.blit_logical(button_surface, (rect.x, rect.y), (rect.width, rect.height), smooth=False)
