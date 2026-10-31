"""Planar board calibration and conservative endpoint snapping, without NumPy."""

import hashlib
import json
import math
import re

from .core import board_groups, require


def point(value):
    require(isinstance(value, (list, tuple)) and len(value) == 2
            and all(type(v) in (int, float) and math.isfinite(v) for v in value),
            "coordinates must contain two finite numbers")
    return list(map(float, value))


def hole_positions(board):
    holes = board_groups(board)
    explicit = board.get("hole_positions")
    if explicit is not None:
        require(isinstance(explicit, dict) and set(explicit) == set(holes),
                "hole_positions must locate every profile hole")
        positions = {h: point(xy) for h, xy in explicit.items()}
    else:
        positions = {}
        for hole in holes:
            match = re.fullmatch(r"([A-J])([1-9][0-9]*)", hole)
            require(match is not None, "nonstandard/rail holes need explicit hole_positions")
            col, row = match.groups()
            x = ord(col) - ord("A")
            positions[hole] = [float(x + (2 if x >= 5 else 0)), float(int(row) - 1)]
    require(len({tuple(xy) for xy in positions.values()}) == len(positions),
            "two holes cannot share the same board coordinate")
    return positions


def board_fingerprint(board):
    content = {"id": board["id"], "groups": board["groups"], "xy": hole_positions(board)}
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def project(matrix, xy):
    x, y = point(xy)
    d = matrix[2][0] * x + matrix[2][1] * y + matrix[2][2]
    require(abs(d) > 1e-10, "point lies on perspective horizon")
    return [(matrix[0][0] * x + matrix[0][1] * y + matrix[0][2]) / d,
            (matrix[1][0] * x + matrix[1][1] * y + matrix[1][2]) / d]


def multiply(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def inverse(m):
    # Gauss-Jordan also detects singular calibrations.
    rows = [list(m[i]) + [float(i == j) for j in range(3)] for i in range(3)]
    for col in range(3):
        pivot = max(range(col, 3), key=lambda i: abs(rows[i][col]))
        require(abs(rows[pivot][col]) > 1e-12, "singular calibration")
        rows[col], rows[pivot] = rows[pivot], rows[col]
        divisor = rows[col][col]
        rows[col] = [v / divisor for v in rows[col]]
        for i in range(3):
            if i != col:
                factor = rows[i][col]
                rows[i] = [v - factor * w for v, w in zip(rows[i], rows[col])]
    return [row[3:] for row in rows]


def _normalizer(points):
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    rms = math.sqrt(sum((p[0] - cx) ** 2 + (p[1] - cy) ** 2 for p in points) / len(points))
    require(rms > 1e-9, "calibration points must be spread over the board")
    scale = math.sqrt(2) / rms
    return [[scale, 0, -scale * cx], [0, scale, -scale * cy], [0, 0, 1]]


def fit_homography(source, destination):
    require(len(source) == len(destination) == 4, "exactly four calibration points required")
    src, dst = [point(p) for p in source], [point(p) for p in destination]
    a, b = _normalizer(src), _normalizer(dst)
    src, dst = [project(a, p) for p in src], [project(b, p) for p in dst]
    rows = []
    for (x, y), (u, v) in zip(src, dst):
        rows += [[x, y, 1, 0, 0, 0, -u*x, -u*y, u],
                 [0, 0, 0, x, y, 1, -v*x, -v*y, v]]
    for col in range(8):
        pivot = max(range(col, 8), key=lambda i: abs(rows[i][col]))
        require(abs(rows[pivot][col]) > 1e-9,
                "degenerate anchors: use four hole centers spanning both board dimensions")
        rows[col], rows[pivot] = rows[pivot], rows[col]
        divisor = rows[col][col]
        rows[col] = [v / divisor for v in rows[col]]
        for i in range(8):
            if i != col:
                factor = rows[i][col]
                rows[i] = [v - factor*w for v, w in zip(rows[i], rows[col])]
    h = [row[-1] for row in rows] + [1.0]
    normalized = [h[:3], h[3:6], h[6:]]
    return multiply(inverse(b), multiply(normalized, a))


def calibrate(board, anchors, checks=None):
    positions = hole_positions(board)
    require(isinstance(anchors, list) and len(anchors) == 4, "four anchors required")
    require(len({a["hole"] for a in anchors}) == 4, "anchor holes must be different")
    require(all(a["hole"] in positions for a in anchors), "anchor hole not in board profile")
    forward = fit_homography([positions[a["hole"]] for a in anchors], [a["xy"] for a in anchors])
    result = {"board_fingerprint": board_fingerprint(board), "anchors": anchors,
              "board_to_image": forward, "image_to_board": inverse(forward), "checks": checks or []}
    calibration_quality(result, board)  # Validate holdouts before storing.
    return result


def calibration_quality(calibration, board):
    require(calibration["board_fingerprint"] == board_fingerprint(board), "board geometry changed; recalibrate")
    positions = hole_positions(board)
    anchor_holes = {a["hole"] for a in calibration["anchors"]}
    seen, residuals = set(), []
    for check in calibration.get("checks", []):
        hole = check["hole"]
        require(hole in positions and hole not in anchor_holes and hole not in seen,
                "validation holes must be distinct and separate from anchors")
        seen.add(hole)
        estimated = project(calibration["image_to_board"], check["xy"])
        residuals.append(math.dist(estimated, positions[hole]))
    return {"validated": len(residuals) >= 2 and max(residuals) <= 0.25,
            "check_count": len(residuals), "max_error_pitch": max(residuals, default=None),
            "threshold_pitch": 0.25}


def snap(calibration, board, xy, radius=0.35, margin=0.2):
    calibration_quality(calibration, board)
    target = project(calibration["image_to_board"], xy)
    ranked = sorted((math.dist(target, pos), hole) for hole, pos in hole_positions(board).items())
    require(len(ranked) >= 2, "snapping requires at least two board holes")
    first, second = ranked[0], ranked[1]
    confident = first[0] <= radius and second[0] - first[0] >= margin
    choices = [hole for distance, hole in ranked[:2] if distance <= 0.8] if not confident else []
    return {"hole": first[1] if confident else None, "alternatives": choices,
            "confidence": "likely" if confident else "uncertain",
            "reason": "Manual pixel annotation snapped to calibrated grid" if confident
                      else "Point is outside the snap radius or ambiguous between holes",
            "source": "manual", "confirmed": False, "image_xy": point(xy),
            "visible": True, "snap_distance_pitch": first[0]}
