"""Procedural, explicitly stylized breadboard data with exact scene labels.

No generated image is claimed to be a real photograph or a validated experiment.
"""

from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import random

from .core import board_groups, make_board, require
from .geometry import fit_homography, hole_positions, inverse, multiply, project


def layout(seed, rows=30):
    rng = random.Random(seed)
    board = make_board(rows)
    positions = hole_positions(board)
    start = rng.randint(3, rows - 8)
    pins = {str(i): f"E{start + i - 1}" for i in range(1, 8)}
    pins.update({str(i): f"F{start + 14 - i}" for i in range(8, 15)})
    available = sorted(set(positions) - set(pins.values()))
    rng.shuffle(available)
    wires = []
    for i in range(rng.randint(2, 8)):
        a, b = available.pop(), available.pop()
        wires.append({"id": f"W{i+1}", "a": a, "b": b})
    return board, pins, wires


def connectivity(board, pins, wires):
    groups = board_groups(board)
    parent = {g: g for g in groups.values()}

    def root(g):
        while parent[g] != g:
            parent[g] = parent[parent[g]]
            g = parent[g]
        return g

    for wire in wires:
        a, b = root(groups[wire["a"]]), root(groups[wire["b"]])
        parent[max(a, b)] = min(a, b)
    terminals = {f"U1.{pin}": hole for pin, hole in pins.items()}
    terminals.update({f"{w['id']}.{side}": w[side] for w in wires for side in ("a", "b")})
    connected = defaultdict(list)
    for terminal, hole in terminals.items():
        connected[root(groups[hole])].append(terminal)
    return [sorted(terminals) for _, terminals in sorted(connected.items())]


def render(seed, layout_seed, rows=30, width=512, height=768, occlusions=True):
    try:
        from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
    except ImportError as exc:
        raise ValueError("Install requirements-vision.txt for synthetic rendering") from exc
    require(type(rows) is int and 12 <= rows <= 63, "synthetic rows must be 12..63")
    board, pins, wires = layout(layout_seed, rows)
    rng = random.Random(seed)
    positions = hole_positions(board)
    pitch = min((height - 140)/(rows - 1), (width - 160)/11)
    ox, oy = (width - 11*pitch)/2, (height - (rows-1)*pitch)/2
    base = [[pitch, 0, ox], [0, pitch, oy], [0, 0, 1]]
    background = tuple(rng.randint(125, 190) for _ in range(3))
    image = Image.new("RGB", (width, height), background)
    mask = Image.new("I", (width, height), 0)
    draw, ids = ImageDraw.Draw(image), ImageDraw.Draw(mask)
    board_box = (ox-30, oy-28, ox+11*pitch+30, oy+(rows-1)*pitch+28)
    draw.rounded_rectangle(board_box, radius=10, fill=(228, 226, 215), outline=(155, 155, 145), width=2)
    gap_x = ox+5.5*pitch
    draw.line([(gap_x, oy-20), (gap_x, oy+(rows-1)*pitch+20)], fill=(130, 130, 125), width=5)
    for hole, pos in positions.items():
        x, y = project(base, pos)
        draw.rectangle((x-2, y-2, x+2, y+2), fill=(40, 45, 43))
    for row in range(1, rows+1, 5):
        draw.text((ox-22, oy+(row-1)*pitch-5), str(row), fill=(65, 65, 65))
    for col in "ABCDEFGHIJ":
        draw.text((project(base, positions[f"{col}1"])[0]-3, oy-20), col, fill=(65, 65, 65))
    top = positions[pins["1"]][1] - 0.4
    bottom = positions[pins["7"]][1] + 0.4
    chip_corners = [[4.35, top], [6.65, top], [6.65, bottom], [4.35, bottom]]
    polygon = [tuple(project(base, p)) for p in chip_corners]
    draw.polygon(polygon, fill=(35, 38, 38))
    ids.polygon(polygon, fill=1)
    draw.text((gap_x-13, oy+(top+1.5)*pitch), "7400", fill=(195, 195, 190))
    draw.ellipse((gap_x-5, oy+top*pitch-5, gap_x+5, oy+top*pitch+5), fill=(105, 105, 95))
    for pin, hole in pins.items():
        x, y = project(base, positions[hole])
        inner = ox + (4.4 if hole.startswith("E") else 6.6)*pitch
        draw.line([(x, y), (inner, y)], fill=(165, 165, 155), width=4)
        ids.line([(x, y), (inner, y)], fill=1, width=4)
    paths = {}
    palette = [(170, 25, 28), (22, 27, 30), (25, 65, 180), (20, 125, 60), (220, 180, 25)]
    same_color = rng.random() < 0.35
    for index, wire in enumerate(wires, 2):
        a, b = [project(base, positions[wire[s]]) for s in ("a", "b")]
        dx, dy = b[0]-a[0], b[1]-a[1]
        length = max(math.hypot(dx, dy), 1)
        bend = rng.uniform(-75, 75)
        control = [(a[0]+b[0])/2 - dy/length*bend, (a[1]+b[1])/2 + dx/length*bend]
        path = [[(1-t)**2*a[0]+2*(1-t)*t*control[0]+t*t*b[0],
                 (1-t)**2*a[1]+2*(1-t)*t*control[1]+t*t*b[1]] for t in [i/40 for i in range(41)]]
        paths[wire["id"]] = path
        color = palette[0] if same_color else rng.choice(palette)
        thickness = rng.randint(4, 7)
        draw.line([tuple(p) for p in path], fill=color, width=thickness)
        ids.line([tuple(p) for p in path], fill=index, width=thickness)
    # Every insertion point is drawn at its true hole; late rectangles can occlude it.
    for index, wire in enumerate(wires, 2):
        for side in ("a", "b"):
            x, y = project(base, positions[wire[side]])
            box = (x-2, y-2, x+2, y+2)
            draw.ellipse(box, fill=(180, 160, 125))
            ids.ellipse(box, fill=index)
    if occlusions and rng.random() < 0.4:
        selected = rng.choice(wires)
        x, y = project(base, positions[selected[rng.choice(("a", "b"))]])
        box = (x-10, y-14, x+16, y+10)
        draw.rectangle(box, fill=(105, 100, 92))
        ids.rectangle(box, fill=65535)
    corners = [[0, 0], [width-1, 0], [width-1, height-1], [0, height-1]]
    jittered = [[x+rng.uniform(-18, 18), y+rng.uniform(-18, 18)] for x, y in corners]
    warp = fit_homography(corners, jittered)
    mapping = multiply(warp, base)
    inv = inverse(warp)
    coeff = [v/inv[2][2] for row in inv for v in row][:8]
    image = image.transform((width, height), Image.Transform.PERSPECTIVE, coeff,
                            Image.Resampling.BICUBIC, fillcolor=background)
    mask = mask.transform((width, height), Image.Transform.PERSPECTIVE, coeff,
                          Image.Resampling.NEAREST, fillcolor=0)
    image = ImageEnhance.Brightness(image).enhance(rng.uniform(0.8, 1.15))
    image = image.filter(ImageFilter.GaussianBlur(rng.uniform(0, 0.65)))

    def label(hole, object_id):
        xy = project(mapping, positions[hole])
        x, y = map(round, xy)
        visible = 0 <= x < width and 0 <= y < height and mask.getpixel((x, y)) == object_id
        return {"xy": xy, "hole": hole, "visible": bool(visible),
                "observable_hole": hole if visible else None}

    anchor_holes = ["A1", "J1", f"J{rows}", f"A{rows}"]
    checks = [f"A{rows//2}", f"J{rows//2}"]
    labels = {
        "label_version": "0.1", "image_type": "synthetic_2d", "image_size": [width, height],
        "board_profile_id": board["id"], "board_to_image": mapping,
        "hole_centers": {hole: project(mapping, xy) for hole, xy in positions.items()},
        "calibration_anchors": [{"hole": h, "xy": project(mapping, positions[h])} for h in anchor_holes],
        "calibration_checks": [{"hole": h, "xy": project(mapping, positions[h])} for h in checks],
        "components": [{"id": "U1", "part": "7400", "mask_id": 1,
                        "body_corners": [project(mapping, p) for p in chip_corners],
                        "pins": {pin: label(hole, 1) for pin, hole in pins.items()}}],
        "wires": [{"id": wire["id"], "mask_id": i,
                   "a": label(wire["a"], i), "b": label(wire["b"], i),
                   "path_xy": [project(warp, p) for p in paths[wire["id"]]]}
                  for i, wire in enumerate(wires, 2)],
        "electrical_groups": connectivity(board, pins, wires),
        "mask_semantics": "Topmost visible instance ID; 0=background/board, 1=U1, 2+=wires, 65535=occluder",
        "limitations": ["Stylized 2D rendering, not a real photograph or validated functional circuit.",
                        "hole/xy are latent scene truth; train observable endpoints only when visible=true.",
                        "Raised cable parallax, realistic specular metal and complex lighting are not modeled."],
    }
    return image, mask, labels, board


