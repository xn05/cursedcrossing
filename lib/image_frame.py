import arcade
from PIL import Image

from lib.geometry import Rect


class ImageFrame:
    def __init__(self, image):
        self.image = image.convert("RGBA")

    def get_size(self):
        return self.image.size

    def get_width(self):
        return self.image.size[0]

    def get_height(self):
        return self.image.size[1]

    def get_rect(self, **kwargs):
        rect = Rect(0, 0, self.get_width(), self.get_height())
        for key, value in kwargs.items():
            setattr(rect, key, value)
        return rect

    def copy(self):
        return ImageFrame(self.image.copy())

    def resize(self, size):
        return ImageFrame(self.image.resize((int(size[0]), int(size[1])), Image.Resampling.NEAREST))

    def crop(self, box):
        return ImageFrame(self.image.crop(box))

    def set_alpha(self, alpha):
        alpha = max(0, min(255, int(alpha)))
        image = self.image.copy()
        current = image.getchannel("A")
        current = current.point(lambda value: value * alpha // 255)
        image.putalpha(current)
        self.image = image

    def to_texture(self):
        return arcade.Texture(self.image)
