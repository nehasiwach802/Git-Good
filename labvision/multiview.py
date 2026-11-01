"""Experimental planar registration and endpoint consensus across video views."""
import cv2
import numpy as np


def track_video_views(path, reference_index, target_indices, step=8):
    """Chain short optical-flow homographies; return target->reference maps.

    Reject a whole chain after a weak link. Cumulative drift and non-planar scene
    motion remain possible; this is experimental registration, not calibration.
    """
    capture = cv2.VideoCapture(str(path))
    results = {reference_index: (np.eye(3), {'accepted': True, 'reason': 'reference_identity'})}
    def read(index):
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        ok, frame = capture.read()
        if not ok:
            return None
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    try:
        reference = read(reference_index)
        if reference is None:
            return results
        for direction in (-1, 1):
            targets = sorted([i for i in target_indices if (i-reference_index)*direction > 0],
                             reverse=direction < 0)
            current_index, previous, cumulative, links = reference_index, reference, np.eye(3), 0
            failed = None
            for target in targets:
                while current_index != target and failed is None:
                    next_index = current_index + direction*min(step, abs(target-current_index))
                    following = read(next_index)
                    corners = cv2.goodFeaturesToTrack(previous, maxCorners=800,
                        qualityLevel=.02, minDistance=8, blockSize=7)
                    if following is None or corners is None or len(corners) < 30:
                        failed = 'flow_insufficient_features'
                        break
                    tracked, status, _ = cv2.calcOpticalFlowPyrLK(previous, following, corners, None,
                        winSize=(25,25), maxLevel=4)
                    if tracked is None:
                        failed = 'flow_tracking_failed'
                        break
                    backward, back_status, _ = cv2.calcOpticalFlowPyrLK(following, previous, tracked, None,
                        winSize=(25,25), maxLevel=4)
                    if backward is None:
                        failed = 'flow_backward_failed'
                        break
                    keep = ((status.ravel()==1) & (back_status.ravel()==1) &
                            (np.linalg.norm(corners[:,0]-backward[:,0],axis=1) < 1))
                    a, b = corners[keep,0], tracked[keep,0]
                    if len(a) < 25:
                        failed = 'flow_roundtrip_rejected'
                        break
                    matrix, mask = cv2.findHomography(a,b,cv2.RANSAC,2,maxIters=2000)
                    if matrix is None or mask is None or mask.mean() < .65 or mask.sum() < 25:
                        failed = 'flow_weak_planar_fit'
                        break
                    coverage = cv2.contourArea(cv2.convexHull(a[mask.ravel().astype(bool)]))/(previous.shape[0]*previous.shape[1])
                    if coverage < .06:
                        failed = 'flow_narrow_fit'
                        break
                    cumulative = matrix @ cumulative
                    links += 1
                    previous, current_index = following, next_index
                if failed:
                    results[target] = (None, {'accepted': False, 'reason': failed, 'links': links})
                else:
                    if not np.isfinite(cumulative).all() or abs(np.linalg.det(cumulative)) < 1e-10:
                        results[target] = (None, {'accepted': False, 'reason': 'flow_degenerate_chain', 'links': links})
                        continue
                    inverse = np.linalg.inv(cumulative)
                    inverse /= inverse[2,2]
                    results[target] = (inverse.copy(), {'accepted': True,
                        'reason': 'chained_roundtrip_flow', 'links': links})
        return results
    finally:
        capture.release()


