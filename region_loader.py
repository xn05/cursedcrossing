import json
import os


def load_regions(config_path):
	with open(config_path, "r", encoding="utf-8") as handle:
		data = json.load(handle)
	regions = {entry["id"]: entry["path"] for entry in data.get("regions", []) if entry.get("id")}
	default_id = data.get("default")
	return regions, default_id


def resolve_region_path(base_dir, regions, region_id):
	if region_id not in regions:
		raise ValueError(f"Unknown region id: {region_id}")
	path = regions[region_id]
	return os.path.join(base_dir, path)
