import math
import random

import pygame

from lib.settings import LOGICAL_HEIGHT, LOGICAL_WIDTH, RAIN_DROPS


class RainSystem:
    def __init__(self, rain_def):
        rain_def = rain_def or {}
        self.effect = rain_def.get("effect", "rain")
        self.frequency = rain_def.get("frequency", RAIN_DROPS)
        self.direction_deg = float(rain_def.get("direction_deg", 200))
        self.speed = float(rain_def.get("speed", 50))
        self.spawn_mode = rain_def.get("spawn", "edge" if self.effect == "rain" else "random")
        self.lifetime = max(0.1, float(rain_def.get("lifetime", 1.0)))
        self.fade = bool(rain_def.get("fade", self.spawn_mode == "random"))
        self.textures = self.build_weighted_textures(rain_def.get("particles", []))
        if not self.textures:
            self.textures = [
                "rain/rain_1.png",
                "rain/rain_2.png",
                "rain/rain_3.png",
            ]
        self.velocity = self.build_velocity(self.direction_deg)
        self.spawn_backtrack = math.hypot(LOGICAL_WIDTH, LOGICAL_HEIGHT)
        self.particles = []
        self.reset()

    def reset(self):
        self.particles = []
        count = int(self.frequency)
        for _ in range(count):
            self.particles.append(self.spawn_particle())

    def update(self, dt):
        velocity = self.velocity * self.speed * dt
        for particle in self.particles:
            particle["pos"] += velocity
            particle["age"] += dt
            if self.should_respawn(particle):
                respawn = self.spawn_particle()
                particle["pos"] = respawn["pos"]
                particle["texture"] = respawn["texture"]
                particle["age"] = respawn["age"]

    def draw(self, surface, textures):
        for particle in self.particles:
            sprite = textures.get(particle["texture"], (2, 4))
            if self.fade:
                sprite = sprite.copy()
                remaining = max(0.0, 1.0 - particle["age"] / self.lifetime)
                sprite.set_alpha(int(255 * remaining))
            surface.blit(sprite, particle["pos"])

    def spawn_particle(self):
        if self.spawn_mode == "random":
            x = random.uniform(0, LOGICAL_WIDTH)
            y = random.uniform(0, LOGICAL_HEIGHT)
        else:
            x, y = self.get_spawn_pos()
            backtrack = random.uniform(0, self.spawn_backtrack)
            x -= self.velocity.x * backtrack
            y -= self.velocity.y * backtrack
        texture_path = random.choice(self.textures)
        return {"pos": pygame.Vector2(x, y), "texture": texture_path, "age": random.uniform(0, self.lifetime)}

    def should_respawn(self, particle):
        if self.spawn_mode == "random" and particle["age"] >= self.lifetime:
            return True
        return (
            particle["pos"].y > LOGICAL_HEIGHT + 20
            or particle["pos"].y < -20
            or particle["pos"].x < -20
            or particle["pos"].x > LOGICAL_WIDTH + 20
        )

    def get_spawn_pos(self):
        margin = 8
        vx = self.velocity.x
        vy = self.velocity.y

        edges = []
        weights = []
        if vx > 0.01:
            edges.append("left")
            weights.append(abs(vx))
        elif vx < -0.01:
            edges.append("right")
            weights.append(abs(vx))

        if vy > 0.01:
            edges.append("top")
            weights.append(abs(vy))
        elif vy < -0.01:
            edges.append("bottom")
            weights.append(abs(vy))

        if not edges:
            return random.uniform(0, LOGICAL_WIDTH), -margin

        edge = random.choices(edges, weights=weights, k=1)[0]
        if edge == "left":
            return -margin, random.uniform(0, LOGICAL_HEIGHT)
        if edge == "right":
            return LOGICAL_WIDTH + margin, random.uniform(0, LOGICAL_HEIGHT)
        if edge == "bottom":
            return random.uniform(0, LOGICAL_WIDTH), LOGICAL_HEIGHT + margin
        return random.uniform(0, LOGICAL_WIDTH), -margin

    @staticmethod
    def build_weighted_textures(particles):
        textures = []
        for particle in particles:
            texture = particle.get("texture")
            weight = int(particle.get("weight", 1))
            if not texture or weight <= 0:
                continue
            textures.extend([texture] * weight)
        return textures

    @staticmethod
    def build_velocity(direction_deg):
        radians = math.radians(direction_deg)
        vec = pygame.Vector2(math.sin(radians), -math.cos(radians))
        if vec.length_squared() == 0:
            return pygame.Vector2(0, 1)
        return vec.normalize()
