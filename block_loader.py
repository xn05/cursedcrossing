import json
import os


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
    solid_rects = sanitize_rects(block_data.get("solid_rects", []))
    passable_rects = sanitize_rects(block_data.get("passable_rects", []))

    return {
        "id": block_data.get("id"),
        "name": block_data.get("name"),
        "texture": block_data.get("texture"),
        "size": size,
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


def normalize_origin(origin, size):
    if not origin:
        return [0, max(0, size[1] - 1)]
    origin = sanitize_size(origin)
    if 1 <= origin[0] <= size[0] and 1 <= origin[1] <= size[1]:
        origin = [origin[0] - 1, origin[1] - 1]
    origin[0] = max(0, min(origin[0], size[0] - 1))
    origin[1] = max(0, min(origin[1], size[1] - 1))
    return origin

