import arcade
from PIL import Image

from lib.geometry import Rect, Vec2
from lib.image_frame import ImageFrame


class TextureManager:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.cache = {}
        self.arcade_cache = {}
        self.size_cache = {}

    def get(self, texture_path, size):
        key = (texture_path, tuple(size))
        if key in self.cache:
            return self.cache[key]
        image = self.load_image(texture_path, fallback_size=size)
        image = image.resize((int(size[0]), int(size[1])), Image.Resampling.NEAREST)
        frame = ImageFrame(image)
        self.cache[key] = frame
        return frame

    def get_raw(self, texture_path):
        key = (texture_path, None)
        if key in self.cache:
            return self.cache[key]
        frame = ImageFrame(self.load_image(texture_path))
        self.cache[key] = frame
        return frame

    def get_arcade(self, texture_path):
        key = (texture_path, "arcade")
        if key in self.arcade_cache:
            return self.arcade_cache[key]
        if texture_path:
            full_path = f"{self.root_dir}/{texture_path}"
            try:
                texture = arcade.load_texture(full_path)
                self.arcade_cache[key] = texture
                return texture
            except FileNotFoundError:
                pass
        texture = arcade.Texture(Image.new("RGBA", (1, 1), (160, 160, 160, 255)))
        self.arcade_cache[key] = texture
        return texture

    def get_arcade_from_frame(self, frame, cache_key):
        key = (cache_key, frame.get_width(), frame.get_height(), "frame")
        if key in self.arcade_cache:
            return self.arcade_cache[key]
        texture = frame.to_texture()
        self.arcade_cache[key] = texture
        return texture

    def get_image_size(self, texture_path):
        if not texture_path:
            return None
        if texture_path in self.size_cache:
            return self.size_cache[texture_path]
        try:
            image = self.load_image(texture_path)
        except FileNotFoundError:
            self.size_cache[texture_path] = None
            return None
        self.size_cache[texture_path] = image.size
        return image.size

    def load_image(self, texture_path, fallback_size=(1, 1)):
        if texture_path:
            full_path = f"{self.root_dir}/{texture_path}"
            try:
                return Image.open(full_path).convert("RGBA")
            except FileNotFoundError:
                pass
        return Image.new("RGBA", (int(fallback_size[0]), int(fallback_size[1])), (160, 160, 160, 255))


class Entity:
    def __init__(self, definition, pos):
        self.definition = definition
        self.pos = Vec2(pos)
        self.size = Vec2(definition.get("size", [8, 8]))
        self.speed = definition.get("speed", 0)
        self.texture = definition.get("texture")
        self.tags = set(definition.get("tags", []))
        self.alive = True

    @property
    def rect(self):
        return Rect(int(self.pos.x), int(self.pos.y), int(self.size.x), int(self.size.y))

    def update(self, dt):
        return None


class Train(Entity):
    def __init__(self, definition, pos, direction):
        super().__init__(definition, pos)
        self.direction = Vec2(direction).normalize()
        self.ghost = "ghost" in self.tags

    def update(self, dt):
        self.pos += self.direction * self.speed * dt


class Car(Entity):
    def __init__(self, definition, pos, direction):
        super().__init__(definition, pos)
        self.direction = Vec2(direction).normalize()
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


class Signal(Entity):
    def __init__(self, definition, pos):
        super().__init__(definition, pos)
        self.is_red = True

    def toggle(self):
        self.is_red = not self.is_red
