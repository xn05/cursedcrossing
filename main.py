import json
import os
import sys

import arcade
import pyglet
from arcade.types import Color
from PIL import Image, ImageDraw, ImageFont

from lib.animation_loader import load_animation
from lib.block_loader import load_block_defs
from lib.block_numbering import coords_to_block_number
from lib.character_loader import load_characters
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
from lib.geometry import Rect, Vec2
from lib.masks import AlphaMask
from lib.settings import (
    COLORS,
    FOG_ALPHA,
    FPS,
    HITBOX_COLORS,
    LOGICAL_HEIGHT,
    LOGICAL_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)


WINDOWS_APP_ID = "cursedcrossing.game"


def configure_windows_taskbar_icon():
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_ID)
    except Exception:
        return


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


def arcade_color(color, alpha=255):
    return Color(int(color[0]), int(color[1]), int(color[2]), int(alpha))


class FontMetrics:
    def __init__(self, size):
        self.size = size

    def render(self, text, *_args, **_kwargs):
        return TextMetrics(text, self.size)


class TextMetrics:
    def __init__(self, text, size):
        self.text = str(text)
        self.size = size

    def get_width(self):
        return max(1, int(len(self.text) * self.size * 0.65))

    def get_height(self):
        return max(1, int(self.size * 1.6))


