import json
import os
import sys

import pygame

from lib.animation_loader import load_animation
from lib.block_loader import load_block_defs
from lib.block_numbering import coords_to_block_number
from lib.character_loader import load_characters
from lib.display_manager import DisplayManager
from lib.entity_loader import load_entity_defs
from lib.entities import TextureManager
from lib.game_state import GameStateController
from lib.region_loader import load_regions, resolve_region_path
from lib.region_title import RegionTitle
from lib.pause_overlay import PauseOverlay
from lib.blocks import build_background_blocks, build_blocks
from lib.movement import load_movement, update_player
from lib.character_select import CharacterSelect
from lib.rain_system import RainSystem
from lib.settings_menu import SettingsMenu
from lib.settings import (
    COLORS,
    FOG_ALPHA,
    FPS,
    HITBOX_COLORS,
    LOGICAL_HEIGHT,
    LOGICAL_WIDTH,
    SHOW_FPS,
    SHOW_RAIN,
)


DEFAULT_RENDER_STAGE_ORDER = [
    "region_background",
    "background_blocks",
    "region_border",
    "blocks",
    "player",
    "particles",
    "fog",
    "titles",
]

DEFAULT_RENDER_LAYERS = {
    stage: layer for layer, stage in enumerate(DEFAULT_RENDER_STAGE_ORDER)
}


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Cursed Crossing")
        self.display = DisplayManager()
        self.render_surface = pygame.Surface((LOGICAL_WIDTH, LOGICAL_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 10)
        self.hud_font_name = "consolas"

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

        # Apply display mode according to settings (borderless fullscreen etc.)
        self.display.apply_display_mode(self.settings_menu)

        regions_path = os.path.join(config_dir, "regions.json")
        regions, default_region = load_regions(regions_path)
        region_id = default_region or next(iter(regions.keys()), None)
        if not region_id:
            raise ValueError("No regions configured in config/regions.json")
        region_path = resolve_region_path(base_dir, regions, region_id)
        self.region = self.load_region(region_path)
        self.region_origin = self.get_region_origin()
        self.region_title = RegionTitle(self.region.get("title", {}), self.textures)

        self.game_state = GameStateController()

        blocks_path = os.path.join(base_dir, "data", "blocks", "blocks.json")
        self.block_defs = load_block_defs(blocks_path, base_dir)
        self.blocks = build_blocks(self.region, self.block_defs, self.textures)
        self.background_blocks = build_background_blocks(self.region, self.block_defs, self.textures)
        self.camera = pygame.Vector2(0, 0)
        self.frame_cache = {}

        rain_def = self.entity_defs.get("environment.rain", {})
        self.title_rain = RainSystem(rain_def)
        self.region_particle_effects = self.build_region_particle_effects(rain_def)

        self.animation_cache = {}

        self.player_pos = pygame.Vector2(0, 0)
        self.player_dir = "down"
        self.player_anim_time = 0.0
        self.player_is_moving = False
        self.player_was_moving = False
        self.player_mask = None
        self.player_collider_cache = {}
        self.settings_return_state = "menu"
        self.reset_player()

    @property
    def show_rain(self):
        return self.settings_menu.show_rain

    @property
    def show_fps(self):
        return self.settings_menu.show_fps

    @property
    def developer_options(self):
        return self.settings_menu.developer_options

    @property
    def show_block_id_overlay(self):
        return self.settings_menu.developer_options and self.settings_menu.show_block_id_overlay

    @property
    def show_hitboxes(self):
        return self.settings_menu.developer_options and self.settings_menu.show_hitboxes

    @property
    def state(self):
        return self.game_state.state

    @state.setter
    def state(self, value):
        self.game_state.state = value

    @property
    def hovered_button(self):
        return self.game_state.hovered_button

    @hovered_button.setter
    def hovered_button(self, value):
        self.game_state.hovered_button = value

    def reset(self):
        self.reset_player()
        self.update_camera()
        self.region_title.reset()
        self.state = "play"
        self.hovered_button = None

    def build_region_particle_effects(self, rain_def):
        effects = []
        if self.region.get("rain_enabled"):
            effects.append(RainSystem(rain_def))

        ambient_particles = self.region.get("ambient_particles", [])
        if isinstance(ambient_particles, dict):
            ambient_particles = [ambient_particles]
        for particle_def in ambient_particles:
            if particle_def and particle_def.get("enabled", True):
                effects.append(RainSystem(particle_def))
        return effects

    def normalize_render_layers(self, configured_layers):
        render_layers = dict(DEFAULT_RENDER_LAYERS)
        if isinstance(configured_layers, dict):
            for key, value in configured_layers.items():
                if key not in render_layers:
                    continue
                try:
                    render_layers[key] = max(0, min(10, int(value)))
                except (TypeError, ValueError):
                    continue
        return render_layers

    def start_transition(self, on_midpoint):
        self.game_state.start_transition(on_midpoint)

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
            "light_level": max(0.0, float(data.get("light_level", data.get("brightness", 1.0)))),
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
            "ambient_particles": data.get("ambient_particles", []),
            "render_layers": self.normalize_render_layers(data.get("render_layers", {})),
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
        if self.state in ("menu", "settings"):
            if self.show_rain:
                self.title_rain.update(dt)
        elif self.state in ("play", "pause"):
            for particle_system in self.region_particle_effects:
                particle_system.update(dt)

        self.character_select.update(dt)
        self.game_state.update_transition(dt)
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

    def draw_region_background_color(self, surface):
        surface.fill(self.region["color"])

    def draw_background_blocks(self, surface):
        for block in self.background_blocks:
            block_def = block["definition"]
            texture_path = block_def.get("texture")
            size = block["sprite_size"]
            sprite = self.textures.get(texture_path, (int(size[0]), int(size[1])))
            sprite = self.apply_block_brightness(sprite, block_def)
            draw_pos = block["draw_pos"] + block["sprite_offset"] - self.camera
            surface.blit(sprite, (int(draw_pos.x), int(draw_pos.y)))

    def draw_menu_background(self):
        surface = self.render_surface
        surface.fill(COLORS["bg"])
        if self.settings_menu.show_rain:
            self.title_rain.draw(surface, self.textures)

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
            sprite = self.apply_block_brightness(sprite, block_def)
            draw_pos = block["draw_pos"] + block["sprite_offset"] - self.camera
            self.render_surface.blit(sprite, (int(draw_pos.x), int(draw_pos.y)))

    def draw_particles(self, surface):
        for particle_system in self.region_particle_effects:
            particle_system.draw(surface, self.textures)

    def draw_region_effects(self, surface):
        light_level = float(self.region.get("light_level", 1.0))
        if light_level < 1.0:
            darkness = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            darkness.fill((0, 0, 0, max(0, min(255, int(255 * (1.0 - light_level))))))
            surface.blit(darkness, (0, 0))
        elif light_level > 1.0:
            brightness = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            alpha = int(255 * min(1.0, (light_level - 1.0) * 0.5))
            brightness.fill((255, 255, 255, max(0, min(255, alpha))))
            surface.blit(brightness, (0, 0))

        if self.region["fog"]["enabled"]:
            fog_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            fog_surface.fill((*self.region["fog"]["color"], self.region["fog"]["alpha"]))
            surface.blit(fog_surface, (0, 0))

    def draw_region_title(self, surface):
        self.region_title.draw(surface)

    def get_render_stages(self, include_titles=True):
        stages = {
            "region_background": lambda: self.draw_region_background_color(self.render_surface),
            "background_blocks": lambda: self.draw_background_blocks(self.render_surface),
            "region_border": self.draw_region,
            "blocks": self.draw_blocks,
            "player": self.draw_player,
            "particles": lambda: self.draw_particles(self.render_surface),
            "fog": lambda: self.draw_region_effects(self.render_surface),
            "titles": lambda: self.draw_region_title(self.render_surface),
        }
        if not include_titles:
            stages.pop("titles", None)

        order_index = {stage: index for index, stage in enumerate(DEFAULT_RENDER_STAGE_ORDER)}
        render_layers = self.region.get("render_layers", DEFAULT_RENDER_LAYERS)
        return sorted(
            stages.items(),
            key=lambda item: (render_layers.get(item[0], DEFAULT_RENDER_LAYERS[item[0]]), order_index[item[0]]),
        )

    def get_render_stage_names(self, include_titles=True):
        stage_names = list(DEFAULT_RENDER_STAGE_ORDER)
        if not include_titles:
            stage_names.remove("titles")

        order_index = {stage: index for index, stage in enumerate(DEFAULT_RENDER_STAGE_ORDER)}
        render_layers = self.region.get("render_layers", DEFAULT_RENDER_LAYERS)
        return sorted(
            stage_names,
            key=lambda stage: (render_layers.get(stage, DEFAULT_RENDER_LAYERS[stage]), order_index[stage]),
        )

    def draw_game_layers(self, include_titles=True):
        self.render_surface.fill((0, 0, 0))
        for _, draw_stage in self.get_render_stages(include_titles):
            draw_stage()

    def draw_region_background_color_high_res(self):
        self.display.screen.fill(self.region["color"])

    def draw_region_border_high_res(self):
        if not self.region["border_enabled"]:
            return
        screen_rect = self.display.logical_to_screen_rect(self.get_region_render_rect())
        pygame.draw.rect(self.display.screen, self.region["border_color"], screen_rect, max(1, int(self.display.scale)))

    def draw_block_collection_high_res(self, blocks):
        for block in blocks:
            block_def = block["definition"]
            texture_path = block_def.get("texture")
            size = block["sprite_size"]
            sprite = self.textures.get_raw(texture_path)
            sprite = self.apply_block_brightness(sprite, block_def)
            draw_pos = block["draw_pos"] + block["sprite_offset"] - self.camera
            self.display.blit_logical(sprite, draw_pos, (int(size[0]), int(size[1])), smooth=True)

    def draw_background_blocks_high_res(self):
        self.draw_block_collection_high_res(self.background_blocks)

    def draw_blocks_high_res(self):
        self.draw_block_collection_high_res(self.blocks)

    def draw_particles_high_res(self):
        for particle_system in self.region_particle_effects:
            for particle in particle_system.particles:
                sprite = self.textures.get_raw(particle["texture"])
                if particle_system.fade:
                    sprite = sprite.copy()
                    remaining = max(0.0, 1.0 - particle["age"] / particle_system.lifetime)
                    sprite.set_alpha(int(255 * remaining))
                self.display.blit_logical(sprite, particle["pos"], sprite.get_size(), smooth=True)

    def draw_region_title_high_res(self):
        self.region_title.draw_high_res(self.display)

    def draw_game_layers_high_res(self, include_titles=True):
        stages = {
            "region_background": self.draw_region_background_color_high_res,
            "background_blocks": self.draw_background_blocks_high_res,
            "region_border": self.draw_region_border_high_res,
            "blocks": self.draw_blocks_high_res,
            "player": self.draw_player_high_res,
            "particles": self.draw_particles_high_res,
            "fog": self.draw_region_effects_high_res,
            "titles": self.draw_region_title_high_res,
        }
        for stage_name in self.get_render_stage_names(include_titles):
            stages[stage_name]()

    def apply_block_brightness(self, sprite, block_def):
        brightness = float(block_def.get("brightness", 1.0))
        if brightness == 1.0:
            return sprite
        sprite = sprite.copy()
        if brightness < 1.0:
            shade = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
            shade.fill((0, 0, 0, max(0, min(255, int(255 * (1.0 - brightness))))))
            sprite.blit(shade, (0, 0))
        else:
            boost = min(255, int(255 * min(1.0, (brightness - 1.0) * 0.5)))
            sprite.fill((boost, boost, boost, 0), special_flags=pygame.BLEND_RGBA_ADD)
        return sprite

    def draw_block_id_overlay(self):
        if not self.show_block_id_overlay:
            return

        tile_size = int(self.region["tile_size"])
        region_width = int(self.region["size"][0])
        region_height = int(self.region["size"][1])
        overlay_color = (100, 100, 100)

        for tile_y in range(region_height):
            for tile_x in range(region_width):
                draw_x = tile_x * tile_size - self.camera.x
                draw_y = tile_y * tile_size - self.camera.y
                outline_rect = pygame.Rect(int(draw_x), int(draw_y), tile_size, tile_size)
                pygame.draw.rect(self.render_surface, overlay_color, outline_rect, 1)

    def draw_player(self):
        frame, draw_pos = self.get_player_frame_and_pos()
        if not frame:
            return
        self.render_surface.blit(frame, (int(draw_pos.x), int(draw_pos.y)))

    def get_player_frame_and_pos(self):
        raw_frame, render_scale = self.get_player_source_frame()
        if not raw_frame:
            return None, None
        frame = self.scale_frame_to_tile(raw_frame, render_scale)
        self.player_mask = self.get_player_collision_mask()
        draw_pos = self.get_player_draw_pos(frame)
        return frame, draw_pos

    def get_player_source_frame(self):
        character_def = self.character_select.get_selected_character()
        anim_key = "walk" if self.player_is_moving else "idle"
        anim_id = None
        if character_def:
            anim_id = character_def.get(anim_key) or character_def.get("idle") or character_def.get("walk")
        animation = self.get_animation(anim_id)
        if not animation:
            return None, 1.0
        direction = self.map_player_direction(self.player_dir)
        frames, fps = self.get_animation_frames(animation, direction)
        frame_index = int(self.player_anim_time * fps) % len(frames)
        frame = frames[frame_index]
        render_scale = 1.0
        if character_def:
            render_scale = float(character_def.get("scale", 1.0))
        return frame, render_scale

    def draw_player_high_res(self):
        raw_frame, render_scale = self.get_player_source_frame()
        if not raw_frame:
            return
        logical_size = self.get_player_logical_size(raw_frame, render_scale)
        self.player_mask = self.get_player_collision_mask()
        draw_pos = self.get_player_draw_pos_from_size(logical_size)
        self.display.blit_logical(raw_frame, draw_pos, logical_size, smooth=False)

    def get_player_collision_mask(self):
        character_def = self.character_select.get_selected_character()
        if not character_def:
            return None
        render_scale = float(character_def.get("scale", 1.0))
        cache_key = (
            character_def.get("id"),
            int(self.region["tile_size"]),
            render_scale,
            character_def.get("idle"),
            character_def.get("walk"),
        )
        cached = self.player_collider_cache.get(cache_key)
        if cached:
            return cached

        sample_rects = []
        for anim_key in ("idle", "walk"):
            anim_id = character_def.get(anim_key)
            animation = self.get_animation(anim_id)
            if not animation:
                continue
            for frames in animation["sequences"].values():
                for frame in frames:
                    scaled_frame = self.scale_frame_to_tile(frame, render_scale)
                    rect = self.get_player_frame_footprint_rect(scaled_frame)
                    if rect:
                        sample_rects.append(rect)

        if sample_rects:
            collider = self.create_stable_player_collider(sample_rects)
        else:
            raw_frame, render_scale = self.get_player_source_frame()
            frame = self.scale_frame_to_tile(raw_frame, render_scale) if raw_frame else None
            collider = self.create_player_collision_mask(frame) if frame else None
        self.player_collider_cache[cache_key] = collider
        return collider

    def get_player_frame_footprint_rect(self, frame):
        if not frame:
            return None
        tile_size = int(self.region["tile_size"])
        frame_w, frame_h = frame.get_size()
        offset_x = int((tile_size - frame_w) / 2)
        offset_y = int(tile_size - frame_h)
        frame_mask = pygame.mask.from_surface(frame)
        visible_rects = frame_mask.get_bounding_rects()
        if visible_rects:
            visible_rect = visible_rects[0].unionall(visible_rects[1:])
        else:
            visible_rect = pygame.Rect(0, 0, frame_w, frame_h)

        hitbox_top = visible_rect.y + visible_rect.height // 2
        return pygame.Rect(
            offset_x + visible_rect.x,
            offset_y + hitbox_top,
            visible_rect.width,
            max(1, visible_rect.bottom - hitbox_top),
        )

    def create_stable_player_collider(self, sample_rects):
        tile_size = int(self.region["tile_size"])
        width = max(1, min(rect.width for rect in sample_rects))
        height = max(1, self.get_middle_value(rect.height for rect in sample_rects))
        bottom = max(rect.bottom for rect in sample_rects)
        center_x = tile_size // 2
        left = int(round(center_x - width / 2))
        top = int(round(bottom - height))
        mask = pygame.Mask((width, height), fill=True)
        return {"mask": mask, "offset": pygame.Vector2(left, top)}

    def get_middle_value(self, values):
        values = sorted(int(value) for value in values)
        return values[len(values) // 2]

    def create_player_collision_mask(self, frame):
        hitbox_rect = self.get_player_frame_footprint_rect(frame)
        if not hitbox_rect:
            return None
        mask = pygame.Mask(hitbox_rect.size, fill=True)
        return {
            "mask": mask,
            "offset": pygame.Vector2(hitbox_rect.x, hitbox_rect.y),
        }

    def get_player_collision_rect(self):
        if not self.player_mask:
            return None
        if isinstance(self.player_mask, dict):
            mask = self.player_mask.get("mask")
            offset = pygame.Vector2(self.player_mask.get("offset", (0, 0)))
        else:
            mask = self.player_mask
            offset = pygame.Vector2(0, 0)
        if not mask:
            return None
        rect = mask.get_rect()
        rect.topleft = (
            int(self.player_pos.x + offset.x - self.camera.x),
            int(self.player_pos.y + offset.y - self.camera.y),
        )
        return rect

    def get_player_draw_pos(self, frame):
        return self.get_player_draw_pos_from_size(frame.get_size())

    def get_player_draw_pos_from_size(self, size):
        tile_size = int(self.region["tile_size"])
        frame_w, frame_h = size
        offset_x = (tile_size - frame_w) / 2
        offset_y = tile_size - frame_h
        return self.player_pos + pygame.Vector2(offset_x, offset_y) - self.camera

    def get_player_logical_size(self, frame, render_scale=1.0):
        tile_size = int(self.region["tile_size"])
        frame_w, frame_h = frame.get_size()
        if frame_w <= 0 or frame_h <= 0:
            return frame.get_size()
        target_h = max(1, int(tile_size * max(0.1, render_scale)))
        scale = target_h / frame_h
        target_w = max(1, int(round(frame_w * scale)))
        return target_w, target_h

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

    def draw(self):
        draw_high_res_dev_overlay = False
        draw_high_res_hitboxes = False
        draw_high_res_pause = False
        draw_high_res_title = False
        if self.state == "menu":
            self.draw_menu_background()
            self.draw_menu()
        elif self.state == "settings":
            self.draw_menu_background()
            self.draw_settings_menu()
        elif self.state == "pause":
            self.draw_game_layers(include_titles=False)
            draw_high_res_dev_overlay = self.show_block_id_overlay
            draw_high_res_hitboxes = self.show_hitboxes
            draw_high_res_pause = True
        else:
            self.draw_game_layers(include_titles=False)
            draw_high_res_title = True
            draw_high_res_dev_overlay = self.show_block_id_overlay
            draw_high_res_hitboxes = self.show_hitboxes

        self.draw_exit_button()
        self.display.present_base(self.render_surface)

        if draw_high_res_dev_overlay:
            self.draw_block_id_overlay_high_res()
        if draw_high_res_hitboxes:
            self.draw_hitboxes_high_res()
        if draw_high_res_pause:
            self.pause_overlay.draw_high_res(self.display, self.hovered_button)
        if draw_high_res_title:
            self.region_title.draw_high_res(self.display)
        if self.show_fps:
            self.draw_fps_high_res()

        self.draw_transition_overlay_high_res()

        self.display.flip()

    def get_exit_button_rect(self):
        size = 14
        margin = 4
        return pygame.Rect(margin, LOGICAL_HEIGHT - size - margin, size, size)

    def draw_exit_button(self):
        rect = self.get_exit_button_rect()
        mouse_pos = self.scale_mouse_pos(pygame.mouse.get_pos())
        color = COLORS["warning"] if rect.collidepoint(mouse_pos) else COLORS["track"]
        pygame.draw.rect(self.render_surface, color, rect, border_radius=3)

        label_surface = self.menu_font.render("X", False, COLORS["text"])
        label_pos = (
            rect.centerx - label_surface.get_width() // 2,
            rect.centery - label_surface.get_height() // 2,
        )
        self.render_surface.blit(label_surface, label_pos)

    def draw_fps(self):
        fps_text = f"FPS {self.clock.get_fps():.0f}"
        fps_surface = self.font.render(fps_text, False, COLORS["text"])
        self.render_surface.blit(fps_surface, (4, 4))

    def draw_fps_high_res(self):
        font_size = max(12, int(10 * self.display.scale))
        font = pygame.font.SysFont(self.hud_font_name, font_size)
        fps_text = f"FPS {self.clock.get_fps():.0f}"
        fps_surface = font.render(fps_text, True, COLORS["text"])
        self.display.screen.blit(fps_surface, self.display.logical_to_screen_pos((4, 4)))

    def draw_block_id_overlay_high_res(self):
        tile_size = int(self.region["tile_size"])
        region_width = int(self.region["size"][0])
        region_height = int(self.region["size"][1])
        overlay_color = (110, 110, 110)
        text_color = (235, 235, 235)
        font_size = max(12, int(8 * self.display.scale))
        font = pygame.font.SysFont(self.hud_font_name, font_size)

        for tile_y in range(region_height):
            for tile_x in range(region_width):
                block_number = coords_to_block_number(tile_x, tile_y, region_width, region_height)
                logical_rect = pygame.Rect(
                    int(tile_x * tile_size - self.camera.x),
                    int(tile_y * tile_size - self.camera.y),
                    tile_size,
                    tile_size,
                )
                screen_rect = self.display.logical_to_screen_rect(logical_rect)
                pygame.draw.rect(self.display.screen, overlay_color, screen_rect, 1)

                number_surface = font.render(str(block_number), True, text_color)
                number_rect = number_surface.get_rect(center=screen_rect.center)
                self.display.screen.blit(number_surface, number_rect)

    def draw_hitboxes_high_res(self):
        block_color = HITBOX_COLORS["block"]
        player_color = HITBOX_COLORS["player"]

        for block in self.blocks:
            for rect in block.get("debug_hitboxes", []):
                debug_rect = pygame.Rect(
                    int(rect.x - self.camera.x),
                    int(rect.y - self.camera.y),
                    rect.width,
                    rect.height,
                )
                pygame.draw.rect(self.display.screen, block_color, self.display.logical_to_screen_rect(debug_rect), 2)

        if self.player_mask:
            player_rect = self.get_player_collision_rect()
            if player_rect:
                pygame.draw.rect(self.display.screen, player_color, self.display.logical_to_screen_rect(player_rect), 2)

    def draw_region_effects_high_res(self):
        light_level = float(self.region.get("light_level", 1.0))
        if light_level < 1.0:
            darkness = pygame.Surface(self.display.window_size)
            darkness.fill((0, 0, 0))
            darkness.set_alpha(max(0, min(255, int(255 * (1.0 - light_level)))))
            self.display.screen.blit(darkness, (0, 0))
        elif light_level > 1.0:
            brightness = pygame.Surface(self.display.window_size)
            brightness.fill((255, 255, 255))
            alpha = int(255 * min(1.0, (light_level - 1.0) * 0.5))
            brightness.set_alpha(max(0, min(255, alpha)))
            self.display.screen.blit(brightness, (0, 0))

        if self.region["fog"]["enabled"]:
            fog_surface = pygame.Surface(self.display.window_size)
            fog_surface.fill(self.region["fog"]["color"])
            fog_surface.set_alpha(self.region["fog"]["alpha"])
            self.display.screen.blit(fog_surface, (0, 0))

    def draw_transition_overlay_high_res(self):
        alpha = self.game_state.get_transition_alpha()
        if alpha <= 0:
            return
        overlay = pygame.Surface(self.display.window_size)
        overlay.fill((0, 0, 0))
        overlay.set_alpha(alpha)
        self.display.screen.blit(overlay, (0, 0))

    def handle_input(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.get_exit_button_rect().collidepoint(self.scale_mouse_pos(event.pos)):
                pygame.quit()
                sys.exit()

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
                self.settings_return_state = "menu"
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
            elif buttons["settings"].collidepoint(pos):
                self.settings_return_state = "pause"
                self.state = "settings"
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
                self.state = self.resolve_settings_return_state(new_state)
                # Apply display changes (e.g. borderless) when leaving settings
                self.display.apply_display_mode(self.settings_menu)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            pos = self.scale_mouse_pos(event.pos)
            scaled_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": event.button})
            new_state = self.settings_menu.handle_input(scaled_event, self.menu_font)
            if new_state != "settings":
                self.state = self.resolve_settings_return_state(new_state)
                # Apply display changes (e.g. borderless) when leaving settings
                self.display.apply_display_mode(self.settings_menu)
                if self.state == "menu" and self.settings_menu.show_rain:
                    self.title_rain.reset()
        else:
            new_state = self.settings_menu.handle_input(event, self.menu_font)
            if new_state != "settings":
                self.state = self.resolve_settings_return_state(new_state)
                # Apply display changes (e.g. borderless) when leaving settings
                self.display.apply_display_mode(self.settings_menu)

    def draw_settings_menu(self):
        self.settings_menu.draw(self.render_surface, self.menu_font)

    def resolve_settings_return_state(self, new_state):
        if new_state == "menu":
            return self.settings_return_state
        return new_state

    def scale_mouse_pos(self, pos):
        return self.display.scale_mouse_pos(pos)

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
