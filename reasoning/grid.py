"""ML2 validation of ML1 geometry; automatic fits never grant human review."""
from copy import deepcopy
import hashlib
import json
import math

from labvision.autocalibration import label_mapping, suggest_hole
from labvision.geometry import board_fingerprint, hole_positions, inverse, project


class GridError(ValueError):
    """Controlled code suitable for an authorized backend caller."""


def require(condition, code):
    if not condition:
        raise GridError(code)


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def normalize_grid(proposal, board, receipt):
    """Sanitize optional model metadata; bad grids leave manual entry available.

    Use only for ML1 results/trusted persisted snapshots, never as a public
    endpoint accepting arbitrary client calibration. Rebuild inverse transforms
    from validated forward geometry instead of trusting a supplied inverse.
    """
    if proposal is None:
        return None  # Older ML1 records remain readable.
    unavailable = {'schema_version': 'ml1-grid-proposal-1', 'status': 'unavailable',
                   'reason': 'invalid_or_unbound_grid_proposal',
                   'labels_confirmed': False, 'reviewed': False}
    try:
        require(isinstance(proposal, dict), 'invalid_grid')
        if proposal.get('status') == 'unavailable':
            return {**unavailable, 'reason': 'unsupported_profile_or_grid_unavailable'}
        require(proposal.get('schema_version') == 'ml1-grid-proposal-1', 'invalid_grid')
        require(proposal.get('image_sha256') == receipt['sha256'] and
                proposal.get('image_size') == [receipt['width'], receipt['height']], 'grid_image_mismatch')
        fingerprint = board_fingerprint(board)
        require(proposal.get('board_fingerprint') == fingerprint, 'grid_board_mismatch')
        require(proposal.get('status') in ('not_found', 'needs_orientation_review'), 'invalid_grid_status')
        result = {'schema_version': 'ml1-grid-proposal-1', 'status': proposal['status'],
                  'image_sha256': receipt['sha256'], 'image_size': [receipt['width'], receipt['height']],
                  'board_fingerprint': fingerprint, 'labels_confirmed': False, 'reviewed': False,
                  'holes': {}, 'calibration': None}
        if proposal['status'] == 'not_found':
            return {**result, 'reason': 'complete_grid_not_found'}
        positions = hole_positions(board)
        rows = len(positions) // 10
        require(10 <= rows <= 70 and set(positions) ==
                {f'{c}{r}' for c in 'ABCDEFGHIJ' for r in range(1, rows + 1)}, 'unsupported_grid')
        require(all(positions[f'{c}{r}'] == [float(i + (2 if i >= 5 else 0)), float(r - 1)]
                    for i, c in enumerate('ABCDEFGHIJ') for r in range(1, rows + 1)), 'unsupported_grid')
        raw = proposal['calibration']
        require(isinstance(raw, dict) and raw.get('board_fingerprint') == fingerprint, 'invalid_grid_calibration')
        matrix = raw['board_to_image']
        require(isinstance(matrix, list) and len(matrix) == 3 and all(
            isinstance(row, list) and len(row) == 3 and all(finite(x) and abs(x) <= 1e9 for x in row)
            for row in matrix), 'invalid_grid_matrix')
        backward = inverse(matrix)
        holes = proposal['holes']
        require(isinstance(holes, dict) and set(holes) == set(positions), 'invalid_grid_holes')
        sanitized = {}
        for hole, position in positions.items():
            xy = holes[hole]
            require(isinstance(xy, list) and len(xy) == 2 and all(finite(x) for x in xy) and
                    0 <= xy[0] < receipt['width'] and 0 <= xy[1] < receipt['height'], 'invalid_grid_hole')
            projected = project(matrix, position)
            require(all(finite(x) for x in projected) and math.dist(projected, xy) <= 1e-4 and
                    math.dist(project(backward, xy), position) <= 1e-4, 'inconsistent_grid_geometry')
            sanitized[hole] = list(xy)
        quality = proposal['quality']
        require(isinstance(quality, dict) and finite(quality.get('matched_fraction')) and
                .65 <= quality['matched_fraction'] <= 1 and type(quality.get('holdout_count')) is int and
                15 <= quality['holdout_count'] <= 10000 and finite(quality.get('holdout_p90_error_pitch')) and
                0 <= quality['holdout_p90_error_pitch'] <= .23, 'insufficient_grid_quality')
        result.update(holes=sanitized, quality={k: quality[k] for k in
                      ('matched_fraction', 'holdout_count', 'holdout_p90_error_pitch')},
                      reason='verify_alignment_and_printed_labels', calibration={
                          'board_to_image': deepcopy(matrix), 'image_to_board': backward,
                          'board_fingerprint': fingerprint, 'anchors': [], 'checks': [],
                          'source': 'automatic_geometry_unreviewed'})
        return result
    except (ValueError, KeyError, TypeError, IndexError, OverflowError, ZeroDivisionError):
        return unavailable


def proposal_digest(proposal):
    return hashlib.sha256(json.dumps(proposal, sort_keys=True, allow_nan=False).encode()).hexdigest()


def accepted_labels(proposal, board, receipt, review, revision):
    """Resolve server-held explicit acceptance, not a client-supplied label map."""
    require(isinstance(proposal,dict) and proposal.get('status')=='needs_orientation_review','grid_unavailable')
    require(isinstance(review, dict) and review.get('acknowledgement') ==
            'reviewed_grid_alignment_and_printed_labels', 'grid_acceptance_required')
    require(review.get('image_sha256') == receipt['sha256'] and
            review.get('board_fingerprint') == board_fingerprint(board) and
            review.get('proposal_digest') == proposal_digest(proposal), 'stale_grid_acceptance')
    require(type(review.get('accepted_revision')) is int and 1 <= review['accepted_revision'] <= revision,
            'stale_grid_acceptance')
    return label_mapping(board, left_top=review.get('left_top'), right_top=review.get('right_top'))


def touch(proposal, board, receipt, xy, review=None, revision=1):
    require(proposal and proposal.get('status') == 'needs_orientation_review', 'grid_unavailable')
    require(isinstance(xy, (tuple, list)) and len(xy) == 2 and all(finite(x) for x in xy) and
            0 <= xy[0] < receipt['width'] and 0 <= xy[1] < receipt['height'], 'invalid_native_image_coordinates')
    mapping = accepted_labels(proposal, board, receipt, review, revision) if review is not None else None
    # A preview returns provisional labels only. Even an accepted mapping leaves
    # the endpoint unconfirmed and does not pair wires or mutate the candidate.
    return suggest_hole(proposal, board, receipt['sha256'], list(xy), verified_label_map=mapping)
