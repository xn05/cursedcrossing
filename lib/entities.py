import math

import pygame


class TextureManager:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.cache = {}
        self.size_cache = {}

    def get(self, texture_path, size):
        key = (texture_path, size)
        if key in self.cache:
            return self.cache[key]
        if texture_path:
            full_path = f"{self.root_dir}/{texture_path}"
            try:
                surface = pygame.image.load(full_path).convert_alpha()
                surface = pygame.transform.scale(surface, size)
                self.cache[key] = surface
                return surface
            except FileNotFoundError:
                pass
        placeholder = pygame.Surface(size, pygame.SRCALPHA)
        placeholder.fill((160, 160, 160))
        self.cache[key] = placeholder
        return placeholder

    def get_image_size(self, texture_path):
        if not texture_path:
            return None
        if texture_path in self.size_cache:
            return self.size_cache[texture_path]
        full_path = f"{self.root_dir}/{texture_path}"
        try:
            surface = pygame.image.load(full_path)
        except FileNotFoundError:
            self.size_cache[texture_path] = None
            return None
        size = surface.get_size()
        self.size_cache[texture_path] = size
        return size


class Entity:
    def __init__(self, definition, pos):
        self.definition = definition
        self.pos = pygame.Vector2(pos)
        self.size = pygame.Vector2(definition.get("size", [8, 8]))
        self.speed = definition.get("speed", 0)
        self.texture = definition.get("texture")
        self.tags = set(definition.get("tags", []))
        self.alive = True

    @property
    def rect(self):
        return pygame.Rect(int(self.pos.x), int(self.pos.y), int(self.size.x), int(self.size.y))

    def update(self, dt):
        return None

    def draw(self, surface, textures):
        if self.definition.get("shape") == "circle":
            color = self.definition.get("color", [200, 60, 60])
            radius = max(1, int(min(self.size.x, self.size.y) // 2))
            center = (self.rect.centerx, self.rect.centery)
            pygame.draw.circle(surface, color, center, radius)
            return
        sprite = textures.get(self.texture, (int(self.size.x), int(self.size.y)))
        surface.blit(sprite, self.rect)


class Train(Entity):
    def __init__(self, definition, pos, direction):
        super().__init__(definition, pos)
        self.direction = pygame.Vector2(direction).normalize()
        self.ghost = "ghost" in self.tags

    def update(self, dt):
        self.pos += self.direction * self.speed * dt


class Car(Entity):
    def __init__(self, definition, pos, direction):
        super().__init__(definition, pos)
        self.direction = pygame.Vector2(direction).normalize()
        self.impatience = 0.0
        self.stopped = False

    def update(self, dt):
        if not self.stopped:
            self.pos += self.direction * self.speed * dt


class Gate(Entity):
    def __init__(self, definition, pos):
        super().__init__(definition, pos)
        self.is_closed = False

    def toggle(self):
        self.is_closed = not self.is_closed

    def draw(self, surface, textures):
        sprite = textures.get(self.texture, (int(self.size.x), int(self.size.y)))
        if self.is_closed:
            surface.blit(sprite, self.rect)
        else:
            ghost = sprite.copy()
            ghost.set_alpha(100)
            surface.blit(ghost, self.rect)


class Signal(Entity):
    def __init__(self, definition, pos):
        super().__init__(definition, pos)
        self.is_red = True

    def toggle(self):
        self.is_red = not self.is_red

