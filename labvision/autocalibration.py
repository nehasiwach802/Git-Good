"""Experimental, image-bound central-grid alignment; never grants circuit review.

Near-overhead, portrait captures of a complete two-by-five-column breadboard.
Printed labels are not read: returned coordinates use provisional A-J/top-down
row numbering until a person verifies the board layout and orientation.
"""
import hashlib
import io

from .core import require
from .geometry import board_fingerprint, hole_positions


def detect_grid(image_bytes, board):
    """Return a geometric proposal or an explicit failure, without mutating board.

    Requires optional requirements-video dependencies. Input and output coordinates
    are decoded native-file pixels, with no EXIF transform. No cloud/model calls.
    """
    import cv2
    import numpy as np
    from PIL import Image

    require(isinstance(image_bytes, bytes) and 0 < len(image_bytes) <= 5*1024*1024,
            'Calibration image must be bytes, at most 5 MiB')
    positions = hole_positions(board)
    rows = max(int(h[1:]) for h in positions if h[0] in 'ABCDEFGHIJ' and h[1:].isdigit())
    expected = {f'{c}{r}' for c in 'ABCDEFGHIJ' for r in range(1, rows+1)}
    require(set(positions) == expected and 10 <= rows <= 70,
            'Automatic calibration requires a complete central A-J grid of 10-70 rows, without rails')
    require(all(positions[f'{c}{r}'] == [float(i+(2 if i >= 5 else 0)), float(r-1)]
                for i,c in enumerate('ABCDEFGHIJ') for r in range(1,rows+1)),
            'Automatic calibration requires standard central-grid geometry')
    with Image.open(io.BytesIO(image_bytes)) as im:
        require(im.format in ('JPEG','PNG') and im.width*im.height <= 8_500_000,
                'Calibration requires a bounded JPEG or PNG')
        size = list(im.size)
        rgb = np.asarray(im.convert('RGB'))
    result = {'schema_version':'ml1-grid-proposal-1', 'status':'not_found',
              'image_sha256':hashlib.sha256(image_bytes).hexdigest(), 'image_size':size,
              'board_fingerprint':board_fingerprint(board), 'labels_confirmed':False,
              'reviewed':False, 'calibration':None, 'holes':{},
              'reason':'No sufficiently supported complete central grid found'}
    scale = min(1., 1600/max(size))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    if scale < 1:
        gray = cv2.resize(gray,None,fx=scale,fy=scale)
    # Dark compact openings. Long wire/edge regions are excluded by shape.
    binary = cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV,31,9)
    contours,_ = cv2.findContours(binary,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
    points = []
    for contour in contours:
        x,y,w,h = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        if 2 <= w <= 24 and 2 <= h <= 24 and .4 <= w/h <= 2.5 and 2 <= area <= 350 and area/(w*h) >= .22:
            m = cv2.moments(contour)
            if m['m00']:
                points.append([m['m10']/m['m00'],m['m01']/m['m00']])
    result['blob_count'] = len(points)
    if len(points) < rows*4 or len(points) > 5000:
        return result
    pts = np.asarray(points, dtype=np.float64)
    # Estimate pitch from nearest neighbours; tolerate stray lettering blobs.
    nearest = []
    for offset in range(0,len(pts),128):
        delta = pts[offset:offset+128,None,:]-pts[None,:,:]
        dist = np.sqrt(np.sum(delta*delta,axis=2))
        dist[dist < 2] = np.inf
        nearest.extend(np.min(dist,axis=1))
    pitch = float(np.median(nearest))
    if not 4 <= pitch <= 50:
        return result
    rng = np.random.default_rng(17)
    remaining = np.arange(len(pts))
    lines = []
    middle = float(np.median(pts[:,1]))
    for _ in range(18):
        p = pts[remaining]
        if len(p) < rows*.35:
            break
        pairs = rng.integers(0,len(p),(1600,2))
        a,b = p[pairs[:,0]],p[pairs[:,1]]
        dy = b[:,1]-a[:,1]
        valid = (np.abs(dy) > rows*pitch*.35) & (np.abs(b[:,0]-a[:,0]) < np.abs(dy)*.5)
        if not valid.any():
            break
        slopes = (b[valid,0]-a[valid,0])/dy[valid]
        intercepts = a[valid,0]-slopes*a[valid,1]
        residual = np.abs(p[:,0,None]-p[:,1,None]*slopes-intercepts)
        counts = np.sum(residual < pitch*.19,axis=0)
        best = int(np.argmax(counts))
        ids = remaining[residual[:,best] < pitch*.19]
        if len(ids) < max(8,rows*.38):
            break
        slope,intercept = np.polyfit(pts[ids,1],pts[ids,0],1)
        lines.append((float(slope*middle+intercept),ids))
        remaining = remaining[residual[:,best] >= pitch*.27]
    lines.sort(key=lambda item:item[0])
    result['column_candidates'] = len(lines)
    if len(lines) < 10:
        return result
    # Both five-column terminal strips, with the wider center channel, distinguish
    # them from the two-column power rails. Missing columns cause rejection.
    pattern = np.array([0,1,2,3,4,7,8,9,10,11],dtype=float)
    choices = []
    for left in range(len(lines)-9):
        for right in range(left+5,len(lines)-4):
            selected = lines[left:left+5]+lines[right:right+5]
            xs = np.array([line[0] for line in selected])
            step,origin = np.polyfit(pattern,xs,1)
            error = float(np.max(np.abs(xs-(origin+step*pattern)))/step)
            if step > 3 and error < .28:
                choices.append((error,selected))
    if not choices:
        return result
    _, selected = min(choices,key=lambda item:item[0])
    # A printed character may lie on a column extension. Require both end rows
    # to have support across many columns instead of using each column's extremes.
    observations = sorted((pts[idx,1],col) for col,(_,ids) in enumerate(selected) for idx in ids)
    bands = []
    for y,col in observations:
        if not bands or y-np.median([v for v,_ in bands[-1]]) > pitch*.42:
            bands.append([])
        bands[-1].append((y,col))
    levels = [float(np.median([y for y,_ in band])) for band in bands
              if len({col for _,col in band}) >= 6]
    if len(levels) < rows*.6:
        return result
    top,bottom = levels[0],levels[-1]
    typical = float(np.median(np.diff(levels)))
    if abs((bottom-top)/typical-(rows-1)) > 1.1:
        result['reason'] = 'Full row extent does not match configured board; use another frame/profile'
        return result
    source,destination = [],[]
    for col,(_,ids) in enumerate(selected):
        p = pts[ids]
        p = p[(p[:,1] >= top-pitch*.4)&(p[:,1] <= bottom+pitch*.4)]
        p = p[np.argsort(p[:,1])]
        gaps = np.diff(p[:,1])
        gaps = gaps[(gaps > pitch*.5)&(gaps < pitch*1.6)]
        if len(gaps) < rows*.25:
            return result
        step = float(np.median(gaps))
        row_index = np.rint((p[:,1]-top)/(bottom-top)*(rows-1)).astype(int)
        for row,xy in zip(row_index,p):
            source.append([pattern[col],row])
            destination.append(xy)
    src,dst = np.asarray(source,dtype=np.float64),np.asarray(destination,dtype=np.float64)
    # Reserve spatially interleaved observations rather than scoring only fit data.
    holdout = (src[:,0].astype(int)+src[:,1].astype(int))%4 == 0
    matrix,inliers = cv2.findHomography(src[~holdout],dst[~holdout],cv2.RANSAC,pitch*.18)
    if matrix is None:
        return result
    predicted = cv2.perspectiveTransform(src[:,None,:],matrix)[:,0,:]
    errors = np.linalg.norm(predicted-dst,axis=1)/pitch
    supported = errors < .23
    coverage = len(set(map(tuple,src[supported])))/(rows*10)
    held = errors[holdout]
    result['quality'] = {'matched_fraction':float(coverage),
                         'holdout_count':int(len(held)),
                         'holdout_p90_error_pitch':float(np.quantile(held,.9)) if len(held) else None}
    if coverage < .65 or len(held) < 15 or np.quantile(held,.9) > .23:
        result['reason'] = 'Grid fit failed independent geometric residual/coverage checks'
        return result
    matrix[:2] /= scale
    inv = np.linalg.inv(matrix)
    hole_names = list(positions)
    allxy = cv2.perspectiveTransform(np.array([positions[h] for h in hole_names],dtype=float)[:,None,:],matrix)[:,0,:]
    if not np.isfinite(allxy).all() or np.any(allxy < 0) or np.any(allxy[:,0] >= size[0]) or np.any(allxy[:,1] >= size[1]):
        return result
    result.update(status='needs_orientation_review',reason='Geometric grid found; verify printed labels and complete row extent',
                  holes={h:xy.tolist() for h,xy in zip(hole_names,allxy)},
                  calibration={'board_to_image':matrix.tolist(),'image_to_board':inv.tolist(),
                               'board_fingerprint':result['board_fingerprint'],
                               'anchors':[], 'checks':[], 'source':'automatic_geometry_unreviewed'})
    return result


def label_mapping(board, *, left_top, right_top):
    """Map provisional IDs using the printed top-left hole of each five-column strip.

    Caller must obtain these labels from a person or a verified capture/profile
    convention. This is label orientation, not manual four-point calibration.
    """
    import re
    positions = hole_positions(board)
    rows = len(positions)//10
    require(set(positions) == {f'{c}{r}' for c in 'ABCDEFGHIJ' for r in range(1,rows+1)},
            'Label mapping requires a complete central grid')
    mapping = {}
    for provisional_columns, label in [('ABCDE',left_top),('FGHIJ',right_top)]:
        match = re.fullmatch(r'([AEFJ])([1-9][0-9]*)',label) if isinstance(label,str) else None
        require(match is not None, 'Supply a printed strip-corner hole, e.g. A63 or F1')
        column,row = match[1],int(match[2])
        require(row in (1,rows),'Strip corner must be row 1 or the final row')
        columns = {'A':'ABCDE','E':'EDCBA','F':'FGHIJ','J':'JIHGF'}[column]
        for source,target in zip(provisional_columns,columns):
            for r in range(1,rows+1):
                mapping[f'{source}{r}'] = f'{target}{r if row == 1 else rows+1-r}'
    require(set(mapping.values()) == set(positions), 'The two strip labels must describe different halves')
    return mapping


def suggest_hole(proposal, board, image_sha256, xy, *, verified_label_map=None):
    """Touch helper: provisional labels only; does not grant physical review."""
    from .geometry import snap
    require(proposal.get('status') == 'needs_orientation_review', 'No automatic grid available')
    require(proposal.get('image_sha256') == image_sha256, 'Grid belongs to another frame')
    require(proposal.get('board_fingerprint') == board_fingerprint(board), 'Grid belongs to another board')
    result = snap(proposal['calibration'],board,xy)
    result['provisional_hole'] = result.pop('hole')
    result['hole'] = None
    result['reason'] = 'Provisional grid position; printed labels/orientation must be verified before assigning a physical hole'
    result['labels_confirmed'] = False
    if verified_label_map is not None:
        positions = hole_positions(board)
        require(isinstance(verified_label_map,dict) and set(verified_label_map) == set(positions)
                and set(verified_label_map.values()) == set(positions), 'Label map must cover the same grid exactly')
        provisional = result['provisional_hole']
        result['hole'] = verified_label_map[provisional] if provisional else None
        result['alternatives'] = [verified_label_map[h] for h in result['alternatives']]
        result['labels_confirmed'] = True
        result['reason'] = 'Touch snapped using an explicitly verified label mapping; connection remains unconfirmed'
    return result
