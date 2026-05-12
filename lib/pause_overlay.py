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
        resume_rect = pygame.Rect(center_x, center_y - button_h - button_gap // 2, button_w, button_h)
        title_rect = pygame.Rect(center_x, center_y + button_gap // 2, button_w, button_h)
        return {"resume": resume_rect, "title": title_rect}

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
            label = "RESUME" if key == "resume" else "TITLE"
            label_surface = self.font.render(label, False, COLORS["text"])
            label_pos = (
                rect.centerx - label_surface.get_width() // 2,
                rect.centery - label_surface.get_height() // 2,
            )
            surface.blit(label_surface, label_pos)
