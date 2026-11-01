"""Experimental wire-end REGION proposals, not insertion-hole ground truth."""
import math


def region_box(point, width, height, radius=None):
    x, y = point
    if not all(math.isfinite(float(v)) for v in (x, y, width, height)):
        raise ValueError('Non-finite image coordinates')
    if not (0 <= x < width and 0 <= y < height):
        raise ValueError('Point outside image')
    radius = radius or max(8, max(width, height) * 0.012)
    return [max(0., x-radius), max(0., y-radius),
            min(float(width), x+radius), min(float(height), y+radius)]


def yolo_region(box, width, height):
    l, t, r, b = box
    if not (0 <= l < r <= width and 0 <= t < b <= height):
        raise ValueError('Invalid region')
    return '0 ' + ' '.join(f'{v:.7f}' for v in
                           ((l+r)/2/width, (t+b)/2/height,
                            (r-l)/width, (b-t)/height))


def propose_regions(image):
    """Local red-insulation skeleton tips. Loose ends are included intentionally.

    These approximate regions may miss metal contacts and contain rail/text
    artifacts. No output is a verified endpoint or exact point/hole label.
    """
    import cv2
    import numpy as np
    from .localvision import thin, _neighbors
    rgb = np.asarray(image.convert('RGB'))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    red = rgb[:, :, 0].astype(float)
    green = rgb[:, :, 1].astype(float)
    blue = rgb[:, :, 2].astype(float)
    mask = (((hsv[:, :, 0] <= 8) | (hsv[:, :, 0] >= 175))
            & (hsv[:, :, 1] >= 95) & (hsv[:, :, 2] >= 70)
            & (red-green >= 40) & (red-blue >= 30))
    white = ((hsv[:, :, 1] < 85) & (hsv[:, :, 2] > 100)).astype('uint8')
    white = cv2.morphologyEx(white, cv2.MORPH_CLOSE, np.ones((15, 15), 'uint8'))
    contours, _ = cv2.findContours(white, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return []
    board = max(contours, key=cv2.contourArea)
    if cv2.contourArea(board) < image.width * image.height * 0.05:
        return []
    board_mask = np.zeros(mask.shape, dtype='uint8')
    cv2.fillConvexPoly(board_mask, cv2.convexHull(board), 1)
    # Reject thin printed rail lines before skeletonization. This can also remove
    # thin real wires: omissions are a documented pseudo-label limitation.
    opened = cv2.morphologyEx(mask.astype('uint8'), cv2.MORPH_OPEN,
                             cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    n, ids, stats, _ = cv2.connectedComponentsWithStats(opened, 8)
    cleaned = np.zeros(mask.shape, dtype=bool)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= 30 and np.count_nonzero((ids == i) & (board_mask > 0)) >= 5:
            cleaned |= ids == i
    skeleton = thin(cleaned)
    degree = np.sum(_neighbors(skeleton), axis=0, dtype=np.uint8)
    tips = list(zip(*np.where(skeleton & (degree == 1))))
    occupied = set(zip(*np.where(skeleton)))
    offsets = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
    regions = []
    for tip in tips:
        path, previous, current = [tip], None, tip
        for _ in range(12):
            choices = [(current[0]+dy, current[1]+dx) for dy, dx in offsets
                       if (current[0]+dy, current[1]+dx) in occupied
                       and (current[0]+dy, current[1]+dx) != previous]
            if len(choices) != 1:
                break
            previous, current = current, choices[0]
            path.append(current)
        if len(path) < 7:
            continue
        xy = [float(tip[1]), float(tip[0])]
        if any(math.dist(xy, p['xy']) < 7 for p in regions):
            continue
        regions.append({'id': f'P{len(regions)+1}', 'xy': xy,
                        'box': region_box(xy, image.width, image.height),
                        'source': 'red-mask-board-skeleton-v3', 'reviewed': False,
                        'kind': 'unknown', 'hole': None, 'confirmed': False})
    return regions


def audit_groups(records):
    """Reject exact-image and known-layout leakage, not just different filenames."""
    seen_hashes, seen_groups = {}, {}
    for record in records:
        split = record['split']
        if split not in {'train', 'val', 'test'}:
            raise ValueError('Unassigned/invalid split')
        for seen, key in ((seen_hashes, record['sha256']),
                          (seen_groups, record['assembly_id'])):
            if key in seen and seen[key] != split:
                raise ValueError('Image or assembly leaks across splits')
            seen[key] = split

