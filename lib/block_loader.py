import json
import os

from lib.block_numbering import block_number_to_coords


def load_block_defs(registry_path, base_dir):
    if not os.path.exists(registry_path):
        return {}
    with open(registry_path, "r", encoding="utf-8-sig") as handle:
        data = json.load(handle)

    blocks = {}
    for entry in data.get("blocks", []):
        path = entry.get("path")
        if not path:
            continue
        block_path = os.path.join(base_dir, path)
        if not os.path.exists(block_path):
            continue
        with open(block_path, "r", encoding="utf-8-sig") as handle:
            block_data = json.load(handle)
        block_id = block_data.get("id") or entry.get("id")
        if not block_id:
            continue
        blocks[block_id] = normalize_block_def(block_data)
    return blocks


def normalize_block_def(block_data):
    size = sanitize_size(block_data.get("size", [1, 1]))
    size = [max(1, size[0]), max(1, size[1])]
    texture_size = block_data.get("texture_size")
    origin = normalize_origin(block_data.get("origin"), size)
    solid_rects = normalize_solid_rects(block_data.get("solid_rects", []), size)
    passable_rects = sanitize_rects(block_data.get("passable_rects", []))
    hitbox_type = str(block_data.get("hitbox_type", block_data.get("hitbox", "pixel"))).lower()
    if hitbox_type not in ("rectangle", "pixel", "square"):
        hitbox_type = "pixel"

    return {
        "id": block_data.get("id"),
        "name": block_data.get("name"),
        "texture": block_data.get("texture"),
        "size": size,
        "brightness": max(0.0, float(block_data.get("brightness", 1.0))),
        "hitbox_type": hitbox_type,
        "hitbox_ratio": max(0.0, float(block_data.get("hitbox_ratio", 1.0))),
        "texture_size": sanitize_size(texture_size) if texture_size else None,
        "origin": origin,
        "solid_rects": solid_rects,
        "passable_rects": passable_rects,
        "stretch_to_fit": bool(block_data.get("stretch_to_fit", True)),
    }


def sanitize_size(value):
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return [0, 0]
    return [int(value[0]), int(value[1])]


def sanitize_rects(rects):
    sanitized = []
    for rect in rects:
        if not isinstance(rect, (list, tuple)) or len(rect) < 4:
            continue
        sanitized.append([int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])])
    return sanitized


def normalize_solid_rects(value, size):
    if value is None:
        return []
    if isinstance(value, int):
        value = [value]
    if not isinstance(value, list):
        return []
    if not value:
        return []

    if all(isinstance(item, int) for item in value):
        return number_rects_to_legacy_rects(value, size)

    sanitized = []
    for item in value:
        if isinstance(item, int):
            sanitized.extend(number_rects_to_legacy_rects([item], size))
        elif isinstance(item, (list, tuple)) and all(isinstance(num, int) for num in item):
            if len(item) == 1:
                sanitized.extend(number_rects_to_legacy_rects([item[0]], size))
            elif len(item) == 2:
                sanitized.append(number_fill_to_legacy_rect(item[0], item[1], size))
            elif len(item) >= 4:
                sanitized.append([int(item[0]), int(item[1]), int(item[2]), int(item[3])])
    return [rect for rect in sanitized if rect and rect[2] > 0 and rect[3] > 0]


def number_rects_to_legacy_rects(numbers, size):
    rects = []
    for number in numbers:
        coords = block_number_to_coords(int(number), size[0], size[1])
        if coords:
            rects.append([coords[0], coords[1], 1, 1])
    return rects


def number_fill_to_legacy_rect(start_number, end_number, size):
    start = block_number_to_coords(int(start_number), size[0], size[1])
    end = block_number_to_coords(int(end_number), size[0], size[1])
    if not start or not end:
        return None
    x1, y1 = start
    x2, y2 = end
    min_x, max_x = min(x1, x2), max(x1, x2)
    min_y, max_y = min(y1, y2), max(y1, y2)
    return [min_x, min_y, max_x - min_x + 1, max_y - min_y + 1]


def normalize_origin(origin, size):
    if not origin:
        return [0, max(0, size[1] - 1)]
    if isinstance(origin, int):
        coords = block_number_to_coords(origin, size[0], size[1])
        if coords:
            return [coords[0], coords[1]]
        return [0, max(0, size[1] - 1)]
    origin = sanitize_size(origin)
    if 1 <= origin[0] <= size[0] and 1 <= origin[1] <= size[1]:
        origin = [origin[0] - 1, origin[1] - 1]
    origin[0] = max(0, min(origin[0], size[0] - 1))
    origin[1] = max(0, min(origin[1], size[1] - 1))
    return origin


