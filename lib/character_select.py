import pygame

from lib.animation_loader import load_animation
from lib.settings import COLORS, LOGICAL_WIDTH, LOGICAL_HEIGHT


class CharacterSelect:
    def __init__(self, characters, character_animations, textures):
        self.characters = characters
        self.character_animations = character_animations
        self.textures = textures
        self.selected_character_index = 0
        self.menu_anim_time = 0.0
        self.hovered_arrow = None

    def update(self, dt):
        self.menu_anim_time += dt

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

    def get_selected_character(self):
        if not self.characters:
            return None
        return self.characters[self.selected_character_index]

    def build_character_list(self, characters):
        characters = list(characters)
        characters.sort(key=lambda item: item.get("display_name", item.get("id", "")))
        return characters

    def get_animation(self, anim_id, animation_cache):
        if not anim_id:
            return None
        if anim_id in animation_cache:
            return animation_cache[anim_id]
        if anim_id in self.character_animations:
            source_defs = self.character_animations
        else:
            return None
        animation = load_animation(source_defs, anim_id, self.textures.root_dir)
        if not animation:
            return None
        animation_cache[anim_id] = animation
        return animation

    def get_animation_frames(self, animation, preferred):
        sequences = animation["sequences"]
        if preferred in sequences:
            return sequences[preferred], animation["fps"]
        first_sequence = next(iter(sequences.values()))
        return first_sequence, animation["fps"]

    def get_character_select_height(self, animation_cache):
        character_def = self.get_selected_character()
        if not character_def:
            return 32
        anim_id = character_def.get("idle") or character_def.get("walk")
        animation = self.get_animation(anim_id, animation_cache)
        if not animation:
            return 32
        return animation["frame_size"][1]

    def get_menu_layout(self, animation_cache):
        title_sprite = self.textures.get("ui/title_text.png", (210, 21))
        title_h = title_sprite.get_height()
        selector_h = self.get_character_select_height(animation_cache)
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

    def get_neighbor_preview_frames(self, animation_cache):
        if not self.characters or len(self.characters) < 2:
            return None, None
        prev_index = (self.selected_character_index - 1) % len(self.characters)
        next_index = (self.selected_character_index + 1) % len(self.characters)
        prev_frame = self.get_character_preview_frame(self.characters[prev_index], animation_cache)
        next_frame = self.get_character_preview_frame(self.characters[next_index], animation_cache)
        return prev_frame, next_frame

    def get_character_preview_frame(self, character_def, animation_cache):
        anim_id = character_def.get("idle") or character_def.get("walk")
        animation = self.get_animation(anim_id, animation_cache)
        if not animation:
            return None
        frames, fps = self.get_animation_frames(animation, "right")
        frame_index = int(self.menu_anim_time * fps) % len(frames)
        return frames[frame_index]

    def brighten_sprite(self, sprite, amount):
        overlay = sprite.copy()
        boost = int(255 * amount)
        overlay.fill((boost, boost, boost, 0), special_flags=pygame.BLEND_RGBA_ADD)
        return overlay

    def character_select_rects(self, animation_cache):
        character_def = self.get_selected_character()
        if not character_def:
            return None
        anim_id = character_def.get("idle") or character_def.get("walk")
        animation = self.get_animation(anim_id, animation_cache)
        if not animation:
            return None
        frame_size = animation["frame_size"]
        layout = self.get_menu_layout(animation_cache)
        center_y = layout["selector_center_y"]
        center_x = LOGICAL_WIDTH // 2
        sprite_rect = pygame.Rect(0, 0, frame_size[0], frame_size[1])
        sprite_rect.center = (center_x, center_y)
        left_rect = pygame.Rect(0, 0, 8, 13)
        right_rect = pygame.Rect(0, 0, 8, 13)
        left_rect.midright = (sprite_rect.left - 6, sprite_rect.centery)
        right_rect.midleft = (sprite_rect.right + 6, sprite_rect.centery)
        return {"left": left_rect, "right": right_rect, "sprite": sprite_rect}

    def draw(self, surface, animation_cache):
        character_def = self.get_selected_character()
        if not character_def:
            return
        anim_id = character_def.get("idle") or character_def.get("walk")
        animation = self.get_animation(anim_id, animation_cache)
        if not animation:
            return
        frames, fps = self.get_animation_frames(animation, "right")
        frame_index = int(self.menu_anim_time * fps) % len(frames)
        frame = frames[frame_index]
        center_x = LOGICAL_WIDTH // 2
        layout = self.get_menu_layout(animation_cache)
        center_y = layout["selector_center_y"]
        sprite_rect = frame.get_rect(center=(center_x, center_y))
        left_sprite = self.textures.get("ui/left.png", (8, 13))
        right_sprite = self.textures.get("ui/right.png", (8, 13))
        left_rect = left_sprite.get_rect(midright=(sprite_rect.left - 6, sprite_rect.centery))
        right_rect = right_sprite.get_rect(midleft=(sprite_rect.right + 6, sprite_rect.centery))
        if self.hovered_arrow == "left":
            left_sprite = self.brighten_sprite(left_sprite, 0.25)
        if self.hovered_arrow == "right":
            right_sprite = self.brighten_sprite(right_sprite, 0.25)
        prev_frame, next_frame = self.get_neighbor_preview_frames(animation_cache)
        if prev_frame:
            preview = prev_frame.copy()
            preview.set_alpha(140)
            preview_rect = preview.get_rect(midright=(left_rect.left - 6, sprite_rect.centery))
            surface.blit(preview, preview_rect)
        if next_frame:
            preview = next_frame.copy()
            preview.set_alpha(140)
            preview_rect = preview.get_rect(midleft=(right_rect.right + 6, sprite_rect.centery))
            surface.blit(preview, preview_rect)
        surface.blit(left_sprite, left_rect)
        surface.blit(frame, sprite_rect)
        surface.blit(right_sprite, right_rect)

