import json

import pygame

from lib.blocks import get_solids


def load_movement(path):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    speed = float(data.get("speed", 60))
    bindings = {}
    for direction, keys in data.get("bindings", {}).items():
        key_codes = []
        for key in keys:
            try:
                key_codes.append(pygame.key.key_code(key))
            except ValueError:
                continue
        bindings[direction] = set(key_codes)
    return {"speed": speed, "bindings": bindings}


def clamp_player_to_region(region, pos):
    width, height = region["size"]
    tile_size = region["tile_size"]
    max_x = width * tile_size - tile_size
    max_y = height * tile_size - tile_size
    pos.x = max(0, min(pos.x, max_x))
    pos.y = max(0, min(pos.y, max_y))
    return pos


def get_player_rect(region, pos):
    tile_size = region["tile_size"]
    player_size = int(tile_size * 0.8)
    return pygame.Rect(int(pos.x), int(pos.y), player_size, player_size)


def resolve_collisions(region, pos, move, blocks, player_mask):
    solids = get_solids(blocks)
    if not solids:
        return pos + move

    new_pos = pygame.Vector2(pos)

    new_pos.x += move.x
    player_rect = get_player_rect(region, new_pos)
    collision_x = False
    for solid_rect, solid_mask, solid_pos in solids:
        if player_rect.colliderect(solid_rect):
            if player_mask and solid_mask:
                offset = (int(solid_pos.x - new_pos.x), int(solid_pos.y - new_pos.y))
                if player_mask.overlap(solid_mask, offset):
                    collision_x = True
                    break
    if collision_x:
        new_pos.x = pos.x

    new_pos.y += move.y
    player_rect = get_player_rect(region, new_pos)
    collision_y = False
    for solid_rect, solid_mask, solid_pos in solids:
        if player_rect.colliderect(solid_rect):
            if player_mask and solid_mask:
                offset = (int(solid_pos.x - new_pos.x), int(solid_pos.y - new_pos.y))
                if player_mask.overlap(solid_mask, offset):
                    collision_y = True
                    break
    if collision_y:
        new_pos.y = pos.y

    return new_pos


def update_player(
    dt,
    movement,
    region,
    player_pos,
    player_dir,
    player_anim_time,
    player_is_moving,
    player_mask,
    blocks,
):
    speed = movement["speed"]
    bindings = movement["bindings"]
    keys = pygame.key.get_pressed()

    dx = 0
    dy = 0
    if any(keys[key] for key in bindings.get("left", [])):
        dx -= 1
    if any(keys[key] for key in bindings.get("right", [])):
        dx += 1
    if any(keys[key] for key in bindings.get("up", [])):
        dy -= 1
    if any(keys[key] for key in bindings.get("down", [])):
        dy += 1

    move = pygame.Vector2(dx, dy)
    player_was_moving = player_is_moving
    player_is_moving = move.length_squared() > 0
    if player_is_moving:
        move = move.normalize() * speed * dt
        player_pos = resolve_collisions(region, player_pos, move, blocks, player_mask)
        if move.x != 0:
            player_dir = "right" if move.x > 0 else "left"
        else:
            player_dir = "down" if move.y > 0 else "up"
    if player_is_moving != player_was_moving:
        player_anim_time = 0.0
    player_anim_time += dt

    player_pos = clamp_player_to_region(region, player_pos)
    return player_pos, player_dir, player_anim_time, player_is_moving, player_was_moving

