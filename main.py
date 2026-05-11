import json
import math
import os
import random
import sys

import pygame

from animation_loader import load_animation
from block_loader import load_block_defs
from character_loader import load_characters
from entity_loader import load_entity_defs
from entities import TextureManager
from region_loader import load_regions, resolve_region_path
from settings import (
    COLORS,
    FOG_ALPHA,
    FPS,
    LOGICAL_HEIGHT,
    LOGICAL_WIDTH,
    RAIN_DROPS,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Cursed Crossing")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.render_surface = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 10)

        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(base_dir, "data", "entities")
        gameplay_dir = os.path.join(base_dir, "data", "gameplay")
        config_dir = os.path.join(base_dir, "config")
        textures_dir = os.path.join(base_dir, "assets", "textures")
        font_path = os.path.join(base_dir, "assets", "font", "main.ttf")

        self.menu_font = pygame.font.Font(font_path, 6)
        self.entity_defs = load_entity_defs(data_dir)
        self.textures = TextureManager(textures_dir)
        self.movement = self.load_movement(os.path.join(gameplay_dir, "keybinds.json"))
        regions_path = os.path.join(config_dir, "regions.json")
        regions, default_region = load_regions(regions_path)
        region_id = default_region or next(iter(regions.keys()), None)
        if not region_id:
            raise ValueError("No regions configured in config/regions.json")
        region_path = resolve_region_path(base_dir, regions, region_id)
        self.region = self.load_region(region_path)
        self.region_origin = self.get_region_origin()

        blocks_path = os.path.join(base_dir, "data", "blocks", "blocks.json")
        self.block_defs = load_block_defs(blocks_path, base_dir)
        self.blocks = self.build_blocks()
        self.background_blocks = self.build_background_blocks()
        self.camera = pygame.Vector2(0, 0)
        self.frame_cache = {}

        rain_def = self.entity_defs.get("environment.rain", {})
        self.rain_frequency = rain_def.get("frequency", RAIN_DROPS)
        self.rain_direction_deg = float(rain_def.get("direction_deg", 200))
        self.rain_speed = float(rain_def.get("speed", 50))
        self.rain_textures = self.build_weighted_rain_textures(rain_def.get("particles", []))
        if not self.rain_textures:
            self.rain_textures = [
                "rain/rain_1.png",
                "rain/rain_2.png",
                "rain/rain_3.png",
            ]
        self.rain_velocity = self.build_rain_velocity(self.rain_direction_deg)
        self.rain_spawn_backtrack = math.hypot(LOGICAL_WIDTH, LOGICAL_HEIGHT)
        self.rain_particles = []
        self.reset_rain_particles()

        self.animation_cache = {}
        self.menu_anim_time = 0.0
        characters_path = os.path.join(data_dir, "characters", "characters.json")
        self.characters, self.character_animations = load_characters(characters_path, data_dir)
        self.characters = self.build_character_list(self.characters)
        self.selected_character_index = 0

        self.player_pos = pygame.Vector2(0, 0)
        self.player_dir = "down"
        self.player_anim_time = 0.0
        self.player_is_moving = False
        self.player_was_moving = False
        self.player_mask = None
        self.reset_player()

        self.state = "menu"
        self.hovered_button = None
        self.hovered_arrow = None

    def reset(self):
        self.reset_player()
        self.update_camera()
        self.state = "play"
        self.hovered_button = None
        self.hovered_arrow = None

    def load_movement(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        speed = float(data.get("speed", 60))
        bindings = {}
        for direction, keys in data.get("bindings", {}).items():
            key_codes = []
            for key in keys:
                try:
                    key_codes.append(pygame.key.key_code(key))
                except ValueError:
                    continue
            bindings[direction] = set(key_codes)
        return {"speed": speed, "bindings": bindings}

    def load_region(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        fog = data.get("fog", {})
        return {
            "id": data.get("id", "region"),
            "tile_size": int(data.get("tile_size", 25)),
            "size": data.get("size", [12, 7]),
            "player_spawn": data.get("player_spawn", [1, 1]),
            "cover_screen": bool(data.get("cover_screen", False)),
            "color": data.get("color", [18, 18, 22]),
            "border_color": data.get("border_color", [30, 32, 38]),
            "border_enabled": bool(data.get("border_enabled", False)),
            "rain_enabled": bool(data.get("rain_enabled", True)),
            "fog": {
                "enabled": bool(fog.get("enabled", True)),
                "color": fog.get("color", COLORS["fog"]),
                "alpha": int(fog.get("alpha", FOG_ALPHA)),
            },
            "tiles": data.get("tiles", []),
            "blocks": data.get("blocks", []),
            "background_blocks": data.get("background_blocks", []),
        }

    def get_region_origin(self):
        if self.region.get("cover_screen"):
            return pygame.Vector2(0, 0)
        width, height = self.region["size"]
        tile_size = self.region["tile_size"]
        region_w = width * tile_size
        region_h = height * tile_size
        origin_x = (LOGICAL_WIDTH - region_w) // 2
        origin_y = (LOGICAL_HEIGHT - region_h) // 2
        return pygame.Vector2(origin_x, origin_y)

    def get_region_pixel_size(self):
        width, height = self.region["size"]
        tile_size = self.region["tile_size"]
        return width * tile_size, height * tile_size

    def get_player_anchor(self):
        tile_size = self.region["tile_size"]
        return self.player_pos + pygame.Vector2(tile_size / 2, tile_size / 2)

    def get_camera_offset(self):
        world_w, world_h = self.get_region_pixel_size()
        target = self.get_player_anchor()
        cam_x = target.x - LOGICAL_WIDTH / 2
        cam_y = target.y - LOGICAL_HEIGHT / 2

        if world_w <= LOGICAL_WIDTH:
            cam_x = -(LOGICAL_WIDTH - world_w) / 2
        else:
            cam_x = max(0, min(cam_x, world_w - LOGICAL_WIDTH))

        if world_h <= LOGICAL_HEIGHT:
            cam_y = -(LOGICAL_HEIGHT - world_h) / 2
        else:
            cam_y = max(0, min(cam_y, world_h - LOGICAL_HEIGHT))

        return pygame.Vector2(cam_x, cam_y)

    def update_camera(self):
        self.camera = self.get_camera_offset()

    def build_blocks(self):
        blocks = []
        tile_size = self.region["tile_size"]
        for placement in self.region.get("blocks", []):
            block_id = placement.get("id")
            if not block_id:
                continue
            block_def = self.block_defs.get(block_id)
            if not block_def:
                continue
            pos = placement.get("pos", [0, 0])
            # Handle both single position [x, y] and multiple positions [[x1,y1], [x2,y2]]
            if isinstance(pos[0], list):
                positions = pos
            else:
                positions = [pos]
            for position in positions:
                anchor = pygame.Vector2(position[0] * tile_size, position[1] * tile_size)
                origin_tiles = pygame.Vector2(block_def.get("origin", [0, 0]))
                size_tiles = block_def.get("size", [1, 1])
                origin = origin_tiles * tile_size
                block_size = (int(size_tiles[0] * tile_size), int(size_tiles[1] * tile_size))
                sprite_size, sprite_offset = self.get_block_sprite_layout(block_def, block_size)
                texture_path = block_def.get("texture")
                sprite = self.textures.get(texture_path, (int(sprite_size[0]), int(sprite_size[1])))
                mask = pygame.mask.from_surface(sprite)
                hitbox = mask.get_rect()
                block_size = max(hitbox.width, hitbox.height)
                solid_rects = self.scale_rects(block_def.get("solid_rects", []), tile_size)
                passable_rects = self.scale_rects(block_def.get("passable_rects", []), tile_size)

                draw_pos = anchor - origin
                world_solids = []
                for rect in solid_rects:
                    world_solids.append(
                        pygame.Rect(
                            int(draw_pos.x + rect[0]),
                            int(draw_pos.y + rect[1]),
                            int(rect[2]),
                            int(rect[3]),
                        )
                    )
                blocks.append(
                    {
                        "definition": block_def,
                        "draw_pos": draw_pos,
                        "block_size": block_size,
                        "sprite_size": sprite_size,
                        "sprite_offset": sprite_offset,
                        "mask": mask,
                        "solid_rects": world_solids,
                        "passable_rects": passable_rects,
                    }
                )
        return blocks

    def get_block_sprite_layout(self, block_def, block_size):
        texture_path = block_def.get("texture")
        texture_override = block_def.get("texture_size")
        stretch_to_fit = block_def.get("stretch_to_fit", True)
        if stretch_to_fit:
            return block_size, pygame.Vector2(0, 0)

        if texture_override:
            native_size = (int(texture_override[0]), int(texture_override[1]))
        else:
            native_size = self.textures.get_image_size(texture_path)
        if not native_size or native_size[0] <= 0 or native_size[1] <= 0:
            return block_size, pygame.Vector2(0, 0)

        scale = block_size[0] / native_size[0]
        sprite_w = block_size[0]
        sprite_h = max(1, int(native_size[1] * scale))
        offset_y = block_size[1] - sprite_h
        return (sprite_w, sprite_h), pygame.Vector2(0, offset_y)

    def scale_rects(self, rects, tile_size):
        scaled = []
        for rect in rects:
            scaled.append(
                [
                    rect[0] * tile_size,
                    rect[1] * tile_size,
                    rect[2] * tile_size,
                    rect[3] * tile_size,
                ]
            )
        return scaled

    def build_background_blocks(self):
        background_blocks = []
        tile_size = self.region["tile_size"]
        for placement in self.region.get("background_blocks", []):
            block_id = placement.get("id")
            if not block_id:
                continue
            block_def = self.block_defs.get(block_id)
            if not block_def:
                continue
            positions = []
            # Handle pos
            pos = placement.get("pos")
            if pos:
                if isinstance(pos[0], list):
                    positions.extend(pos)
                else:
                    positions.append(pos)
            # Handle fill
            fill = placement.get("fill")
            if fill:
                if len(fill) == 2 and len(fill[0]) == 2 and len(fill[1]) == 2:
                    x1, y1 = fill[0]
                    x2, y2 = fill[1]
                    min_x, max_x = min(x1, x2), max(x1, x2)
                    min_y, max_y = min(y1, y2), max(y1, y2)
                    for x in range(min_x, max_x + 1):
                        for y in range(min_y, max_y + 1):
                            positions.append([x, y])
            # Remove duplicates if any
            positions = list(set(tuple(p) for p in positions))
            positions = [list(p) for p in positions]
            for position in positions:
                anchor = pygame.Vector2(position[0] * tile_size, position[1] * tile_size)
                origin_tiles = pygame.Vector2(block_def.get("origin", [0, 0]))
                size_tiles = block_def.get("size", [1, 1])
                origin = origin_tiles * tile_size
                block_size = (int(size_tiles[0] * tile_size), int(size_tiles[1] * tile_size))
                sprite_size, sprite_offset = self.get_block_sprite_layout(block_def, block_size)
                texture_path = block_def.get("texture")
                sprite = self.textures.get(texture_path, (int(sprite_size[0]), int(sprite_size[1])))
                mask = pygame.mask.from_surface(sprite)
                hitbox = mask.get_rect()
                block_size = max(hitbox.width, hitbox.height)
                passable_rects = self.scale_rects(block_def.get("passable_rects", []), tile_size)

                draw_pos = anchor - origin
                background_blocks.append(
                    {
                        "definition": block_def,
                        "draw_pos": draw_pos,
                        "block_size": block_size,
                        "sprite_size": sprite_size,
                        "sprite_offset": sprite_offset,
                        "mask": mask,
                        "passable_rects": passable_rects,
                    }
                )
        return background_blocks

    def reset_player(self):
        spawn = self.region["player_spawn"]
        tile_size = self.region["tile_size"]
        self.player_pos = pygame.Vector2(spawn[0] * tile_size, spawn[1] * tile_size)
        self.player_dir = "down"
        self.player_anim_time = 0.0
        self.player_is_moving = False
        self.player_was_moving = False

    def update(self, dt):
        self.update_rain(dt)
        self.update_menu(dt)
        if self.state != "play":
            return
        self.update_player(dt)
        self.update_camera()

    def update_player(self, dt):
        speed = self.movement["speed"]
        bindings = self.movement["bindings"]
        keys = pygame.key.get_pressed()

        dx = 0
        dy = 0
        if any(keys[key] for key in bindings.get("left", [])):
            dx -= 1
        if any(keys[key] for key in bindings.get("right", [])):
            dx += 1
        if any(keys[key] for key in bindings.get("up", [])):
            dy -= 1
        if any(keys[key] for key in bindings.get("down", [])):
            dy += 1

        move = pygame.Vector2(dx, dy)
        self.player_was_moving = self.player_is_moving
        self.player_is_moving = move.length_squared() > 0
        if self.player_is_moving:
            move = move.normalize() * speed * dt
            self.player_pos = self.resolve_collisions(self.player_pos, move)
            if move.x != 0:
                self.player_dir = "right" if move.x > 0 else "left"
            else:
                self.player_dir = "down" if move.y > 0 else "up"
        if self.player_is_moving != self.player_was_moving:
            self.player_anim_time = 0.0
        self.player_anim_time += dt

        self.clamp_player_to_region()

    def clamp_player_to_region(self):
        width, height = self.region["size"]
        tile_size = self.region["tile_size"]
        max_x = width * tile_size - tile_size
        max_y = height * tile_size - tile_size
        self.player_pos.x = max(0, min(self.player_pos.x, max_x))
        self.player_pos.y = max(0, min(self.player_pos.y, max_y))

    def get_player_rect(self, pos):
        tile_size = self.region["tile_size"]
        player_size = int(tile_size * 0.8)
        return pygame.Rect(int(pos.x), int(pos.y), player_size, player_size)

    def get_solids(self):
        solids = []
        for block in self.blocks:
            mask = block.get("mask")
            pos = block["draw_pos"]
            for rect in block.get("solid_rects", []):
                solids.append((rect, mask, pos))
        return solids

    def resolve_collisions(self, pos, move):
        solids = self.get_solids()
        if not solids:
            return pos + move

        new_pos = pygame.Vector2(pos)

        # Check X movement
        new_pos.x += move.x
        player_rect = self.get_player_rect(new_pos)
        collision_x = False
        for solid_rect, solid_mask, solid_pos in solids:
            if player_rect.colliderect(solid_rect):
                if self.player_mask and solid_mask:
                    offset = (int(solid_pos.x - new_pos.x), int(solid_pos.y - new_pos.y))
                    if self.player_mask.overlap(solid_mask, offset):
                        collision_x = True
                        break
        if collision_x:
            new_pos.x = pos.x

        # Check Y movement
        new_pos.y += move.y
        player_rect = self.get_player_rect(new_pos)
        collision_y = False
        for solid_rect, solid_mask, solid_pos in solids:
            if player_rect.colliderect(solid_rect):
                if self.player_mask and solid_mask:
                    offset = (int(solid_pos.x - new_pos.x), int(solid_pos.y - new_pos.y))
                    if self.player_mask.overlap(solid_mask, offset):
                        collision_y = True
                        break
        if collision_y:
            new_pos.y = pos.y

        return new_pos

    def update_menu(self, dt):
        if self.state != "menu":
            return
        self.menu_anim_time += dt

    def draw_background(self):
        surface = self.render_surface
        surface.fill(self.region["color"])
        self.draw_background_blocks(surface)
        if self.region["rain_enabled"]:
            self.draw_rain(surface)
        if self.region["fog"]["enabled"]:
            fog_surface = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT))
            fog_surface.fill(self.region["fog"]["color"])
            fog_surface.set_alpha(self.region["fog"]["alpha"])
            surface.blit(fog_surface, (0, 0))

    def draw_background_blocks(self, surface):
        for block in self.background_blocks:
            block_def = block["definition"]
            texture_path = block_def.get("texture")
            size = block["sprite_size"]
            sprite = self.textures.get(texture_path, (int(size[0]), int(size[1])))
            draw_pos = block["draw_pos"] + block["sprite_offset"] - self.camera
            surface.blit(sprite, (int(draw_pos.x), int(draw_pos.y)))

    def draw_menu_background(self):
        surface = self.render_surface
        surface.fill(COLORS["bg"])
        self.draw_rain(surface)

    def draw_region(self):
        rect = self.get_region_render_rect()
        if self.region["border_enabled"]:
            pygame.draw.rect(self.render_surface, self.region["border_color"], rect, 1)

    def get_region_render_rect(self):
        world_w, world_h = self.get_region_pixel_size()
        return pygame.Rect(int(-self.camera.x), int(-self.camera.y), world_w, world_h)

    def draw_blocks(self):
        for block in self.blocks:
            block_def = block["definition"]
            texture_path = block_def.get("texture")
            size = block["sprite_size"]
            sprite = self.textures.get(texture_path, (int(size[0]), int(size[1])))
            draw_pos = block["draw_pos"] + block["sprite_offset"] - self.camera
            self.render_surface.blit(sprite, (int(draw_pos.x), int(draw_pos.y)))

    def draw_player(self):
        character_def = self.get_selected_character()
        if not character_def:
            return
        anim_key = "walk" if self.player_is_moving else "idle"
        anim_id = character_def.get(anim_key) or character_def.get("idle")
        animation = self.get_animation(anim_id)
        if not animation:
            return

        preferred = self.map_player_direction(self.player_dir)
        frames, fps = self.get_animation_frames(animation, preferred)
        frame_index = int(self.player_anim_time * fps) % len(frames)
        frame = frames[frame_index]
        frame = self.scale_frame_to_tile(frame)
        self.player_mask = pygame.mask.from_surface(frame)

        draw_pos = self.player_pos - self.camera
        self.render_surface.blit(frame, draw_pos)

    def scale_frame_to_tile(self, frame):
        tile_size = int(self.region["tile_size"])
        target = (tile_size, tile_size)
        if frame.get_size() == target:
            return frame
        cache_key = (id(frame), tile_size)
        cached = self.frame_cache.get(cache_key)
        if cached:
            return cached
        scaled = pygame.transform.scale(frame, target)
        self.frame_cache[cache_key] = scaled
        return scaled

    def map_player_direction(self, direction):
        if direction == "up":
            return "backward"
        if direction == "down":
            return "forward"
        return direction

    def draw_rain(self, surface):
        for particle in self.rain_particles:
            sprite = self.textures.get(particle["texture"], (2, 4))
            surface.blit(sprite, particle["pos"])

    def build_weighted_rain_textures(self, particles):
        textures = []
        for particle in particles:
            texture = particle.get("texture")
            weight = int(particle.get("weight", 1))
            if not texture or weight <= 0:
                continue
            textures.extend([texture] * weight)
        return textures

    def build_rain_velocity(self, direction_deg):
        radians = math.radians(direction_deg)
        vec = pygame.Vector2(math.sin(radians), -math.cos(radians))
        if vec.length_squared() == 0:
            return pygame.Vector2(0, 1)
        return vec.normalize()

    def reset_rain_particles(self):
        self.rain_particles = []
        count = int(self.rain_frequency)
        for _ in range(count):
            particle = self.spawn_rain_particle()
            self.rain_particles.append(particle)

    def spawn_rain_particle(self):
        x, y = self.get_rain_spawn_pos()
        backtrack = random.uniform(0, self.rain_spawn_backtrack)
        x -= self.rain_velocity.x * backtrack
        y -= self.rain_velocity.y * backtrack
        texture_path = random.choice(self.rain_textures)
        return {"pos": pygame.Vector2(x, y), "texture": texture_path}

    def get_rain_spawn_pos(self):
        margin = 8
        vx = self.rain_velocity.x
        vy = self.rain_velocity.y

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

    def update_rain(self, dt):
        velocity = self.rain_velocity * self.rain_speed * dt
        for particle in self.rain_particles:
            particle["pos"] += velocity
            if (
                particle["pos"].y > LOGICAL_HEIGHT + 20
                or particle["pos"].x < -20
                or particle["pos"].x > LOGICAL_WIDTH + 20
            ):
                respawn = self.spawn_rain_particle()
                particle["pos"] = respawn["pos"]
                particle["texture"] = respawn["texture"]

    def draw(self):
        if self.state == "menu":
            self.draw_menu_background()
            self.draw_menu()
        elif self.state == "pause":
            self.draw_background()
            self.draw_region()
            self.draw_blocks()
            self.draw_player()
            self.draw_pause_overlay()
        else:
            self.draw_background()
            self.draw_region()
            self.draw_blocks()
            self.draw_player()

        scaled = pygame.transform.scale(self.render_surface, (WINDOW_WIDTH, WINDOW_HEIGHT))
        self.screen.blit(scaled, (0, 0))
        pygame.display.flip()

    def handle_input(self, event):
        if self.state == "menu":
            self.handle_menu_input(event)
            return
        if self.state == "pause":
            self.handle_pause_input(event)
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
            self.reset()
        # Check for pause key
        if event.type == pygame.KEYDOWN:
            pause_keys = self.movement["bindings"].get("pause", set())
            if event.key in pause_keys:
                self.state = "pause"

    def menu_buttons(self):
        layout = self.get_menu_layout()
        button_w = 120
        button_h = 18
        button_gap = 8
        center_x = LOGICAL_WIDTH // 2 - button_w // 2
        start_rect = pygame.Rect(center_x, layout["buttons_top"], button_w, button_h)
        settings_rect = pygame.Rect(center_x, layout["buttons_top"] + button_h + button_gap, button_w, button_h)
        return {"start": start_rect, "settings": settings_rect}

    def pause_menu_buttons(self):
        button_w = 120
        button_h = 18
        button_gap = 8
        center_x = LOGICAL_WIDTH // 2 - button_w // 2
        center_y = LOGICAL_HEIGHT // 2
        resume_rect = pygame.Rect(center_x, center_y - button_h - button_gap // 2, button_w, button_h)
        title_rect = pygame.Rect(center_x, center_y + button_gap // 2, button_w, button_h)
        return {"resume": resume_rect, "title": title_rect}

    def draw_menu(self):
        layout = self.get_menu_layout()
        title_sprite = self.textures.get("ui/title_text.png", (210, 21))
        title_pos = (LOGICAL_WIDTH // 2 - title_sprite.get_width() // 2, layout["title_y"])
        self.draw_character_select(layout["selector_center_y"])
        self.render_surface.blit(title_sprite, title_pos)

        buttons = self.menu_buttons()
        for key, rect in buttons.items():
            color = COLORS["warning"] if self.hovered_button == key else COLORS["track"]
            pygame.draw.rect(self.render_surface, color, rect, border_radius=3)
            label = "START GAME" if key == "start" else "SETTINGS"
            label_surface = self.menu_font.render(label, False, COLORS["text"])
            label_pos = (
                rect.centerx - label_surface.get_width() // 2,
                rect.centery - label_surface.get_height() // 2,
            )
            self.render_surface.blit(label_surface, label_pos)

    def draw_pause_overlay(self):
        # Draw semi-transparent overlay
        overlay = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT))
        overlay.fill((0, 0, 0))
        overlay.set_alpha(100)
        self.render_surface.blit(overlay, (0, 0))

        # Draw pause text
        pause_text_surface = self.menu_font.render("PAUSED", False, COLORS["warning"])
        pause_text_pos = (
            LOGICAL_WIDTH // 2 - pause_text_surface.get_width() // 2,
            LOGICAL_HEIGHT // 2 - 40,
        )
        self.render_surface.blit(pause_text_surface, pause_text_pos)

        # Draw buttons
        buttons = self.pause_menu_buttons()
        for key, rect in buttons.items():
            color = COLORS["warning"] if self.hovered_button == key else COLORS["track"]
            pygame.draw.rect(self.render_surface, color, rect, border_radius=3)
            label = "RESUME" if key == "resume" else "TITLE"
            label_surface = self.menu_font.render(label, False, COLORS["text"])
            label_pos = (
                rect.centerx - label_surface.get_width() // 2,
                rect.centery - label_surface.get_height() // 2,
            )
            self.render_surface.blit(label_surface, label_pos)

    def handle_menu_input(self, event):
        buttons = self.menu_buttons()
        select_rects = self.character_select_rects()
        if event.type == pygame.MOUSEMOTION:
            pos = self.scale_mouse_pos(event.pos)
            self.hovered_button = None
            self.hovered_arrow = None
            for key, rect in buttons.items():
                if rect.collidepoint(pos):
                    self.hovered_button = key
                    break
            if select_rects:
                if select_rects["left"].collidepoint(pos):
                    self.hovered_arrow = "left"
                elif select_rects["right"].collidepoint(pos):
                    self.hovered_arrow = "right"
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self.scale_mouse_pos(event.pos)
            if select_rects and select_rects["left"].collidepoint(pos):
                self.select_previous_character()
                return
            if select_rects and select_rects["right"].collidepoint(pos):
                self.select_next_character()
                return
            if buttons["start"].collidepoint(pos):
                self.reset()
            elif buttons["settings"].collidepoint(pos):
                pass
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self.reset()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_LEFT:
            self.select_previous_character()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RIGHT:
            self.select_next_character()

    def handle_pause_input(self, event):
        buttons = self.pause_menu_buttons()
        if event.type == pygame.MOUSEMOTION:
            pos = self.scale_mouse_pos(event.pos)
            self.hovered_button = None
            for key, rect in buttons.items():
                if rect.collidepoint(pos):
                    self.hovered_button = key
                    break
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self.scale_mouse_pos(event.pos)
            if buttons["resume"].collidepoint(pos):
                self.state = "play"
            elif buttons["title"].collidepoint(pos):
                self.state = "menu"
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self.state = "play"
        # ESC to resume
        pause_keys = self.movement["bindings"].get("pause", set())
        if event.type == pygame.KEYDOWN and event.key in pause_keys:
            self.state = "play"

    def scale_mouse_pos(self, pos):
        x = int(pos[0] * LOGICAL_WIDTH / WINDOW_WIDTH)
        y = int(pos[1] * LOGICAL_HEIGHT / WINDOW_HEIGHT)
        return x, y

    def build_character_list(self, characters):
        characters = list(characters)
        characters.sort(key=lambda item: item.get("display_name", item.get("id", "")))
        return characters

    def get_selected_character(self):
        if not self.characters:
            return None
        return self.characters[self.selected_character_index]

    def select_previous_character(self):
        if not self.characters:
            return
        self.selected_character_index = (self.selected_character_index - 1) % len(self.characters)
        self.menu_anim_time = 0.0

    def select_next_character(self):
        if not self.characters:
            return
        self.selected_character_index = (self.selected_character_index + 1) % len(self.characters)
        self.menu_anim_time = 0.0

    def get_neighbor_preview_frames(self):
        if not self.characters or len(self.characters) < 2:
            return None, None
        prev_index = (self.selected_character_index - 1) % len(self.characters)
        next_index = (self.selected_character_index + 1) % len(self.characters)
        prev_frame = self.get_character_preview_frame(self.characters[prev_index])
        next_frame = self.get_character_preview_frame(self.characters[next_index])
        return prev_frame, next_frame

    def get_character_preview_frame(self, character_def):
        anim_id = character_def.get("idle") or character_def.get("walk")
        animation = self.get_animation(anim_id)
        if not animation:
            return None
        frames, fps = self.get_animation_frames(animation, "right")
        frame_index = int(self.menu_anim_time * fps) % len(frames)
        return frames[frame_index]

    def draw_character_select(self, center_y):
        character_def = self.get_selected_character()
        if not character_def:
            return
        anim_id = character_def.get("idle") or character_def.get("walk")
        animation = self.get_animation(anim_id)
        if not animation:
            return
        frames, fps = self.get_animation_frames(animation, "right")
        frame_index = int(self.menu_anim_time * fps) % len(frames)
        frame = frames[frame_index]
        center_x = LOGICAL_WIDTH // 2
        sprite_rect = frame.get_rect(center=(center_x, center_y))
        left_sprite = self.textures.get("ui/left.png", (8, 13))
        right_sprite = self.textures.get("ui/right.png", (8, 13))
        left_rect = left_sprite.get_rect(midright=(sprite_rect.left - 6, sprite_rect.centery))
        right_rect = right_sprite.get_rect(midleft=(sprite_rect.right + 6, sprite_rect.centery))
        if self.hovered_arrow == "left":
            left_sprite = self.brighten_sprite(left_sprite, 0.25)
        if self.hovered_arrow == "right":
            right_sprite = self.brighten_sprite(right_sprite, 0.25)
        prev_frame, next_frame = self.get_neighbor_preview_frames()
        if prev_frame:
            preview = prev_frame.copy()
            preview.set_alpha(140)
            preview_rect = preview.get_rect(midright=(left_rect.left - 6, sprite_rect.centery))
            self.render_surface.blit(preview, preview_rect)
        if next_frame:
            preview = next_frame.copy()
            preview.set_alpha(140)
            preview_rect = preview.get_rect(midleft=(right_rect.right + 6, sprite_rect.centery))
            self.render_surface.blit(preview, preview_rect)
        self.render_surface.blit(left_sprite, left_rect)
        self.render_surface.blit(frame, sprite_rect)
        self.render_surface.blit(right_sprite, right_rect)

    def character_select_rects(self):
        character_def = self.get_selected_character()
        if not character_def:
            return None
        anim_id = character_def.get("idle") or character_def.get("walk")
        animation = self.get_animation(anim_id)
        if not animation:
            return None
        frame_size = animation["frame_size"]
        layout = self.get_menu_layout()
        center_y = layout["selector_center_y"]
        center_x = LOGICAL_WIDTH // 2
        sprite_rect = pygame.Rect(0, 0, frame_size[0], frame_size[1])
        sprite_rect.center = (center_x, center_y)
        left_rect = pygame.Rect(0, 0, 8, 13)
        right_rect = pygame.Rect(0, 0, 8, 13)
        left_rect.midright = (sprite_rect.left - 6, sprite_rect.centery)
        right_rect.midleft = (sprite_rect.right + 6, sprite_rect.centery)
        return {"left": left_rect, "right": right_rect, "sprite": sprite_rect}

    def get_menu_layout(self):
        title_sprite = self.textures.get("ui/title_text.png", (210, 21))
        title_h = title_sprite.get_height()
        selector_h = self.get_character_select_height()
        selector_gap = 6
        title_gap = 12
        button_h = 18
        button_gap = 8
        buttons_h = button_h * 2 + button_gap
        total_h = selector_h + selector_gap + title_h + title_gap + buttons_h
        top_y = (LOGICAL_HEIGHT - total_h) // 2
        selector_center_y = top_y + selector_h // 2
        title_y = top_y + selector_h + selector_gap
        buttons_top = title_y + title_h + title_gap
        return {
            "selector_center_y": selector_center_y,
            "title_y": title_y,
            "buttons_top": buttons_top,
        }

    def get_character_select_height(self):
        character_def = self.get_selected_character()
        if not character_def:
            return 32
        anim_id = character_def.get("idle") or character_def.get("walk")
        animation = self.get_animation(anim_id)
        if not animation:
            return 32
        return animation["frame_size"][1]

    def get_animation(self, anim_id):
        if not anim_id:
            return None
        if anim_id in self.animation_cache:
            return self.animation_cache[anim_id]
        if anim_id in self.character_animations:
            source_defs = self.character_animations
        else:
            source_defs = self.entity_defs
        animation = load_animation(source_defs, anim_id, self.textures.root_dir)
        if not animation:
            return None
        self.animation_cache[anim_id] = animation
        return animation

    def get_animation_frames(self, animation, preferred):
        sequences = animation["sequences"]
        if preferred in sequences:
            return sequences[preferred], animation["fps"]
        first_sequence = next(iter(sequences.values()))
        return first_sequence, animation["fps"]

    def brighten_sprite(self, sprite, amount):
        overlay = sprite.copy()
        boost = int(255 * amount)
        overlay.fill((boost, boost, boost, 0), special_flags=pygame.BLEND_RGBA_ADD)
        return overlay

    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                self.handle_input(event)
            self.update(dt)
            self.draw()


if __name__ == "__main__":
    Game().run()
