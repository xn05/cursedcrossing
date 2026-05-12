import pygame
from lib.block_numbering import block_number_to_coords


def get_block_positions(placement, region_size):
    """
    Get block positions from number-based fields, with coordinate fields kept
    as a legacy fallback.

    Args:
        placement: Block placement dict
        region_size: [width, height] of the region in tiles

    Returns:
        List of [x, y] positions
    """
    positions = []
    region_width, region_height = region_size[0], region_size[1]

    numbers = placement.get("numbers")
    if numbers:
        if not isinstance(numbers, list):
            numbers = [numbers]
        for block_num in numbers:
            coords = block_number_to_coords(block_num, region_width, region_height)
            if coords:
                positions.append(list(coords))

    numbers_fill = placement.get("numbers_fill")
    if numbers_fill and len(numbers_fill) == 2:
        coords1 = block_number_to_coords(numbers_fill[0], region_width, region_height)
        coords2 = block_number_to_coords(numbers_fill[1], region_width, region_height)
        if coords1 and coords2:
            x1, y1 = coords1
            x2, y2 = coords2
            min_x, max_x = min(x1, x2), max(x1, x2)
            min_y, max_y = min(y1, y2), max(y1, y2)
            for x in range(min_x, max_x + 1):
                for y in range(min_y, max_y + 1):
                    positions.append([x, y])

    if not positions:
        pos = placement.get("pos")
        if pos:
            if isinstance(pos[0], list):
                positions.extend(pos)
            else:
                positions.append(pos)

    if not positions:
        fill = placement.get("fill")
        if fill and len(fill) == 2 and len(fill[0]) == 2 and len(fill[1]) == 2:
            x1, y1 = fill[0]
            x2, y2 = fill[1]
            min_x, max_x = min(x1, x2), max(x1, x2)
            min_y, max_y = min(y1, y2), max(y1, y2)
            for x in range(min_x, max_x + 1):
                for y in range(min_y, max_y + 1):
                    positions.append([x, y])

    unique_positions = list(dict.fromkeys(tuple(position) for position in positions))
    return [list(position) for position in unique_positions]


def scale_rects(rects, tile_size):
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


def get_centered_rect(draw_pos, width, height, rect_width, rect_height):
    center_x = draw_pos.x + width / 2
    center_y = draw_pos.y + height / 2
    return pygame.Rect(
        int(center_x - rect_width / 2),
        int(center_y - rect_height / 2),
        int(rect_width),
        int(rect_height),
    )


def union_rects(rects):
    if not rects:
        return []
    union = rects[0].copy()
    for rect in rects[1:]:
        union.union_ip(rect)
    return [union]


def build_hitboxes(block_def, draw_pos, sprite_pos, block_size, tile_size, mask):
    solid_rects = scale_rects(block_def.get("solid_rects", []), tile_size)
    if not solid_rects:
        return [], []

    hitbox_type = block_def.get("hitbox_type", "pixel")
    ratio = max(0.0, min(1.0, float(block_def.get("hitbox_ratio", 1.0))))
    block_w, block_h = block_size

    if hitbox_type == "square":
        hitbox_size = max(1, int(tile_size * ratio))
        rect = get_centered_rect(draw_pos, block_w, block_h, hitbox_size, hitbox_size)
        return [{"rect": rect, "mask": None, "mask_pos": None, "type": "square"}], [rect]

    if hitbox_type == "rectangle":
        rect_w = max(1, int(block_w * ratio))
        rect_h = max(1, int(block_h * ratio))
        rect = get_centered_rect(draw_pos, block_w, block_h, rect_w, rect_h)
        return [{"rect": rect, "mask": None, "mask_pos": None, "type": "rectangle"}], [rect]

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
    hitboxes = [
        {"rect": rect, "mask": mask, "mask_pos": sprite_pos, "type": "pixel"}
        for rect in world_solids
    ]
    return hitboxes, union_rects(world_solids)


