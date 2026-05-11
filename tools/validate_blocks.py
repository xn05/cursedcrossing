import json
import os
import sys

from block_loader import load_block_defs


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    blocks_path = os.path.join(base_dir, "data", "blocks", "blocks.json")
    region_path = os.path.join(base_dir, "data", "region", "east_norton", "region.json")

    block_defs = load_block_defs(blocks_path, base_dir)
    if not block_defs:
        print("No blocks loaded from registry.")
        return 1

    with open(region_path, "r", encoding="utf-8") as handle:
        region = json.load(handle)

    placements = region.get("blocks", [])
    missing = []
    for placement in placements:
        block_id = placement.get("id")
        if block_id not in block_defs:
            missing.append(block_id)

    if missing:
        print("Missing block defs for:", ", ".join(missing))
        return 1

    print(f"Loaded {len(block_defs)} block(s) and validated {len(placements)} placement(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

