import json
import os


def load_characters(registry_path, data_root):
    if not os.path.exists(registry_path):
        return [], {}

    with open(registry_path, "r", encoding="utf-8") as handle:
        registry = json.load(handle)

    characters = []
    animations = {}
    base_dir = os.path.dirname(registry_path)
    for entry in registry.get("characters", []):
        character = {
            "id": entry.get("id"),
            "display_name": entry.get("display_name"),
            "selectable": entry.get("selectable", True),
        }
        anim_map = {}
        for name, rel_path in entry.get("animations", {}).items():
            if not rel_path:
                continue
            anim_path = os.path.join(base_dir, rel_path)
            with open(anim_path, "r", encoding="utf-8") as anim_handle:
                anim_def = json.load(anim_handle)
            anim_id = anim_def.get("id") or f"anim.{character['id']}.{name}"
            anim_def["id"] = anim_id
            animations[anim_id] = anim_def
            anim_map[name] = anim_id
        character.update(anim_map)
        if character.get("id"):
            characters.append(character)
    return characters, animations
