"""Experimental red-wire tip proposals. No trained weights or wire pairing."""

import math
import re

from .core import CandidateError, require
from .geometry import calibration_quality, hole_positions, project


def _neighbors(mask):
    import numpy as np
    p = np.pad(mask, 1)
    return [p[:-2, 1:-1], p[:-2, 2:], p[1:-1, 2:], p[2:, 2:],
            p[2:, 1:-1], p[2:, :-2], p[1:-1, :-2], p[:-2, :-2]]


def thin(mask, max_iterations=100):
    """Zhang-Suen thinning with zero padding, preserving separate image edges."""
    import numpy as np
    mask = np.asarray(mask, dtype=bool).copy()
    for _ in range(max_iterations):
        changed = False
        for step in (0, 1):
            neighbors = _neighbors(mask)
            count = np.sum(neighbors, axis=0, dtype=np.uint8)
            transitions = np.sum([~neighbors[i] & neighbors[(i+1) % 8]
                                  for i in range(8)], axis=0, dtype=np.uint8)
            n, _, e, _, s, _, w, _ = neighbors
            if step == 0:
                condition = ~(n & e & s) & ~(e & s & w)
            else:
                condition = ~(n & e & w) & ~(n & s & w)
            remove = mask & (count >= 2) & (count <= 6) & (transitions == 1) & condition
            if remove.any():
                mask[remove] = False
                changed = True
        if not changed:
            break
    return mask


def propose_red_wire_tips(image, board, calibration, crop=None, min_branch=10):
    try:
        import numpy as np
        from PIL import Image, ImageFilter
    except ImportError as exc:
        raise CandidateError("Install requirements-local-vision.txt") from exc
    require(calibration_quality(calibration, board)["validated"], "validated calibration required")
    require(type(min_branch) is int and min_branch >= 3, "min_branch must be at least 3")
    box = list(crop or [0, 0, image.width, image.height])
    l, t, r, b = box
    require(0 <= l < r <= image.width and 0 <= t < b <= image.height, "invalid crop")
    photo = image.convert("RGB").crop(box)
    data = np.asarray(photo, dtype=np.int16)
    red, green, blue = (data[:, :, i] for i in range(3))
    mask = ((red >= 65) & (red-green >= 50) & (red-blue >= 50)
            & (red >= 1.9*green) & (red >= 1.9*blue))
    # Close one-pixel segmentation gaps. Glare/crossings can still break topology.
    mask_image = Image.fromarray((mask*255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    skeleton = thin(np.asarray(mask_image) > 0)
    degree = np.sum(_neighbors(skeleton), axis=0, dtype=np.uint8)
    tips = list(zip(*np.where(skeleton & (degree == 1))))
    occupied = set(zip(*np.where(skeleton)))
    offsets = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
    # Sparse user-marked rail contacts reveal where occupied holes are. Exclude
    # them to avoid feeding that annotation information into this baseline.
    positions = {h: xy for h, xy in hole_positions(board).items() if re.fullmatch(r"[A-J][1-9][0-9]*", h)}
    proposals = []
    for tip in tips:
        path, previous, current = [tip], None, tip
        for _ in range(16):
            choices = [(current[0]+dy, current[1]+dx) for dy, dx in offsets
                       if (current[0]+dy, current[1]+dx) in occupied and (current[0]+dy, current[1]+dx) != previous]
            if len(choices) != 1:
                break
            previous, current = current, choices[0]
            path.append(current)
        if len(path) < min_branch:
            continue
        tip_xy = [float(tip[1]+l), float(tip[0]+t)]
        back_xy = [float(path[-1][1]+l), float(path[-1][0]+t)]
        tip_board = project(calibration["image_to_board"], tip_xy)
        back_board = project(calibration["image_to_board"], back_xy)
        direction = [a-b for a, b in zip(tip_board, back_board)]
        length = math.hypot(*direction)
        if length < 0.2:
            continue
        direction = [v/length for v in direction]
        ranked = []
        for hole, xy in positions.items():
            delta = [a-b for a, b in zip(xy, tip_board)]
            along = sum(a*b for a, b in zip(delta, direction))
            across = abs(delta[0]*direction[1]-delta[1]*direction[0])
            if -0.2 <= along <= 1.8 and across <= 0.35:
                ranked.append((across + 0.2*max(0, along), hole))
        ranked.sort()
        if not ranked:
            continue
        unique = len(ranked) == 1 or ranked[1][0]-ranked[0][0] >= 0.08
        hole = ranked[0][1] if unique else None
        proposals.append({"id": "P" + str(len(proposals)+1), "hole": hole,
                          "alternatives": [] if unique else [h for _, h in ranked[:2]],
                          "tip_xy": tip_xy,
                          "insertion_xy": project(calibration["board_to_image"], positions[hole]) if hole else None,
                          "confidence": "uncertain", "source": "vision", "confirmed": False,
                          "reason": "Color-mask tip extrapolated toward a central-grid hole; pairing and insertion need review"})
    return {"method": "red-mask-skeleton-tip-v1", "crop": box, "proposals": proposals,
            "mask": mask_image, "skeleton": Image.fromarray((skeleton*255).astype(np.uint8)),
            "limitations": ["Red wires only; no trained model or component detection.",
                            "No wire pairing; glare, crossings, metal leads and shadows can cause errors.",
                            "Central A-J holes only; sparse annotated rail positions excluded.",
                            "Thresholds inspected on this photo: development check, not held-out accuracy."]}