class Game(arcade.Window):
    def __init__(self):
        super().__init__(
            WINDOW_WIDTH,
            WINDOW_HEIGHT,
            "Cursed Crossing",
            update_rate=1 / FPS,
            draw_rate=1 / FPS,
            center_window=True,
            vsync=True,
        )
        arcade.set_background_color(COLORS["bg"])

        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(base_dir, "data", "entities")
        gameplay_dir = os.path.join(base_dir, "data", "gameplay", "config")
        config_dir = os.path.join(base_dir, "config")
        textures_dir = os.path.join(base_dir, "assets", "textures")
        font_path = os.path.join(base_dir, "assets", "font", "main.ttf")
        icon_path = os.path.join(textures_dir, "icon", "icon.png")
        settings_path = os.path.join(config_dir, "settings.json")

        self.set_window_icon(icon_path)
        self.menu_font = FontMetrics(6)
        self.font_path = font_path
        self.hud_font_name = "main"
        self.pause_overlay = PauseOverlay(None)
        self.entity_defs = load_entity_defs(data_dir)
        self.textures = TextureManager(textures_dir)
        keybinds_path = os.path.join(config_dir, "keybinds.json")
        if not os.path.exists(keybinds_path):
            keybinds_path = os.path.join(gameplay_dir, "keybinds.json")
        self.movement = load_movement(keybinds_path)

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

        self.game_state = GameStateController()

        blocks_path = os.path.join(base_dir, "data", "blocks", "blocks.json")
        self.block_defs = load_block_defs(blocks_path, base_dir)
        self.blocks = build_blocks(self.region, self.block_defs, self.textures)
        self.background_blocks = build_background_blocks(self.region, self.block_defs, self.textures)
        self.camera = Vec2(0, 0)
        self.frame_cache = {}

        rain_def = self.entity_defs.get("environment.rain", {})
        self.title_rain = RainSystem(rain_def)
        self.region_particle_effects = self.build_region_particle_effects(rain_def)

        self.animation_cache = {}
        self.pressed_keys = set()
        self.mouse_logical = (0, 0)
        self.current_fps = 0.0
        self.text_cache = {}
        self.hover_texture_cache = {}

        self.player_pos = Vec2(0, 0)
        self.player_dir = "down"
        self.player_anim_time = 0.0
        self.player_is_moving = False
        self.player_was_moving = False
        self.player_mask = None
        self.player_collider_cache = {}
        self.settings_return_state = "menu"
        self.reset_player()
        self.apply_display_mode()

    def set_window_icon(self, icon_path):
        if not os.path.exists(icon_path):
            return
        try:
            icon_image = Image.open(icon_path).convert("RGBA")
            icons = []
            for size in (16, 32, 48, 64, 128, 256):
                resized = icon_image.resize((size, size), Image.Resampling.LANCZOS)
                icons.append(pyglet.image.ImageData(size, size, "RGBA", resized.tobytes(), pitch=-size * 4))
            self.set_icon(*icons)
        except Exception:
            return

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

    @property
    def logical_scale(self):
        return min(self.width / LOGICAL_WIDTH, self.height / LOGICAL_HEIGHT)

    @property
    def viewport_rect(self):
        scale = self.logical_scale
        width = int(LOGICAL_WIDTH * scale)
        height = int(LOGICAL_HEIGHT * scale)
        x = int((self.width - width) / 2)
        y = int((self.height - height) / 2)
        return Rect(x, y, width, height)

    def apply_display_mode(self):
        if self.settings_menu.borderless_fullscreen:
            self.set_fullscreen(True)
            return
        if self.fullscreen:
            self.set_fullscreen(False)
        self.set_size(WINDOW_WIDTH, WINDOW_HEIGHT)

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
            return Vec2(0, 0)
        width, height = self.region["size"]
        tile_size = self.region["tile_size"]
        return Vec2(
            (LOGICAL_WIDTH - width * tile_size) // 2,
            (LOGICAL_HEIGHT - height * tile_size) // 2,
        )

    def get_region_pixel_size(self):
        width, height = self.region["size"]
        tile_size = self.region["tile_size"]
        return width * tile_size, height * tile_size

    def get_player_anchor(self):
        tile_size = self.region["tile_size"]
        return self.player_pos + Vec2(tile_size / 2, tile_size / 2)

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
        return Vec2(cam_x, cam_y)

    def update_camera(self):
        self.camera = self.get_camera_offset()

    def reset_player(self):
        spawn = self.region["player_spawn"]
        tile_size = self.region["tile_size"]
        self.player_pos = Vec2(spawn[0] * tile_size, spawn[1] * tile_size)
        self.player_dir = "down"
        self.player_anim_time = 0.0
        self.player_is_moving = False
        self.player_was_moving = False

    def on_update(self, dt):
        if dt > 0:
            self.current_fps = 1.0 / dt
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

        self.player_mask = self.get_player_collision_mask()
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
            self.pressed_keys,
        )
        self.region_title.update(dt)
        self.update_camera()

    def logical_to_screen_rect(self, rect, camera=False):
        x = rect.x - (self.camera.x if camera else 0)
        y = rect.y - (self.camera.y if camera else 0)
        viewport = self.viewport_rect
        scale = self.logical_scale
        return arcade.LBWH(
            viewport.x + x * scale,
            viewport.y + (LOGICAL_HEIGHT - y - rect.height) * scale,
            rect.width * scale,
            rect.height * scale,
        )

    def mouse_to_logical(self, x, y):
        viewport = self.viewport_rect
        scale = self.logical_scale
        return (
            int((x - viewport.x) / scale),
            int(LOGICAL_HEIGHT - (y - viewport.y) / scale),
        )

    def draw_texture(self, texture, x, y, width, height, camera=False, alpha=255, pixelated=True, color=(255, 255, 255)):
        screen_rect = self.logical_to_screen_rect(Rect(int(x), int(y), int(width), int(height)), camera=camera)
        arcade.draw_texture_rect(texture, screen_rect, color=arcade_color(color, alpha), alpha=alpha, pixelated=pixelated)

    def get_hover_overlay_texture(self, texture):
        key = id(texture)
        cached = self.hover_texture_cache.get(key)
        if cached:
            return cached
        alpha = texture.image.getchannel("A").point(lambda value: int(value * 0.30))
        image = Image.new("RGBA", texture.image.size, (255, 255, 255, 0))
        image.putalpha(alpha)
        cached = arcade.Texture(image)
        self.hover_texture_cache[key] = cached
        return cached

    def draw_hoverable_texture(self, texture, rect, hovered=False):
        self.draw_texture(texture, rect.x, rect.y, rect.width, rect.height)
        if hovered:
            overlay = self.get_hover_overlay_texture(texture)
            self.draw_texture(overlay, rect.x, rect.y, rect.width, rect.height)

    def draw_rect(self, rect, color, camera=False, alpha=255):
        arcade.draw_rect_filled(self.logical_to_screen_rect(rect, camera=camera), (*color, alpha))

    def draw_rect_outline(self, rect, color, camera=False, width=1, alpha=255):
        arcade.draw_rect_outline(self.logical_to_screen_rect(rect, camera=camera), (*color, alpha), max(1, width * self.logical_scale))

    def draw_pixel_panel(self, rect, color, alpha=255, notch=2):
        notch = max(1, int(notch))
        inner_w = max(1, rect.width - notch * 2)
        inner_h = max(1, rect.height - notch * 2)
        self.draw_rect(Rect(rect.x + notch, rect.y, inner_w, rect.height), color, alpha=alpha)
        self.draw_rect(Rect(rect.x, rect.y + notch, rect.width, inner_h), color, alpha=alpha)
        if notch > 1:
            self.draw_rect(Rect(rect.x + 1, rect.y + 1, rect.width - 2, rect.height - 2), color, alpha=alpha)

    def get_text_texture(self, text, color, font_size=8, alpha=255):
        text = str(text)
        cache_key = (text, tuple(color), int(font_size), int(alpha))
        cached = self.text_cache.get(cache_key)
        if cached:
            return cached

        font = ImageFont.truetype(self.font_path, max(1, int(font_size)))
        bbox = font.getbbox(text)
        width = max(1, bbox[2] - bbox[0])
        height = max(1, bbox[3] - bbox[1])
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.text((-bbox[0], -bbox[1]), text, font=font, fill=(*color, int(alpha)))
        solid_alpha = image.getchannel("A").point(lambda value: int(alpha) if value >= 128 else 0)
        image = Image.new("RGBA", image.size, (*color, 0))
        image.putalpha(solid_alpha)
        visible_bounds = image.getchannel("A").getbbox()
        if visible_bounds:
            image = image.crop(visible_bounds)
            width, height = image.size
        cached = (arcade.Texture(image), width, height)
        self.text_cache[cache_key] = cached
        return cached

    def draw_text_top_left(self, text, x, y, color, font_size=8, anchor_x="left", anchor_y="top", alpha=255):
        texture, width, height = self.get_text_texture(text, color, font_size, alpha)
        draw_x = x
        if anchor_x == "center":
            draw_x -= width / 2
        elif anchor_x == "right":
            draw_x -= width

        draw_y = y
        if anchor_y == "center":
            draw_y -= height / 2
        elif anchor_y in ("bottom", "baseline"):
            draw_y -= height

        self.draw_texture(texture, draw_x, draw_y, width, height, alpha=alpha, pixelated=True)

    def on_draw(self):
        self.clear()
        if self.state == "menu":
            self.draw_menu_background()
            self.draw_menu()
            self.draw_exit_button()
        elif self.state == "settings":
            self.draw_menu_background()
            self.draw_settings_menu()
        elif self.state == "pause":
            self.draw_game_layers(include_titles=False)
            if self.show_block_id_overlay:
                self.draw_block_id_overlay()
            if self.show_hitboxes:
                self.draw_hitboxes()
            self.draw_pause_overlay()
        else:
            self.draw_game_layers(include_titles=False)
            if self.show_block_id_overlay:
                self.draw_block_id_overlay()
            if self.show_hitboxes:
                self.draw_hitboxes()
            self.draw_region_title()

        if self.show_fps:
            self.draw_fps()
        self.draw_transition_overlay()

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
        stages = {
            "region_background": self.draw_region_background,
            "background_blocks": lambda: self.draw_block_collection(self.background_blocks),
            "region_border": self.draw_region_border,
            "blocks": lambda: self.draw_block_collection(self.blocks),
            "player": self.draw_player,
            "particles": self.draw_region_particles,
            "fog": self.draw_region_effects,
            "titles": self.draw_region_title,
        }
        for stage_name in self.get_render_stage_names(include_titles):
            stages[stage_name]()

    def draw_region_background(self):
        self.draw_rect(Rect(0, 0, LOGICAL_WIDTH, LOGICAL_HEIGHT), tuple(self.region["color"]))

    def draw_region_border(self):
        if not self.region["border_enabled"]:
            return
        world_w, world_h = self.get_region_pixel_size()
        self.draw_rect_outline(Rect(0, 0, world_w, world_h), tuple(self.region["border_color"]), camera=True)

    def block_tint(self, block_def):
        brightness = float(block_def.get("brightness", 1.0))
        if brightness >= 1.0:
            return (255, 255, 255)
        value = max(0, min(255, int(255 * brightness)))
        return (value, value, value)

    def draw_block_collection(self, blocks):
        for block in blocks:
            block_def = block["definition"]
            texture = self.textures.get_arcade(block_def.get("texture"))
            draw_pos = block["draw_pos"] + block["sprite_offset"]
            size = block["sprite_size"]
            self.draw_texture(
                texture,
                draw_pos.x,
                draw_pos.y,
                int(size[0]),
                int(size[1]),
                camera=True,
                color=self.block_tint(block_def),
            )

    def draw_region_particles(self):
        for particle_system in self.region_particle_effects:
            self.draw_particles(particle_system, camera=False)

    def draw_particles(self, particle_system, camera=False):
        for particle in particle_system.particles:
            size = tuple(particle.get("size", (2, 4)))
            frame = self.textures.get(particle["texture"], size)
            texture = self.textures.get_arcade_from_frame(frame, ("particle", particle["texture"], size))
            alpha = 255
            if particle_system.fade:
                remaining = max(0.0, 1.0 - particle["age"] / particle_system.lifetime)
                alpha = int(255 * remaining)
            self.draw_texture(texture, particle["pos"].x, particle["pos"].y, size[0], size[1], camera=camera, alpha=alpha)

    def draw_region_effects(self):
        light_level = float(self.region.get("light_level", 1.0))
        if light_level < 1.0:
            alpha = max(0, min(255, int(255 * (1.0 - light_level))))
            self.draw_rect(Rect(0, 0, LOGICAL_WIDTH, LOGICAL_HEIGHT), (0, 0, 0), alpha=alpha)
        elif light_level > 1.0:
            alpha = int(255 * min(1.0, (light_level - 1.0) * 0.5))
            self.draw_rect(Rect(0, 0, LOGICAL_WIDTH, LOGICAL_HEIGHT), (255, 255, 255), alpha=alpha)
        if self.region["fog"]["enabled"]:
            self.draw_rect(
                Rect(0, 0, LOGICAL_WIDTH, LOGICAL_HEIGHT),
                tuple(self.region["fog"]["color"]),
                alpha=self.region["fog"]["alpha"],
            )

    def draw_region_title(self):
        if not self.region_title.active:
            return
        image_path = self.region_title.config.get("image")
        if not image_path:
            return
        base_size = self.textures.get_image_size(image_path)
        if not base_size:
            return
        scale = max(0.01, float(self.region_title.config.get("scale", 1.0)))
        logical_size = (max(1, int(base_size[0] * scale)), max(1, int(base_size[1] * scale)))
        duration = max(0.0, float(self.region_title.config.get("duration", 0.0)))
        fade = max(0.0, float(self.region_title.config.get("fade_duration", 0.0)))
        alpha = 255
        if fade > 0.0 and self.region_title.time > duration:
            remaining = max(0.0, duration + fade - self.region_title.time)
            alpha = int(255 * min(1.0, remaining / fade))
        texture = self.textures.get_arcade(image_path)
        self.draw_texture(
            texture,
            LOGICAL_WIDTH / 2 - logical_size[0] / 2,
            LOGICAL_HEIGHT / 2 - logical_size[1] / 2,
            logical_size[0],
            logical_size[1],
            alpha=alpha,
        )

    def draw_player(self):
        raw_frame, render_scale = self.get_player_source_frame()
        if not raw_frame:
            return
        logical_size = self.get_player_logical_size(raw_frame, render_scale)
        draw_pos = self.get_player_draw_pos_from_size(logical_size)
        texture = self.textures.get_arcade_from_frame(raw_frame, ("player", id(raw_frame)))
        self.draw_texture(texture, draw_pos.x + self.camera.x, draw_pos.y + self.camera.y, *logical_size, camera=True)

    def draw_menu_background(self):
        self.draw_rect(Rect(0, 0, LOGICAL_WIDTH, LOGICAL_HEIGHT), COLORS["bg"])
        if self.settings_menu.show_rain:
            self.draw_particles(self.title_rain)

    def menu_buttons(self):
        layout = self.character_select.get_menu_layout(self.animation_cache)
        button_w = 120
        button_h = 18
        button_gap = 8
        center_x = LOGICAL_WIDTH // 2 - button_w // 2
        start_rect = Rect(center_x, layout["buttons_top"], button_w, button_h)
        settings_rect = Rect(center_x, layout["buttons_top"] + button_h + button_gap, button_w, button_h)
        return {"start": start_rect, "settings": settings_rect}

    def draw_menu(self):
        layout = self.character_select.get_menu_layout(self.animation_cache)
        self.draw_character_select()
        title_size = (210, 21)
        title_texture = self.textures.get_arcade("ui/title_text.png")
        title_x = LOGICAL_WIDTH // 2 - title_size[0] // 2
        self.draw_texture(title_texture, title_x, layout["title_y"], *title_size)
        for key, rect in self.menu_buttons().items():
            label = "START GAME" if key == "start" else "SETTINGS"
            self.draw_button(rect, label, self.hovered_button == key)

    def draw_character_select(self):
        character_def = self.character_select.get_selected_character()
        if not character_def:
            return
        anim_id = character_def.get("idle") or character_def.get("walk")
        animation = self.character_select.get_animation(anim_id, self.animation_cache)
        if not animation:
            return
        frames, fps = self.character_select.get_animation_frames(animation, "right")
        frame_index = int(self.character_select.menu_anim_time * fps) % len(frames)
        frame = frames[frame_index]
        rects = self.character_select.character_select_rects(self.animation_cache)
        if not rects:
            return

        prev_frame, next_frame = self.character_select.get_neighbor_preview_frames(self.animation_cache)
        if prev_frame:
            preview_rect = prev_frame.get_rect(midright=(rects["left"].left - 6, rects["left"].centery))
            self.draw_surface_frame(prev_frame, preview_rect.x, preview_rect.y, alpha=140)
        if next_frame:
            preview_rect = next_frame.get_rect(midleft=(rects["right"].right + 6, rects["right"].centery))
            self.draw_surface_frame(next_frame, preview_rect.x, preview_rect.y, alpha=140)

        left_texture = self.textures.get_arcade("ui/left.png")
        right_texture = self.textures.get_arcade("ui/right.png")
        self.draw_hoverable_texture(left_texture, rects["left"], self.character_select.hovered_arrow == "left")
        self.draw_hoverable_texture(right_texture, rects["right"], self.character_select.hovered_arrow == "right")
        self.draw_surface_frame(frame, rects["sprite"].x, rects["sprite"].y)

    def draw_surface_frame(self, frame, x, y, alpha=255):
        texture = self.textures.get_arcade_from_frame(frame, ("frame", id(frame)))
        self.draw_texture(texture, x, y, frame.get_width(), frame.get_height(), alpha=alpha)

    def draw_button(self, rect, label, hovered):
        base = COLORS["warning"] if hovered else COLORS["track"]
        self.draw_pixel_panel(rect, base, notch=2)
        self.draw_text_top_left(label, rect.centerx, rect.centery, (255, 255, 255), font_size=6, anchor_x="center", anchor_y="center")

    def get_exit_button_rect(self):
        size = 14
        margin = 4
        return Rect(margin, LOGICAL_HEIGHT - size - margin, size, size)

    def draw_exit_button(self):
        rect = self.get_exit_button_rect()
        base = COLORS["warning"] if rect.collidepoint(self.mouse_logical) else COLORS["track"]
        self.draw_pixel_panel(rect, base, notch=2)
        self.draw_text_top_left("X", rect.centerx, rect.centery, (255, 255, 255), font_size=6, anchor_x="center", anchor_y="center")

    def draw_settings_menu(self):
        layout = self.settings_menu.get_settings_layout(self.menu_font)
        self.draw_text_top_left("SETTINGS", LOGICAL_WIDTH // 2, layout["title_y"], COLORS["text"], font_size=6, anchor_x="center")
        for key, rect in self.settings_menu.settings_buttons(self.menu_font).items():
            if key == "show_fps":
                label = f"SHOW FPS: {'ON' if self.settings_menu.show_fps else 'OFF'}"
            elif key == "show_rain":
                label = f"SHOW RAIN: {'ON' if self.settings_menu.show_rain else 'OFF'}"
            elif key == "borderless_fullscreen":
                label = f"BORDERLESS FULLSCREEN: {'ON' if self.settings_menu.borderless_fullscreen else 'OFF'}"
            elif key == "show_block_id_overlay":
                label = f"BLOCK ID OVERLAY: {'ON' if self.settings_menu.show_block_id_overlay else 'OFF'}"
            elif key == "show_hitboxes":
                label = f"SHOW HITBOXES: {'ON' if self.settings_menu.show_hitboxes else 'OFF'}"
            else:
                label = "BACK"
            self.draw_button(rect, label, self.settings_menu.hovered_setting == key)

    def draw_pause_overlay(self):
        self.draw_rect(Rect(0, 0, LOGICAL_WIDTH, LOGICAL_HEIGHT), (0, 0, 0), alpha=100)
        self.draw_text_top_left("PAUSED", LOGICAL_WIDTH // 2, LOGICAL_HEIGHT // 2 - 40, COLORS["warning"], font_size=6, anchor_x="center")
        for key, rect in self.pause_overlay.get_button_rects().items():
            label = self.pause_overlay.get_button_label(key)
            self.draw_button(rect, label, self.hovered_button == key)

    def draw_fps(self):
        self.draw_text_top_left(f"FPS {self.current_fps:.0f}", 4, 4, COLORS["text"], font_size=8)

    def draw_block_id_overlay(self):
        tile_size = int(self.region["tile_size"])
        region_width = int(self.region["size"][0])
        region_height = int(self.region["size"][1])
        for tile_y in range(region_height):
            for tile_x in range(region_width):
                block_number = coords_to_block_number(tile_x, tile_y, region_width, region_height)
                rect = Rect(tile_x * tile_size, tile_y * tile_size, tile_size, tile_size)
                self.draw_rect_outline(rect, (110, 110, 110), camera=True)
                screen = self.logical_to_screen_rect(rect, camera=True)
                viewport = self.viewport_rect
                logical_x = (screen.x - viewport.x) / self.logical_scale
                logical_y = LOGICAL_HEIGHT - (screen.y - viewport.y) / self.logical_scale
                self.draw_text_top_left(
                    str(block_number),
                    logical_x,
                    logical_y,
                    (235, 235, 235),
                    font_size=8,
                    anchor_x="center",
                    anchor_y="center",
                )

    def draw_hitboxes(self):
        for block in self.blocks:
            for rect in block.get("debug_hitboxes", []):
                self.draw_rect_outline(rect, HITBOX_COLORS["block"], camera=True, width=2)
        player_rect = self.get_player_collision_rect()
        if player_rect:
            world_rect = Rect(
                int(player_rect.x + self.camera.x),
                int(player_rect.y + self.camera.y),
                player_rect.width,
                player_rect.height,
            )
            self.draw_rect_outline(world_rect, HITBOX_COLORS["player"], camera=True, width=2)

    def draw_transition_overlay(self):
        alpha = self.game_state.get_transition_alpha()
        if alpha > 0:
            self.draw_rect(Rect(0, 0, LOGICAL_WIDTH, LOGICAL_HEIGHT), (0, 0, 0), alpha=alpha)

    def on_mouse_motion(self, x, y, dx, dy):
        self.mouse_logical = self.mouse_to_logical(x, y)
        if self.state == "menu":
            self.update_menu_hover()
        elif self.state == "pause":
            self.update_pause_hover()
        elif self.state == "settings":
            self.update_settings_hover()

    def on_mouse_press(self, x, y, button, modifiers):
        self.mouse_logical = self.mouse_to_logical(x, y)
        if button != arcade.MOUSE_BUTTON_LEFT:
            return
        if self.state == "menu":
            if self.get_exit_button_rect().collidepoint(self.mouse_logical):
                self.close()
                return
            self.handle_menu_click()
        elif self.state == "settings":
            self.handle_settings_click()
        elif self.state == "pause":
            self.handle_pause_click()

    def on_key_press(self, symbol, modifiers):
        self.pressed_keys.add(symbol)
        if self.state == "menu":
            if symbol == arcade.key.ENTER:
                self.start_transition(self.reset)
            elif symbol == arcade.key.LEFT:
                self.character_select.select_previous_character()
            elif symbol == arcade.key.RIGHT:
                self.character_select.select_next_character()
            return
        if self.state == "settings":
            if symbol == arcade.key.ESCAPE:
                self.state = self.resolve_settings_return_state("menu")
                self.apply_display_mode()
            return
        if self.state == "pause":
            pause_keys = self.movement["bindings"].get("pause", set())
            if symbol == arcade.key.ENTER or symbol in pause_keys:
                self.state = "play"
            return
        if symbol == arcade.key.R:
            self.reset()
        if symbol in self.movement["bindings"].get("pause", set()):
            self.state = "pause"

    def on_key_release(self, symbol, modifiers):
        self.pressed_keys.discard(symbol)

    def update_menu_hover(self):
        self.hovered_button = None
        self.character_select.hovered_arrow = None
        for key, rect in self.menu_buttons().items():
            if rect.collidepoint(self.mouse_logical):
                self.hovered_button = key
                break
        select_rects = self.character_select.character_select_rects(self.animation_cache)
        if select_rects:
            if select_rects["left"].collidepoint(self.mouse_logical):
                self.character_select.hovered_arrow = "left"
            elif select_rects["right"].collidepoint(self.mouse_logical):
                self.character_select.hovered_arrow = "right"

    def handle_menu_click(self):
        select_rects = self.character_select.character_select_rects(self.animation_cache)
        if select_rects and select_rects["left"].collidepoint(self.mouse_logical):
            self.character_select.select_previous_character()
            return
        if select_rects and select_rects["right"].collidepoint(self.mouse_logical):
            self.character_select.select_next_character()
            return
        buttons = self.menu_buttons()
        if buttons["start"].collidepoint(self.mouse_logical):
            self.start_transition(self.reset)
        elif buttons["settings"].collidepoint(self.mouse_logical):
            self.settings_return_state = "menu"
            self.state = "settings"

    def update_pause_hover(self):
        self.hovered_button = None
        for key, rect in self.pause_overlay.get_button_rects().items():
            if rect.collidepoint(self.mouse_logical):
                self.hovered_button = key
                break

    def handle_pause_click(self):
        buttons = self.pause_overlay.get_button_rects()
        if buttons["resume"].collidepoint(self.mouse_logical):
            self.state = "play"
        elif buttons["settings"].collidepoint(self.mouse_logical):
            self.settings_return_state = "pause"
            self.state = "settings"
        elif buttons["title"].collidepoint(self.mouse_logical):
            self.state = "menu"

    def update_settings_hover(self):
        self.settings_menu.hovered_setting = None
        for key, rect in self.settings_menu.settings_buttons(self.menu_font).items():
            if rect.collidepoint(self.mouse_logical):
                self.settings_menu.hovered_setting = key
                break

    def handle_settings_click(self):
        buttons = self.settings_menu.settings_buttons(self.menu_font)
        if buttons["show_fps"].collidepoint(self.mouse_logical):
            self.settings_menu.toggle_fps()
        elif buttons["show_rain"].collidepoint(self.mouse_logical):
            self.settings_menu.toggle_rain()
        elif buttons["borderless_fullscreen"].collidepoint(self.mouse_logical):
            self.settings_menu.toggle_borderless_fullscreen()
            self.apply_display_mode()
        elif "show_block_id_overlay" in buttons and buttons["show_block_id_overlay"].collidepoint(self.mouse_logical):
            self.settings_menu.toggle_block_id_overlay()
        elif "show_hitboxes" in buttons and buttons["show_hitboxes"].collidepoint(self.mouse_logical):
            self.settings_menu.toggle_hitboxes()
        elif buttons["back"].collidepoint(self.mouse_logical):
            self.state = self.resolve_settings_return_state("menu")
            if self.state == "menu" and self.settings_menu.show_rain:
                self.title_rain.reset()

    def resolve_settings_return_state(self, new_state):
        if new_state == "menu":
            return self.settings_return_state
        return new_state

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
        render_scale = float(character_def.get("scale", 1.0)) if character_def else 1.0
        return frame, render_scale

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
        frame_mask = AlphaMask.from_image(frame.image)
        visible_rects = frame_mask.get_bounding_rects()
        visible_rect = visible_rects[0].unionall(visible_rects[1:]) if visible_rects else Rect(0, 0, frame_w, frame_h)
        hitbox_top = visible_rect.y + visible_rect.height // 2
        return Rect(
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
        left = int(round(tile_size // 2 - width / 2))
        top = int(round(bottom - height))
        return {"mask": AlphaMask((width, height), fill=True), "offset": Vec2(left, top)}

    def get_middle_value(self, values):
        values = sorted(int(value) for value in values)
        return values[len(values) // 2]

    def create_player_collision_mask(self, frame):
        hitbox_rect = self.get_player_frame_footprint_rect(frame)
        if not hitbox_rect:
            return None
        return {"mask": AlphaMask(hitbox_rect.size, fill=True), "offset": Vec2(hitbox_rect.x, hitbox_rect.y)}

    def get_player_collision_rect(self):
        if not self.player_mask:
            return None
        mask = self.player_mask.get("mask")
        offset = Vec2(self.player_mask.get("offset", (0, 0)))
        if not mask:
            return None
        rect = mask.get_rect()
        rect.topleft = (
            int(self.player_pos.x + offset.x - self.camera.x),
            int(self.player_pos.y + offset.y - self.camera.y),
        )
        return rect

    def get_player_draw_pos_from_size(self, size):
        tile_size = int(self.region["tile_size"])
        frame_w, frame_h = size
        offset_x = (tile_size - frame_w) / 2
        offset_y = tile_size - frame_h
        return self.player_pos + Vec2(offset_x, offset_y) - self.camera

    def get_player_logical_size(self, frame, render_scale=1.0):
        tile_size = int(self.region["tile_size"])
        frame_w, frame_h = frame.get_size()
        if frame_w <= 0 or frame_h <= 0:
            return frame.get_size()
        target_h = max(1, int(tile_size * max(0.1, render_scale)))
        scale = target_h / frame_h
        return max(1, int(round(frame_w * scale))), target_h

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
        scaled = frame.resize(target)
        self.frame_cache[cache_key] = scaled
        return scaled

    def map_player_direction(self, direction):
        if direction == "up":
            return "backward"
        if direction == "down":
            return "forward"
        return direction

    def _build_character_list(self, characters):
        characters = list(characters)
        characters.sort(key=lambda item: item.get("display_name", item.get("id", "")))
        return characters

    def get_animation(self, anim_id):
        if not anim_id:
            return None
        if anim_id in self.animation_cache:
            return self.animation_cache[anim_id]
        source_defs = self.character_select.character_animations if anim_id in self.character_select.character_animations else self.entity_defs
        animation = load_animation(source_defs, anim_id, self.textures.root_dir)
        if animation:
            self.animation_cache[anim_id] = animation
        return animation

    def get_animation_frames(self, animation, preferred):
        sequences = animation["sequences"]
        if preferred in sequences:
            return sequences[preferred], animation["fps"]
        first_sequence = next(iter(sequences.values()))
        return first_sequence, animation["fps"]


if __name__ == "__main__":
    configure_windows_taskbar_icon()
    Game()
    arcade.run()
