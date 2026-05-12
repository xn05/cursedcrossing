import json
import math
import os
import random
import sys

import pygame

from lib.animation_loader import load_animation
from lib.block_loader import load_block_defs
from lib.character_loader import load_characters
from lib.entity_loader import load_entity_defs
from lib.entities import TextureManager
from lib.region_loader import load_regions, resolve_region_path
from lib.region_title import RegionTitle
from lib.pause_overlay import PauseOverlay
from lib.blocks import build_background_blocks, build_blocks
from lib.movement import load_movement, update_player
from lib.character_select import CharacterSelect
from lib.settings_menu import SettingsMenu
from lib.settings import (
    COLORS,
    FADE_IN_DURATION,
    FOG_ALPHA,
    FPS,
    LOGICAL_HEIGHT,
    LOGICAL_WIDTH,
    RAIN_DROPS,
    SHOW_FPS,
    SHOW_RAIN,
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
        gameplay_dir = os.path.join(base_dir, "data", "gameplay", "config")
        config_dir = os.path.join(base_dir, "config")
        textures_dir = os.path.join(base_dir, "assets", "textures")
        font_path = os.path.join(base_dir, "assets", "font", "main.ttf")
        settings_path = os.path.join(config_dir, "settings.json")

        self.menu_font = pygame.font.Font(font_path, 6)
        self.pause_overlay = PauseOverlay(self.menu_font)
        self.entity_defs = load_entity_defs(data_dir)
        self.textures = TextureManager(textures_dir)
        keybinds_path = os.path.join(config_dir, "keybinds.json")
        if not os.path.exists(keybinds_path):
            keybinds_path = os.path.join(gameplay_dir, "keybinds.json")
        self.movement = load_movement(keybinds_path)

        # Character selection and settings menus
        characters_path = os.path.join(data_dir, "characters", "characters.json")
        characters, character_animations = load_characters(characters_path, data_dir)
        characters = self._build_character_list(characters)
        self.character_select = CharacterSelect(characters, character_animations, self.textures)
        self.settings_menu = SettingsMenu(settings_path)

        regions_path = os.path.join(config_dir, "regions.json")
        regions, default_region = load_regions(regions_path)
        region_id = default_region or next(iter(regions.keys()), None)
        if not region_id:
            raise ValueError("No regions configured in config/regions.json")
        region_path = resolve_region_path(base_dir, regions, region_id)
        self.region = self.load_region(region_path)
        self.region_origin = self.get_region_origin()
        self.region_title = RegionTitle(self.region.get("title", {}), self.textures)

        self.fade_in_duration = max(0.0, float(FADE_IN_DURATION))
        self.fade_out_duration = self.fade_in_duration
        self.transition_active = False
        self.transition_phase = None
        self.transition_time = 0.0
        self.transition_midpoint_done = False
        self.transition_on_midpoint = None

        blocks_path = os.path.join(base_dir, "data", "blocks", "blocks.json")
        self.block_defs = load_block_defs(blocks_path, base_dir)
        self.blocks = build_blocks(self.region, self.block_defs, self.textures)
        self.background_blocks = build_background_blocks(self.region, self.block_defs, self.textures)
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

        self.player_pos = pygame.Vector2(0, 0)
        self.player_dir = "down"
        self.player_anim_time = 0.0
        self.player_is_moving = False
        self.player_was_moving = False
        self.player_mask = None
        self.reset_player()

        self.state = "menu"
        self.hovered_button = None

    @property
    def show_rain(self):
        return self.settings_menu.show_rain

    @property
    def show_fps(self):
        return self.settings_menu.show_fps

    def reset(self):
        self.reset_player()
        self.update_camera()
        self.region_title.reset()
        self.state = "play"
        self.hovered_button = None

    def start_transition(self, on_midpoint):
        self.transition_active = True
        self.transition_phase = "out"
        self.transition_time = 0.0
        self.transition_midpoint_done = False
        self.transition_on_midpoint = on_midpoint

    def update_transition(self, dt):
        if not self.transition_active:
            return
        duration = self.fade_out_duration if self.transition_phase == "out" else self.fade_in_duration
        duration = max(0.0, float(duration))
        if duration == 0.0:
            self._advance_transition_phase()
            return
        self.transition_time += dt
        if self.transition_time >= duration:
            self._advance_transition_phase()

    def _advance_transition_phase(self):
        if self.transition_phase == "out":
            if not self.transition_midpoint_done and self.transition_on_midpoint:
                self.transition_on_midpoint()
            self.transition_midpoint_done = True
            self.transition_phase = "in"
            self.transition_time = 0.0
        else:
            self.transition_active = False
            self.transition_phase = None
            self.transition_time = 0.0
            self.transition_on_midpoint = None

    def get_transition_alpha(self):
        if not self.transition_active or not self.transition_phase:
            return 0
        duration = self.fade_out_duration if self.transition_phase == "out" else self.fade_in_duration
        duration = max(0.0, float(duration))
        if duration == 0.0:
            return 0 if self.transition_phase == "in" else 255
        t = min(1.0, self.transition_time / duration)
        if self.transition_phase == "out":
            return int(255 * t)
        return int(255 * (1.0 - t))

    def draw_transition_overlay(self):
        alpha = self.get_transition_alpha()
        if alpha <= 0:
            return
        overlay = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT))
        overlay.fill((0, 0, 0))
        overlay.set_alpha(alpha)
        self.render_surface.blit(overlay, (0, 0))

    def load_region(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        fog = data.get("fog", {})
        title = data.get("title", {})
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
            "title": {
                "enabled": bool(title.get("enabled", False)),
                "image": title.get("image"),
                "scale": float(title.get("scale", 1.0)),
                "duration": float(title.get("duration", 2.0)),
                "fade_duration": float(title.get("fade_duration", 1.0)),
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

    def reset_player(self):
        spawn = self.region["player_spawn"]
        tile_size = self.region["tile_size"]
        self.player_pos = pygame.Vector2(spawn[0] * tile_size, spawn[1] * tile_size)
        self.player_dir = "down"
        self.player_anim_time = 0.0
        self.player_is_moving = False
        self.player_was_moving = False

    def update(self, dt):
        if self.show_rain and self.region["rain_enabled"]:
            self.update_rain(dt)
        self.character_select.update(dt)
        self.update_transition(dt)
        if self.state != "play":
            return
        (
            self.player_pos,
            self.player_dir,
            self.player_anim_time,
            self.player_is_moving,
            self.player_was_moving,
        ) = update_player(
            dt,
            self.movement,
            self.region,
            self.player_pos,
            self.player_dir,
            self.player_anim_time,
            self.player_is_moving,
            self.player_mask,
            self.blocks,
        )
        self.region_title.update(dt)
        self.update_camera()



    def draw_background(self):
        surface = self.render_surface
        surface.fill(self.region["color"])
        self.draw_background_blocks(surface)
        if self.show_rain and self.region["rain_enabled"]:
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
        if self.settings_menu.show_rain and self.region["rain_enabled"]:
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
        character_def = self.character_select.get_selected_character()
        anim_key = "walk" if self.player_is_moving else "idle"
        anim_id = None
        if character_def:
            anim_id = character_def.get(anim_key) or character_def.get("idle") or character_def.get("walk")
        animation = self.get_animation(anim_id)
        if not animation:
            return
        direction = self.map_player_direction(self.player_dir)
        frames, fps = self.get_animation_frames(animation, direction)
        frame_index = int(self.player_anim_time * fps) % len(frames)
        frame = frames[frame_index]
        render_scale = 1.0
        if character_def:
            render_scale = float(character_def.get("scale", 1.0))
        frame = self.scale_frame_to_tile(frame, render_scale)
        self.player_mask = pygame.mask.from_surface(frame)
        draw_pos = self.get_player_draw_pos(frame)
        self.render_surface.blit(frame, (int(draw_pos.x), int(draw_pos.y)))

    def get_player_draw_pos(self, frame):
        tile_size = int(self.region["tile_size"])
        frame_w, frame_h = frame.get_size()
        offset_x = (tile_size - frame_w) / 2
        offset_y = tile_size - frame_h
        return self.player_pos + pygame.Vector2(offset_x, offset_y) - self.camera

    def scale_frame_to_tile(self, frame, render_scale=1.0):
        tile_size = int(self.region["tile_size"])
        frame_w, frame_h = frame.get_size()
        if frame_w <= 0 or frame_h <= 0:
            return frame
        target_h = max(1, int(tile_size * max(0.1, render_scale)))
        scale = target_h / frame_h
        target_w = max(1, int(round(frame_w * scale)))
        target = (target_w, target_h)
        if frame.get_size() == target:
            return frame
        cache_key = (id(frame), target_w, target_h)
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
        elif self.state == "settings":
            self.draw_menu_background()
            self.draw_settings_menu()
        elif self.state == "pause":
            self.draw_background()
            self.draw_region()
            self.draw_blocks()
            self.draw_player()
            self.pause_overlay.draw(self.render_surface, self.hovered_button)
        else:
            self.draw_background()
            self.draw_region()
            self.draw_blocks()
            self.draw_player()
            self.region_title.draw(self.render_surface)

        if self.show_fps:
            self.draw_fps()

        self.draw_transition_overlay()
        scaled = pygame.transform.scale(self.render_surface, (WINDOW_WIDTH, WINDOW_HEIGHT))
        self.screen.blit(scaled, (0, 0))
        pygame.display.flip()

    def draw_fps(self):
        fps_text = f"FPS {self.clock.get_fps():.0f}"
        fps_surface = self.font.render(fps_text, False, COLORS["text"])
        self.render_surface.blit(fps_surface, (4, 4))

    def handle_input(self, event):
        if self.state == "menu":
            self.handle_menu_input(event)
            return
        if self.state == "settings":
            self.handle_settings_input(event)
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
        layout = self.character_select.get_menu_layout(self.animation_cache)
        button_w = 120
        button_h = 18
        button_gap = 8
        center_x = LOGICAL_WIDTH // 2 - button_w // 2
        start_rect = pygame.Rect(center_x, layout["buttons_top"], button_w, button_h)
        settings_rect = pygame.Rect(center_x, layout["buttons_top"] + button_h + button_gap, button_w, button_h)
        return {"start": start_rect, "settings": settings_rect}

    def draw_menu(self):
        layout = self.character_select.get_menu_layout(self.animation_cache)
        title_sprite = self.textures.get("ui/title_text.png", (210, 21))
        title_pos = (LOGICAL_WIDTH // 2 - title_sprite.get_width() // 2, layout["title_y"])
        self.character_select.draw(self.render_surface, self.animation_cache)
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

    def handle_menu_input(self, event):
        buttons = self.menu_buttons()
        select_rects = self.character_select.character_select_rects(self.animation_cache)
        if event.type == pygame.MOUSEMOTION:
            pos = self.scale_mouse_pos(event.pos)
            self.hovered_button = None
            self.character_select.hovered_arrow = None
            for key, rect in buttons.items():
                if rect.collidepoint(pos):
                    self.hovered_button = key
                    break
            if select_rects:
                if select_rects["left"].collidepoint(pos):
                    self.character_select.hovered_arrow = "left"
                elif select_rects["right"].collidepoint(pos):
                    self.character_select.hovered_arrow = "right"
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self.scale_mouse_pos(event.pos)
            if select_rects and select_rects["left"].collidepoint(pos):
                self.character_select.select_previous_character()
                return
            if select_rects and select_rects["right"].collidepoint(pos):
                self.character_select.select_next_character()
                return
            if buttons["start"].collidepoint(pos):
                self.start_transition(self.reset)
            elif buttons["settings"].collidepoint(pos):
                self.state = "settings"
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self.start_transition(self.reset)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_LEFT:
            self.character_select.select_previous_character()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RIGHT:
            self.character_select.select_next_character()

    def handle_pause_input(self, event):
        buttons = self.pause_overlay.get_button_rects()
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
        pause_keys = self.movement["bindings"].get("pause", set())
        if event.type == pygame.KEYDOWN and event.key in pause_keys:
            self.state = "play"

    def handle_settings_input(self, event):
        # Scale mouse position for settings menu input
        if event.type == pygame.MOUSEMOTION:
            pos = self.scale_mouse_pos(event.pos)
            # Create a new event with scaled position for settings menu
            scaled_event = pygame.event.Event(pygame.MOUSEMOTION, {"pos": pos})
            new_state = self.settings_menu.handle_input(scaled_event, self.menu_font)
            if new_state != "settings":
                self.state = new_state
        elif event.type == pygame.MOUSEBUTTONDOWN:
            pos = self.scale_mouse_pos(event.pos)
            scaled_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": event.button})
            new_state = self.settings_menu.handle_input(scaled_event, self.menu_font)
            if new_state != "settings":
                self.state = new_state
                if new_state == "menu" and self.settings_menu.show_rain:
                    self.reset_rain_particles()
        else:
            new_state = self.settings_menu.handle_input(event, self.menu_font)
            if new_state != "settings":
                self.state = new_state

    def draw_settings_menu(self):
        self.settings_menu.draw(self.render_surface, self.menu_font)

    def scale_mouse_pos(self, pos):
        x = int(pos[0] * LOGICAL_WIDTH / WINDOW_WIDTH)
        y = int(pos[1] * LOGICAL_HEIGHT / WINDOW_HEIGHT)
        return x, y

    def _build_character_list(self, characters):
        characters = list(characters)
        characters.sort(key=lambda item: item.get("display_name", item.get("id", "")))
        return characters

    def get_animation(self, anim_id):
        if not anim_id:
            return None
        if anim_id in self.animation_cache:
            return self.animation_cache[anim_id]
        if anim_id in self.character_select.character_animations:
            source_defs = self.character_select.character_animations
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
