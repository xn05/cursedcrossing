import pygame

from lib.settings import LOGICAL_HEIGHT, LOGICAL_WIDTH


class RegionTitle:
    def __init__(self, config, textures):
        self.config = config or {}
        self.textures = textures
        self.time = 0.0
        self.active = bool(self.config.get("enabled", False))

    def reset(self):
        self.time = 0.0
        self.active = bool(self.config.get("enabled", False))

    def update(self, dt):
        if not self.active:
            return
        duration = max(0.0, float(self.config.get("duration", 0.0)))
        fade = max(0.0, float(self.config.get("fade_duration", 0.0)))
        self.time += dt
        if self.time >= duration + fade:
            self.active = False

    def draw(self, surface):
        if not self.active:
            return
        image_path = self.config.get("image")
        if not image_path:
            return
        base_size = self.textures.get_image_size(image_path)
        if not base_size:
            return
        scale = max(0.01, float(self.config.get("scale", 1.0)))
        target_size = (max(1, int(base_size[0] * scale)), max(1, int(base_size[1] * scale)))
        sprite = self.textures.get(image_path, target_size)
        duration = max(0.0, float(self.config.get("duration", 0.0)))
        fade = max(0.0, float(self.config.get("fade_duration", 0.0)))
        alpha = 255
        if fade > 0.0 and self.time > duration:
            remaining = max(0.0, duration + fade - self.time)
            alpha = int(255 * min(1.0, remaining / fade))
        sprite = sprite.copy()
        sprite.set_alpha(max(0, min(255, alpha)))
        rect = sprite.get_rect(center=(LOGICAL_WIDTH // 2, LOGICAL_HEIGHT // 2))
        surface.blit(sprite, rect)
