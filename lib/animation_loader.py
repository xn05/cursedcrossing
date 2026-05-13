import os

from PIL import Image

from lib.image_frame import ImageFrame


def load_animation(entity_defs, anim_id, textures_root):
    anim_def = entity_defs.get(anim_id)
    if not anim_def:
        return None

    texture = anim_def.get("texture")
    layers = anim_def.get("layers") or ([texture] if texture else [])
    if not layers:
        return None

    grid = anim_def.get("grid", {})
    columns = int(grid.get("columns", 0))
    rows = int(grid.get("rows", 0))
    fps = anim_def.get("fps", 6)
    index_base = int(anim_def.get("index_base", 0))
    sequences = anim_def.get("sequences", {})

    sheets = [load_sheet(textures_root, layer) for layer in layers]
    sheet_w, sheet_h = sheets[0].size
    if columns <= 0:
        columns = max(1, sheet_w // 32)
    if rows <= 0:
        rows = max(1, sheet_h // 32)
    frame_w = sheet_w // columns
    frame_h = sheet_h // rows

    def make_frame(index):
        col = index % columns
        row = index // columns
        frame = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 0))
        src = (col * frame_w, row * frame_h, (col + 1) * frame_w, (row + 1) * frame_h)
        for sheet in sheets:
            frame.alpha_composite(sheet.crop(src), (0, 0))
        return ImageFrame(frame)

    frames = [make_frame(i) for i in range(columns * rows)]

    if sequences:
        frames_by_sequence = {}
        for name, indices in sequences.items():
            remapped = []
            for raw_index in indices:
                index = int(raw_index) - index_base
                if 0 <= index < len(frames):
                    remapped.append(frames[index])
            if remapped:
                frames_by_sequence[name] = remapped
    else:
        frames_by_sequence = {"default": frames}

    if not frames_by_sequence:
        return None

    return {
        "fps": fps,
        "frame_size": (frame_w, frame_h),
        "sequences": frames_by_sequence,
    }


def load_sheet(textures_root, texture_path):
    full_path = os.path.join(textures_root, texture_path)
    return Image.open(full_path).convert("RGBA")