def get_block_sprite_layout(block_def, block_size, textures):
    texture_path = block_def.get("texture")
    texture_override = block_def.get("texture_size")
    stretch_to_fit = block_def.get("stretch_to_fit", True)
    if stretch_to_fit:
        return block_size, pygame.Vector2(0, 0)

    if texture_override:
        native_size = (int(texture_override[0]), int(texture_override[1]))
    else:
        native_size = textures.get_image_size(texture_path)
    if not native_size or native_size[0] <= 0 or native_size[1] <= 0:
        return block_size, pygame.Vector2(0, 0)

    scale = block_size[0] / native_size[0]
    sprite_w = block_size[0]
    sprite_h = max(1, int(native_size[1] * scale))
    offset_y = block_size[1] - sprite_h
    return (sprite_w, sprite_h), pygame.Vector2(0, offset_y)


def build_blocks(region, block_defs, textures):
    blocks = []
    tile_size = region["tile_size"]
    region_size = region.get("size", [50, 50])
    for placement in region.get("blocks", []):
        block_id = placement.get("id")
        if not block_id:
            continue
        block_def = block_defs.get(block_id)
        if not block_def:
            continue
        positions = get_block_positions(placement, region_size)
        for position in positions:
            anchor = pygame.Vector2(position[0] * tile_size, position[1] * tile_size)
            origin_tiles = pygame.Vector2(block_def.get("origin", [0, 0]))
            size_tiles = block_def.get("size", [1, 1])
            origin = origin_tiles * tile_size
            block_size = (int(size_tiles[0] * tile_size), int(size_tiles[1] * tile_size))
            sprite_size, sprite_offset = get_block_sprite_layout(block_def, block_size, textures)
            texture_path = block_def.get("texture")
            sprite = textures.get(texture_path, (int(sprite_size[0]), int(sprite_size[1])))
            mask = pygame.mask.from_surface(sprite)
            passable_rects = scale_rects(block_def.get("passable_rects", []), tile_size)

            draw_pos = anchor - origin
            sprite_pos = draw_pos + sprite_offset
            hitboxes, debug_hitboxes = build_hitboxes(
                block_def,
                draw_pos,
                sprite_pos,
                block_size,
                tile_size,
                mask,
            )
            blocks.append(
                {
                    "definition": block_def,
                    "draw_pos": draw_pos,
                    "block_size": max(block_size),
                    "sprite_size": sprite_size,
                    "sprite_offset": sprite_offset,
                    "mask": mask,
                    "hitboxes": hitboxes,
                    "debug_hitboxes": debug_hitboxes,
                    "passable_rects": passable_rects,
                }
            )
    return blocks


def build_background_blocks(region, block_defs, textures):
    background_blocks = []
    tile_size = region["tile_size"]
    region_size = region.get("size", [50, 50])
    for placement in region.get("background_blocks", []):
        block_id = placement.get("id")
        if not block_id:
            continue
        block_def = block_defs.get(block_id)
        if not block_def:
            continue
        positions = get_block_positions(placement, region_size)
        for position in positions:
            anchor = pygame.Vector2(position[0] * tile_size, position[1] * tile_size)
            origin_tiles = pygame.Vector2(block_def.get("origin", [0, 0]))
            size_tiles = block_def.get("size", [1, 1])
            origin = origin_tiles * tile_size
            block_size = (int(size_tiles[0] * tile_size), int(size_tiles[1] * tile_size))
            sprite_size, sprite_offset = get_block_sprite_layout(block_def, block_size, textures)
            texture_path = block_def.get("texture")
            sprite = textures.get(texture_path, (int(sprite_size[0]), int(sprite_size[1])))
            mask = pygame.mask.from_surface(sprite)
            passable_rects = scale_rects(block_def.get("passable_rects", []), tile_size)

            draw_pos = anchor - origin
            background_blocks.append(
                {
                    "definition": block_def,
                    "draw_pos": draw_pos,
                    "block_size": max(block_size),
                    "sprite_size": sprite_size,
                    "sprite_offset": sprite_offset,
                    "mask": mask,
                    "passable_rects": passable_rects,
                }
            )
    return background_blocks


def get_solids(blocks):
    solids = []
    for block in blocks:
        solids.extend(block.get("hitboxes", []))
    return solids

