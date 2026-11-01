"""Local video keyframe selection. No labels, calibration or connectivity inferred."""
import hashlib
import cv2
import numpy as np
from PIL import Image


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def extract_frames(path, output, count=6, samples=48):
    """Decode bounded samples, choosing sharpness within temporal bins.

    Sharpness is a relative full-frame heuristic, not board visibility or accuracy.
    Pixel coordinates refer to decoded frames (including decoder orientation).
    """
    if not 1 <= count <= samples <= 120:
        raise ValueError('Require 1 <= count <= samples <= 120')
    capture = cv2.VideoCapture(str(path))
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if not capture.isOpened() or not np.isfinite(fps) or fps <= 0 or total < 1:
            raise ValueError(f'Unreadable video or invalid frame metadata: {path}')
        indices = np.unique(np.linspace(0, total - 1, min(samples, total)).astype(int))
        selected = []
        for bucket in np.array_split(indices, min(count, len(indices))):
            best = None
            for index in bucket:
                capture.set(cv2.CAP_PROP_POS_FRAMES, int(index))
                ok, frame = capture.read()
                if not ok:
                    continue
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                factor = min(1.0, 640 / max(gray.shape))
                small = cv2.resize(gray, None, fx=factor, fy=factor)
                score = float(cv2.Laplacian(small, cv2.CV_64F).var())
                if best is None or score > best[0]:
                    milliseconds = float(capture.get(cv2.CAP_PROP_POS_MSEC))
                    has_pts = np.isfinite(milliseconds) and (milliseconds > 0 or index == 0)
                    timestamp = milliseconds / 1000 if has_pts else int(index) / fps
                    best = (score, int(index), frame, timestamp,
                            'decoder_pts' if has_pts else 'estimated_from_fps')
            if best is None:
                continue
            score, index, frame, timestamp, timestamp_source = best
            output.mkdir(parents=True, exist_ok=True)
            target = output / f'frame-{index:07d}.jpg'
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            image.save(target, quality=95)
            selected.append({'file': target.name, 'frame_index': index,
                             'timestamp_s': round(timestamp, 4),
                             'timestamp_source': timestamp_source,
                             'width': image.width, 'height': image.height,
                             'sharpness': round(score, 3), 'sha256': file_hash(target),
                             'label_status': 'unlabelled'})
        if not selected:
            raise ValueError(f'No frames decoded: {path}')
        return {'source_sha256': file_hash(path), 'fps': fps,
                'frame_count': total, 'duration_s': round(total / fps, 3),
                'selected': selected, 'assembly_id': None, 'split': 'unassigned',
                'layout_review_required': True}
    finally:
        capture.release()


