"""Optional local endpoint inference for trusted, explicitly configured weights."""
import hashlib
import os
from pathlib import Path
import threading

from .core import CandidateError, require


class EndpointDetector:
    """Reuse one model safely across upload jobs; imports optional deps lazily.

    Weights must be a trusted local file. No download or random-weight fallback.
    Outputs are region proposals, never confirmed wiring or physical hole IDs.
    """
    def __init__(self, weights, *, device='cpu', confidence=.5, model_factory=None):
        path = Path(weights).resolve()
        require(path.is_file(), 'Endpoint detector weights are missing')
        require(type(confidence) in (int, float) and 0 < confidence < 1,
                'Endpoint confidence must be between zero and one')
        self.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        self.device, self.confidence = device, confidence
        self.lock = threading.Lock()
        if model_factory is None:
            # Host controls cache locations. Avoid runtime dependency downloads.
            os.environ.setdefault('YOLO_AUTOINSTALL', 'false')
            from ultralytics import YOLO, settings
            settings.update({'sync': False})
            model_factory = YOLO
        self.model = model_factory(str(path))

    def __call__(self, path, image_size, image_sha256):
        require(hashlib.sha256(Path(path).read_bytes()).hexdigest() == image_sha256,
                'Detector image hash mismatch')
        width, height = image_size
        with self.lock:
            prediction = self.model.predict(source=str(Path(path).resolve()),
                imgsz=768, conf=self.confidence, iou=.7, max_det=100,
                device=self.device, verbose=False)[0]
        boxes = prediction.boxes.xyxy.cpu().tolist()
        scores = prediction.boxes.conf.cpu().tolist()
        import math
        require(len(boxes) == len(scores), 'Detector returned inconsistent results')
        proposals = []
        for box, score in zip(boxes, scores):
            require(len(box) == 4 and all(math.isfinite(v) for v in box) and
                    math.isfinite(score) and 0 <= score <= 1, 'Invalid detector output')
            x1, y1, x2, y2 = box
            require(0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height,
                    'Detector box outside uploaded image')
            proposals.append({'id': f'P{len(proposals)+1}', 'box': box, 'score': score,
                              'hole': None, 'confirmed': False, 'reviewed': False,
                              'kind': 'unknown', 'source': 'experimental_detector'})
        return {'status': 'unreviewed_region_proposals', 'model_sha256': self.sha256,
                'confidence_threshold': self.confidence, 'target': 'wire_end_region',
                'real_accuracy_established': False,
                'videos': [{'video_id': 'uploaded-image', 'frames': [{
                    'sha256': image_sha256, 'image_size': list(image_size),
                    'proposals': proposals}]}]}


_configured = None
_configured_key = None
_configuration_lock = threading.Lock()


def configured_detector():
    """Opt in using host process env; .env Gemini parser remains unchanged."""
    global _configured, _configured_key
    filename = os.environ.get('LABVISION_ENDPOINT_WEIGHTS', '').strip()
    if not filename:
        return None
    path = Path(filename).resolve()
    require(path.is_file(), 'Configured endpoint weights unavailable')
    key = (str(path), path.stat().st_mtime_ns, path.stat().st_size)
    with _configuration_lock:
        if _configured is None or _configured_key != key:
            _configured = EndpointDetector(path)
            _configured_key = key
        return _configured
