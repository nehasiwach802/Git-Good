"""Image-bound detector proposals for explicit endpoint review; no inferred pairing."""
from copy import deepcopy
import math

from .annotation import invalidate
from .core import endpoints, require
from .geometry import calibration_quality, snap


def import_predictions(session, report):
    report = report.get('endpoint_detection', report)
    matches = [frame for video in report.get('videos', []) for frame in video.get('frames', [])
               if frame.get('sha256') == session['image_sha256']]
    require(len(matches) == 1, 'Prediction report must contain exactly one matching image hash')
    frame = matches[0]
    require(frame['image_size'] == session['image_size'], 'Prediction dimensions differ')
    w, h = session['image_size']
    proposals, identifiers = [], set()
    for item in frame['proposals']:
        identifier = item['id']
        require(isinstance(identifier, str) and identifier and identifier not in identifiers,
                'Duplicate or invalid proposal ID')
        identifiers.add(identifier)
        box = item['box']
        require(len(box) == 4 and all(type(v) in (int, float) and math.isfinite(v) for v in box),
                'Invalid detector box')
        x1, y1, x2, y2 = box
        require(0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h, 'Detector box outside image')
        proposals.append({'id': identifier, 'box': list(box),
                          'xy': [(x1+x2)/2, (y1+y2)/2], 'confirmed': False})
    session['detector_proposals'] = {'image_sha256': session['image_sha256'],
                                    'model_sha256': report.get('model_sha256'),
                                    'proposals': proposals}
    return len(proposals)


def assign_proposal(session, target, identifier):
    pool = session.get('detector_proposals', {})
    require(pool.get('image_sha256') == session['image_sha256'], 'Proposal image mismatch')
    calibration = session.get('calibration')
    require(calibration is not None, 'Calibrate first')
    require(calibration_quality(calibration, session['board'])['validated'],
            'Validate calibration with two separate check holes first')
    lookup = {name: point for name, point, _ in endpoints(session['candidate'])}
    require(target in lookup, 'Select an existing endpoint')
    found = [p for p in pool.get('proposals', []) if p['id'] == identifier]
    require(len(found) == 1, 'Unknown proposal ID')
    proposal = found[0]
    result = snap(calibration, session['board'], proposal['xy'])
    result.update(source='vision', confirmed=False, visible=None,
                  proposal_origin='experimental_detector', proposal_reviewed=False,
                  detector_proposal_id=identifier,
                  reason='Detector region center, not verified insertion point; inspect and correct')
    lookup[target].clear()
    lookup[target].update(deepcopy(result))
    for wire in session['candidate']['wires']:
        if target in (wire['id']+'.a', wire['id']+'.b'):
            wire['pairing_reviewed'] = False
    invalidate(session)
    return result
