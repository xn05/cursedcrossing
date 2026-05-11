import json
import os


def load_entity_defs(root_dir):
    entity_defs = {}
    for dirpath, _, filenames in os.walk(root_dir):
        for name in filenames:
            if not name.endswith(".json"):
                continue
            file_path = os.path.join(dirpath, name)
            with open(file_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            entity_id = data.get("id")
            if not entity_id:
                continue
            entity_defs[entity_id] = data
    return entity_defs
