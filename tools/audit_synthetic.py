"""Check generated files, endpoint labels, visible masks and layout split isolation."""

import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from labvision.core import require
from labvision.geometry import calibrate, calibration_quality


def audit(directory):
    from PIL import Image
    root = Path(directory).resolve()
    records = [json.loads(line) for line in (root/"manifest.jsonl").read_text().splitlines()]
    board = json.loads((root/"board.json").read_text())
    assignments, scene_ids = {}, set()
    counts = {"scenes": 0, "visible_endpoints": 0, "hidden_endpoints": 0}

    def file(relative):
        result = (root/relative).resolve()
        require(result.is_relative_to(root), "manifest path escapes dataset root")
        return result

    for record in records:
        require(record["scene_id"] not in scene_ids, "duplicate scene ID")
        scene_ids.add(record["scene_id"])
        assembly, split = record["assembly_id"], record["split"]
        require(split in ("train", "val", "test"), "invalid split")
        require(assembly not in assignments or assignments[assembly] == split, "layout leaks across splits")
        assignments[assembly] = split
        labels = json.loads(file(record["labels"]).read_text())
        require(labels["assembly_id"] == assembly and labels["split"] == split, "manifest/labels disagree")
        with Image.open(file(record["image"])) as image, Image.open(file(record["mask"])) as mask:
            require(image.size == mask.size == tuple(labels["image_size"]), "image/mask dimensions differ")
            calibration = calibrate(board, labels["calibration_anchors"], labels["calibration_checks"])
            require(calibration_quality(calibration, board)["validated"], "invalid generated calibration")
            holes = []
            for obj in labels["components"] + labels["wires"]:
                points = list(obj["pins"].values()) if "pins" in obj else [obj["a"], obj["b"]]
                if "a" in obj:
                    require(math.dist(obj["path_xy"][0], obj["a"]["xy"]) < 1e-6, "wire path start mismatch")
                    require(math.dist(obj["path_xy"][-1], obj["b"]["xy"]) < 1e-6, "wire path end mismatch")
                for p in points:
                    holes.append(p["hole"])
                    require(math.dist(labels["hole_centers"][p["hole"]], p["xy"]) < 1e-6,
                            "endpoint does not match transformed hole center")
                    x, y = map(round, p["xy"])
                    visible = 0 <= x < mask.width and 0 <= y < mask.height and mask.getpixel((x, y)) == obj["mask_id"]
                    require(visible == p["visible"], "visibility/mask mismatch")
                    require(p["observable_hole"] == (p["hole"] if visible else None), "hidden label leaked")
                    counts["visible_endpoints" if visible else "hidden_endpoints"] += 1
            require(len(holes) == len(set(holes)), "two physical endpoints share a hole")
        counts["scenes"] += 1
    counts["layouts"] = len(assignments)
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory")
    print(json.dumps(audit(parser.parse_args().directory), indent=2))
