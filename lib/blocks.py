import pygame


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
    for placement in region.get("blocks", []):
        block_id = placement.get("id")
        if not block_id:
            continue
        block_def = block_defs.get(block_id)
        if not block_def:
            continue
        pos = placement.get("pos", [0, 0])
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
            sprite_size, sprite_offset = get_block_sprite_layout(block_def, block_size, textures)
            texture_path = block_def.get("texture")
            sprite = textures.get(texture_path, (int(sprite_size[0]), int(sprite_size[1])))
            mask = pygame.mask.from_surface(sprite)
            hitbox = mask.get_rect()
            block_size = max(hitbox.width, hitbox.height)
            solid_rects = scale_rects(block_def.get("solid_rects", []), tile_size)
            passable_rects = scale_rects(block_def.get("passable_rects", []), tile_size)

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


def build_background_blocks(region, block_defs, textures):
    background_blocks = []
    tile_size = region["tile_size"]
    for placement in region.get("background_blocks", []):
        block_id = placement.get("id")
        if not block_id:
            continue
        block_def = block_defs.get(block_id)
        if not block_def:
            continue
        positions = []
        pos = placement.get("pos")
        if pos:
            if isinstance(pos[0], list):
                positions.extend(pos)
            else:
                positions.append(pos)
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
        positions = list(set(tuple(p) for p in positions))
        positions = [list(p) for p in positions]
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
            hitbox = mask.get_rect()
            block_size = max(hitbox.width, hitbox.height)
            passable_rects = scale_rects(block_def.get("passable_rects", []), tile_size)

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


def get_solids(blocks):
    solids = []
    for block in blocks:
        mask = block.get("mask")
        pos = block["draw_pos"]
        for rect in block.get("solid_rects", []):
            solids.append((rect, mask, pos))
    return solids

