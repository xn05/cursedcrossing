import math


class Vec2:
    def __init__(self, x=0, y=None):
        if y is None and hasattr(x, "x") and hasattr(x, "y"):
            self.x = float(x.x)
            self.y = float(x.y)
        elif y is None and isinstance(x, (list, tuple)):
            self.x = float(x[0])
            self.y = float(x[1])
        else:
            self.x = float(x)
            self.y = float(0 if y is None else y)

    def __add__(self, other):
        other = Vec2(other)
        return Vec2(self.x + other.x, self.y + other.y)

    def __iadd__(self, other):
        other = Vec2(other)
        self.x += other.x
        self.y += other.y
        return self

    def __sub__(self, other):
        other = Vec2(other)
        return Vec2(self.x - other.x, self.y - other.y)

    def __isub__(self, other):
        other = Vec2(other)
        self.x -= other.x
        self.y -= other.y
        return self

    def __mul__(self, value):
        return Vec2(self.x * value, self.y * value)

    def __rmul__(self, value):
        return self.__mul__(value)

    def __imul__(self, value):
        self.x *= value
        self.y *= value
        return self

    def __iter__(self):
        yield self.x
        yield self.y

    def length_squared(self):
        return self.x * self.x + self.y * self.y

    def normalize(self):
        length = math.sqrt(self.length_squared())
        if length == 0:
            return Vec2(0, 0)
        return Vec2(self.x / length, self.y / length)

    def copy(self):
        return Vec2(self.x, self.y)

    def __repr__(self):
        return f"Vec2({self.x}, {self.y})"


class Rect:
    def __init__(self, x=0, y=0, width=0, height=0):
        self.x = int(x)
        self.y = int(y)
        self.width = int(width)
        self.height = int(height)

    @property
    def left(self):
        return self.x

    @left.setter
    def left(self, value):
        self.x = int(value)

    @property
    def right(self):
        return self.x + self.width

    @right.setter
    def right(self, value):
        self.x = int(value) - self.width

    @property
    def top(self):
        return self.y

    @top.setter
    def top(self, value):
        self.y = int(value)

    @property
    def bottom(self):
        return self.y + self.height

    @bottom.setter
    def bottom(self, value):
        self.y = int(value) - self.height

    @property
    def centerx(self):
        return self.x + self.width // 2

    @centerx.setter
    def centerx(self, value):
        self.x = int(value) - self.width // 2

    @property
    def centery(self):
        return self.y + self.height // 2

    @centery.setter
    def centery(self, value):
        self.y = int(value) - self.height // 2

    @property
    def center(self):
        return self.centerx, self.centery

    @center.setter
    def center(self, value):
        self.centerx = value[0]
        self.centery = value[1]

    @property
    def midright(self):
        return self.right, self.centery

    @midright.setter
    def midright(self, value):
        self.right = value[0]
        self.centery = value[1]

    @property
    def midleft(self):
        return self.left, self.centery

    @midleft.setter
    def midleft(self, value):
        self.left = value[0]
        self.centery = value[1]

    @property
    def size(self):
        return self.width, self.height

    @property
    def topleft(self):
        return self.x, self.y

    @topleft.setter
    def topleft(self, value):
        self.x = int(value[0])
        self.y = int(value[1])

    def copy(self):
        return Rect(self.x, self.y, self.width, self.height)

    def colliderect(self, other):
        return self.left < other.right and self.right > other.left and self.top < other.bottom and self.bottom > other.top

    def collidepoint(self, pos):
        return self.left <= pos[0] < self.right and self.top <= pos[1] < self.bottom

    def union(self, other):
        left = min(self.left, other.left)
        top = min(self.top, other.top)
        right = max(self.right, other.right)
        bottom = max(self.bottom, other.bottom)
        return Rect(left, top, right - left, bottom - top)

    def union_ip(self, other):
        union = self.union(other)
        self.x, self.y, self.width, self.height = union.x, union.y, union.width, union.height

    def unionall(self, rects):
        union = self.copy()
        for rect in rects:
            union.union_ip(rect)
        return union

    def __repr__(self):
        return f"Rect({self.x}, {self.y}, {self.width}, {self.height})"
