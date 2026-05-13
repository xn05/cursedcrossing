from lib.geometry import Rect


class AlphaMask:
    def __init__(self, size, pixels=None, fill=False):
        self.width = int(size[0])
        self.height = int(size[1])
        if fill:
            self.pixels = {(x, y) for y in range(self.height) for x in range(self.width)}
        else:
            self.pixels = set(pixels or [])

    @classmethod
    def from_image(cls, image, threshold=1):
        image = image.convert("RGBA")
        alpha = image.getchannel("A")
        pixels = set()
        width, height = image.size
        data = alpha.load()
        for y in range(height):
            for x in range(width):
                if data[x, y] >= threshold:
                    pixels.add((x, y))
        return cls((width, height), pixels)

    def get_size(self):
        return self.width, self.height

    def get_rect(self):
        return Rect(0, 0, self.width, self.height)

    def get_bounding_rects(self):
        if not self.pixels:
            return []
        xs = [pixel[0] for pixel in self.pixels]
        ys = [pixel[1] for pixel in self.pixels]
        left = min(xs)
        top = min(ys)
        right = max(xs) + 1
        bottom = max(ys) + 1
        return [Rect(left, top, right - left, bottom - top)]

    def count(self):
        return len(self.pixels)

    def fill(self):
        self.pixels = {(x, y) for y in range(self.height) for x in range(self.width)}

    def overlap(self, other, offset):
        offset_x, offset_y = int(offset[0]), int(offset[1])
        if len(self.pixels) <= len(other.pixels):
            for x, y in self.pixels:
                if (x - offset_x, y - offset_y) in other.pixels:
                    return x, y
            return None
        for x, y in other.pixels:
            if (x + offset_x, y + offset_y) in self.pixels:
                return x + offset_x, y + offset_y
        return None
