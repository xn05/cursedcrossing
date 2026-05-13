from lib.animation_loader import load_animation
from lib.geometry import Rect
from lib.settings import LOGICAL_WIDTH, LOGICAL_HEIGHT


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
        if self.characters:
            self.selected_character_index = (self.selected_character_index - 1) % len(self.characters)
            self.menu_anim_time = 0.0

    def select_next_character(self):
        if self.characters:
            self.selected_character_index = (self.selected_character_index + 1) % len(self.characters)
            self.menu_anim_time = 0.0

    def get_selected_character(self):
        if not self.characters:
            return None
        return self.characters[self.selected_character_index]

    def get_animation(self, anim_id, animation_cache):
        if not anim_id:
            return None
        if anim_id in animation_cache:
            return animation_cache[anim_id]
        if anim_id not in self.character_animations:
            return None
        animation = load_animation(self.character_animations, anim_id, self.textures.root_dir)
        if animation:
            animation_cache[anim_id] = animation
        return animation

    def get_animation_frames(self, animation, preferred):
        sequences = animation["sequences"]
        if preferred in sequences:
            return sequences[preferred], animation["fps"]
        return next(iter(sequences.values())), animation["fps"]

    def get_selector_slot_size(self, animation_cache):
        max_w = 32
        max_h = 32
        for character in self.characters:
            anim_id = character.get("idle") or character.get("walk")
            animation = self.get_animation(anim_id, animation_cache)
            if not animation:
                continue
            width, height = animation.get("frame_size", (0, 0))
            max_w = max(max_w, width)
            max_h = max(max_h, height)
        return max_w, max_h

    def get_menu_layout(self, animation_cache):
        title_sprite = self.textures.get("ui/title_text.png", (210, 21))
        title_h = title_sprite.get_height()
        selector_h = self.get_selector_slot_size(animation_cache)[1]
        selector_gap = 6
        title_gap = 12
        button_h = 18
        button_gap = 8
        buttons_h = button_h * 2 + button_gap
        total_h = selector_h + selector_gap + title_h + title_gap + buttons_h
        top_y = (LOGICAL_HEIGHT - total_h) // 2
        return {
            "selector_center_y": top_y + selector_h // 2,
            "title_y": top_y + selector_h + selector_gap,
            "buttons_top": top_y + selector_h + selector_gap + title_h + title_gap,
        }

    def get_neighbor_preview_frames(self, animation_cache):
        if not self.characters or len(self.characters) < 2:
            return None, None
        prev_index = (self.selected_character_index - 1) % len(self.characters)
        next_index = (self.selected_character_index + 1) % len(self.characters)
        return (
            self.get_character_preview_frame(self.characters[prev_index], animation_cache),
            self.get_character_preview_frame(self.characters[next_index], animation_cache),
        )

    def get_character_preview_frame(self, character_def, animation_cache):
        anim_id = character_def.get("idle") or character_def.get("walk")
        animation = self.get_animation(anim_id, animation_cache)
        if not animation:
            return None
        frames, fps = self.get_animation_frames(animation, "right")
        return frames[int(self.menu_anim_time * fps) % len(frames)]

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
        slot_w, slot_h = self.get_selector_slot_size(animation_cache)
        slot_rect = Rect(0, 0, slot_w, slot_h)
        slot_rect.center = (center_x, center_y)
        sprite_rect = Rect(0, 0, frame_size[0], frame_size[1])
        sprite_rect.center = (center_x, center_y)
        left_rect = Rect(0, 0, 8, 13)
        right_rect = Rect(0, 0, 8, 13)
        arrow_gap = 6
        left_rect.midright = (slot_rect.left - arrow_gap, slot_rect.centery)
        right_rect.midleft = (slot_rect.right + arrow_gap, slot_rect.centery)
        return {"left": left_rect, "right": right_rect, "sprite": sprite_rect}