def register_view(source, reference):
    """Return source->reference homography, rejecting weak/spatially narrow fits.

    Breadboard is approximately planar; raised wires and loose ends are not.
    Feature registration cannot establish physical wire identity.
    """
    detector = cv2.SIFT_create(nfeatures=3500)
    def features(image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # Include scene detail: repeated hole texture alone is highly ambiguous.
        # Raised-wire parallax remains a limitation even with a strong fit.
        return detector.detectAndCompute(gray, None)
    ka, da = features(source)
    kb, db = features(reference)
    diagnostic = {'accepted': False}
    if da is None or db is None or len(da) < 12 or len(db) < 12:
        return None, {**diagnostic, 'reason': 'insufficient_features'}
    pairs = cv2.BFMatcher().knnMatch(da, db, k=2)
    matches = [pair[0] for pair in pairs if len(pair) == 2 and pair[0].distance < .75*pair[1].distance]
    diagnostic['matches'] = len(matches)
    if len(matches) < 16:
        return None, {**diagnostic, 'reason': 'insufficient_distinct_matches'}
    a = np.float32([ka[m.queryIdx].pt for m in matches])
    b = np.float32([kb[m.trainIdx].pt for m in matches])
    matrix, mask = cv2.findHomography(a, b, cv2.RANSAC, 3.0, maxIters=4000, confidence=.999)
    if matrix is None or mask is None or not np.isfinite(matrix).all():
        return None, {**diagnostic, 'reason': 'homography_failed'}
    inliers = mask.ravel().astype(bool)
    count, ratio = int(inliers.sum()), float(inliers.mean())
    diagnostic.update(inliers=count, inlier_ratio=ratio)
    if count < 14 or ratio < .45:
        return None, {**diagnostic, 'reason': 'weak_consensus'}
    area = cv2.contourArea(cv2.convexHull(b[inliers])) / (reference.shape[0]*reference.shape[1])
    error = np.linalg.norm(cv2.perspectiveTransform(a[inliers, None], matrix)[:, 0]-b[inliers], axis=1)
    diagnostic.update(reference_coverage=float(area), median_error_px=float(np.median(error)))
    if area < .04 or np.median(error) > 2:
        return None, {**diagnostic, 'reason': 'narrow_or_imprecise_fit'}
    corners = np.float32([[0,0],[source.shape[1],0],
                          [source.shape[1],source.shape[0]],[0,source.shape[0]]])
    warped = cv2.perspectiveTransform(corners[:, None], matrix)[:, 0]
    warped_area = abs(cv2.contourArea(warped))
    if (not np.isfinite(warped).all() or not cv2.isContourConvex(warped) or
            not .15 < warped_area/(reference.shape[0]*reference.shape[1]) < 6):
        return None, {**diagnostic, 'reason': 'implausible_projected_view'}
    return matrix, {**diagnostic, 'accepted': True, 'reason': 'planar_feature_consensus'}


def warp_proposals(proposals, matrix, size, view_id):
    width, height = size
    result = []
    for proposal in proposals:
        x1, y1, x2, y2 = proposal['box']
        xy = cv2.perspectiveTransform(np.float32([[[(x1+x2)/2, (y1+y2)/2]]]), matrix)[0, 0]
        if np.isfinite(xy).all() and 0 <= xy[0] < width and 0 <= xy[1] < height:
            result.append({'xy': xy.tolist(), 'score': float(proposal['score']), 'view': view_id})
    return result


def consensus(points, size, threshold=.5, minimum_views=2):
    """Cluster nearby mapped centers; at most one vote per source frame.

    Radius matches approximate endpoint region scale, not breadboard hole pitch.
    Scores are uncalibrated detector scores, never probabilities of correctness.
    """
    width, height = size
    radius = max(8, .012*max(size))
    clusters = []
    for point in sorted(points, key=lambda p: p['score'], reverse=True):
        if point['score'] < threshold:
            continue
        # Anchor-based clustering prevents chains joining neighboring endpoints.
        eligible = [c for c in clusters if point['view'] not in c['views'] and
                    np.linalg.norm(np.array(c['anchor'])-point['xy']) <= radius]
        if eligible:
            cluster = min(eligible, key=lambda c: np.linalg.norm(np.array(c['anchor'])-point['xy']))
            cluster['points'].append(point)
            cluster['views'].add(point['view'])
        else:
            clusters.append({'anchor': point['xy'], 'points': [point], 'views': {point['view']}})
    result = []
    for cluster in clusters:
        if len(cluster['views']) < minimum_views:
            continue
        center = np.average([p['xy'] for p in cluster['points']], axis=0,
                            weights=[p['score'] for p in cluster['points']])
        x, y = center.tolist()
        result.append({'box': [max(0,x-radius),max(0,y-radius),min(width,x+radius),min(height,y+radius)],
                       'score': max(p['score'] for p in cluster['points']),
                       'supporting_views': sorted(cluster['views']), 'hole': None,
                       'confirmed': False, 'reviewed': False, 'kind': 'unknown',
                       'source': 'experimental_multiview_consensus'})
    return result
