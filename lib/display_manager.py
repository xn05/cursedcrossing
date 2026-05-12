import pygame

from lib.settings import (
    BORDERLESS_FULLSCREEN,
    LOGICAL_HEIGHT,
    LOGICAL_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)


class DisplayManager:
    def __init__(self):
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.window_size = self.screen.get_size()

    def apply_display_mode(self, settings_menu):
        borderless = bool(getattr(settings_menu, "borderless_fullscreen", BORDERLESS_FULLSCREEN))
        if borderless:
            info = pygame.display.Info()
            display_w, display_h = info.current_w, info.current_h
            if getattr(pygame, "FULLSCREEN_DESKTOP", None) is not None:
                flags = pygame.FULLSCREEN_DESKTOP
            else:
                flags = pygame.FULLSCREEN | pygame.NOFRAME
            try:
                self.screen = pygame.display.set_mode((display_w, display_h), flags)
            except pygame.error:
                self.screen = pygame.display.set_mode((display_w, display_h), pygame.FULLSCREEN)
            self.window_size = self.screen.get_size()
            return

        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.window_size = (WINDOW_WIDTH, WINDOW_HEIGHT)

    def scale_mouse_pos(self, pos):
        window_w, window_h = self.window_size
        x = int(pos[0] * LOGICAL_WIDTH / window_w)
        y = int(pos[1] * LOGICAL_HEIGHT / window_h)
        return x, y

    @property
    def scale_x(self):
        return self.window_size[0] / LOGICAL_WIDTH

    @property
    def scale_y(self):
        return self.window_size[1] / LOGICAL_HEIGHT

    @property
    def scale(self):
        return min(self.scale_x, self.scale_y)

    def logical_to_screen_pos(self, pos):
        return int(pos[0] * self.scale_x), int(pos[1] * self.scale_y)

    def logical_to_screen_size(self, size):
        return max(1, int(size[0] * self.scale_x)), max(1, int(size[1] * self.scale_y))

    def logical_to_screen_rect(self, rect):
        x, y = self.logical_to_screen_pos((rect.x, rect.y))
        width, height = self.logical_to_screen_size((rect.width, rect.height))
        return pygame.Rect(x, y, width, height)

    def blit_logical(self, sprite, logical_pos, logical_size=None, smooth=True):
        if logical_size is None:
            logical_size = sprite.get_size()
        screen_size = self.logical_to_screen_size(logical_size)
        if sprite.get_size() != screen_size:
            transform = pygame.transform.smoothscale if smooth else pygame.transform.scale
            sprite = transform(sprite, screen_size)
        screen_pos = self.logical_to_screen_pos(logical_pos)
        self.screen.blit(sprite, screen_pos)

    def present_base(self, render_surface):
        scaled = pygame.transform.scale(render_surface, self.window_size)
        self.screen.blit(scaled, (0, 0))

    def flip(self):
        pygame.display.flip()
