import os

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
        self.center_windowed_mode()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.window_size = self.screen.get_size()

    def apply_display_mode(self, settings_menu):
        borderless = bool(getattr(settings_menu, "borderless_fullscreen", BORDERLESS_FULLSCREEN))
        if borderless:
            display_w, display_h = self.get_desktop_size()

            os.environ["SDL_VIDEO_WINDOW_POS"] = "0,0"
            self.screen = pygame.display.set_mode((display_w, display_h), pygame.NOFRAME)
            self.window_size = self.screen.get_size()
            return

        self.center_windowed_mode()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.window_size = (WINDOW_WIDTH, WINDOW_HEIGHT)

    def get_desktop_size(self):
        modes = pygame.display.list_modes()
        if modes and modes != -1:
            return modes[0]
        info = pygame.display.Info()
        return info.current_w, info.current_h

    def center_windowed_mode(self):
        os.environ.pop("SDL_VIDEO_WINDOW_POS", None)
        os.environ["SDL_VIDEO_CENTERED"] = "1"

    def scale_mouse_pos(self, pos):
        viewport = self.viewport_rect
        x = int((pos[0] - viewport.x) / self.scale)
        y = int((pos[1] - viewport.y) / self.scale)
        return x, y

    @property
    def scale(self):
        return min(self.window_size[0] / LOGICAL_WIDTH, self.window_size[1] / LOGICAL_HEIGHT)

    @property
    def viewport_rect(self):
        scale = self.scale
        width = int(LOGICAL_WIDTH * scale)
        height = int(LOGICAL_HEIGHT * scale)
        x = int((self.window_size[0] - width) / 2)
        y = int((self.window_size[1] - height) / 2)
        return pygame.Rect(x, y, width, height)

    def logical_to_screen_pos(self, pos):
        viewport = self.viewport_rect
        return int(viewport.x + pos[0] * self.scale), int(viewport.y + pos[1] * self.scale)

    def logical_to_screen_size(self, size):
        return max(1, int(size[0] * self.scale)), max(1, int(size[1] * self.scale))

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
        self.screen.fill((0, 0, 0))
        viewport = self.viewport_rect
        scaled = pygame.transform.scale(render_surface, (viewport.width, viewport.height))
        self.screen.blit(scaled, viewport)

    def flip(self):
        pygame.display.flip()