def generate(directory, count=200, seed=42, variants=2):
    require(type(count) is int and 1 <= count <= 5000, "count must be 1..5000")
    require(type(variants) is int and 1 <= variants <= 20, "variants must be 1..20")
    target = Path(directory)
    require(not target.exists() or not any(target.iterdir()), "dataset output must be a new/empty directory")
    for child in ("images", "labels", "masks"):
        (target/child).mkdir(parents=True, exist_ok=True)
    manifest = []
    for index in range(count):
        layout_index = index//variants
        assembly = f"synthetic-{seed}-layout-{layout_index:05d}"
        bucket = int(hashlib.sha256(assembly.encode()).hexdigest()[:8], 16) % 100
        split = "train" if bucket < 70 else "val" if bucket < 85 else "test"
        image, mask, labels, board = render(f"{seed}:{index}", f"{seed}:layout:{layout_index}")
        stem = f"scene-{index:05d}"
        labels.update(scene_id=stem, assembly_id=assembly, split=split, render_seed=f"{seed}:{index}")
        image.save(target/"images"/(stem+".png"))
        mask.convert("I;16").save(target/"masks"/(stem+".png"))
        (target/"labels"/(stem+".json")).write_text(json.dumps(labels, indent=2) + "\n", encoding="utf-8")
        manifest.append({"scene_id": stem, "assembly_id": assembly, "split": split,
                         "image_type": "synthetic_2d", "image": f"images/{stem}.png",
                         "labels": f"labels/{stem}.json", "mask": f"masks/{stem}.png"})
    (target/"board.json").write_text(json.dumps(board, indent=2) + "\n", encoding="utf-8")
    (target/"manifest.jsonl").write_text("".join(json.dumps(row)+"\n" for row in manifest), encoding="utf-8")
    summary = {"count": count, "seed": seed, "variants_per_layout": variants,
               "layouts": len({row["assembly_id"] for row in manifest}),
               "split_counts": {s: sum(row["split"] == s for row in manifest) for s in ("train", "val", "test")},
               "status": "synthetic fixtures generated; no detector trained or real-photo accuracy established"}
    (target/"summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary
