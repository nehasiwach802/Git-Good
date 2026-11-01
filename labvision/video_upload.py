"""ML1 callable video preprocessing for the existing backend owner."""
import hashlib
import io
import math
from pathlib import Path
import tempfile

from PIL import Image

from .core import CandidateError, PART_PINS, require
from .geometry import hole_positions
from .upload import extract_upload


def process_video(video_path, board, *, known_parts=None, try_vision=False,
                  timeout=20, detector=None, extractor=None, frame_count=6,
                  samples=48, selected_frame_id=None, max_bytes=50*1024*1024,
                  max_duration_s=60, max_pixels=8_500_000, max_edge=1600,
                  auto_grid=False):
    """Return selected-image ML1 output and owned JPEG bytes for alternate views.

    Synchronous: invoke in the backend's worker, never on an async event loop.
    This owns only bounded preprocessing; backend owns uploads, persistence,
    job deadlines, authorization and transport. No cross-view fusion performed.
    Only selected frame is sent to Gemini when explicitly enabled.
    """
    require(type(frame_count) is int and type(samples) is int and
            1 <= frame_count <= samples <= 120, 'Invalid video sampling counts')
    require(type(max_bytes) is int and max_bytes > 0, 'Invalid video byte limit')
    require(type(max_pixels) is int and max_pixels > 0, 'Invalid pixel limit')
    require(type(max_edge) is int and 64 <= max_edge <= 2000, 'Invalid frame edge limit')
    require(type(max_duration_s) in (int,float) and math.isfinite(max_duration_s)
            and max_duration_s > 0, 'Invalid video duration limit')
    require(type(try_vision) is bool, 'try_vision must be boolean')
    require(type(auto_grid) is bool, 'auto_grid must be boolean')
    require(type(timeout) in (int,float) and 0 < timeout <= 30, 'Invalid vision timeout')
    known_parts = list(known_parts or [])
    require(all(part in PART_PINS for part in known_parts), 'Unsupported reported part')
    hole_positions(board)
    path = Path(video_path).resolve()
    require(path.is_file() and 0 < path.stat().st_size <= max_bytes,
            'Video must be a nonempty local file within the byte limit')
    from .video import extract_frames
    from .detection import configured_detector
    detector_status = 'disabled'
    if detector is None:
        try:
            detector = configured_detector()
        except (CandidateError,ImportError,RuntimeError,OSError,ValueError):
            detector_status = 'unavailable'
    with tempfile.TemporaryDirectory(prefix='labvision-video-') as folder:
        try:
            record = extract_frames(path, Path(folder)/'frames', count=frame_count,
                samples=samples, max_pixels=max_pixels, max_duration_s=max_duration_s)
        except (ValueError,OSError) as error:
            raise CandidateError('Video could not be decoded within preprocessing limits') from error
        frames = []
        for i, sample in enumerate(record['selected']):
            with Image.open(Path(folder)/'frames'/sample['file']) as opened:
                image = opened.convert('RGB')
                image.thumbnail((max_edge,max_edge))
                stream = io.BytesIO()
                image.save(stream, format='JPEG', quality=90)
                data, size = stream.getvalue(), list(image.size)
            require(len(data) <= 5*1024*1024, 'Encoded frame exceeds image upload limit')
            sha = hashlib.sha256(data).hexdigest()
            detection = {'status': detector_status}
            if detector is not None:
                frame_path = Path(folder)/f'normalized-{i}.jpg'
                frame_path.write_bytes(data)
                try:
                    detection = detector(frame_path, size, sha)
                except (CandidateError,ImportError,RuntimeError,OSError,ValueError):
                    detection = {'status':'unavailable', 'error_code':'endpoint_detector_unavailable'}
            frames.append({'id':f'F{i+1}', 'jpeg_bytes':data, 'sha256':sha,
                'content_type':'image/jpeg', 'size_bytes':len(data),
                'width':size[0], 'height':size[1], 'frame_index':sample['frame_index'],
                'timestamp_s':sample['timestamp_s'], 'timestamp_source':sample['timestamp_source'],
                'sharpness':sample['sharpness'],
                'decoded_size':[sample['width'],sample['height']],
                'endpoint_detection':detection})
        if auto_grid:
            from .autocalibration import detect_grid
            for frame in frames:
                try:
                    frame['grid_proposal'] = detect_grid(frame['jpeg_bytes'],board)
                except (CandidateError,ImportError,RuntimeError,OSError,ValueError):
                    frame['grid_proposal'] = {'status':'unavailable',
                        'reason':'Automatic grid requires a supported complete central-grid profile and decodable frame'}
        if selected_frame_id is None:
            aligned = [f for f in frames if f.get('grid_proposal',{}).get('status') == 'needs_orientation_review']
            selected = max(aligned or frames, key=lambda frame: frame['sharpness'])
        else:
            matching = [f for f in frames if f['id']==selected_frame_id]
            require(len(matching)==1, 'Selected frame ID is not among extracted frames')
            selected = matching[0]
        # Reuse selected-frame detections instead of running its model twice.
        result = extract_upload(selected['jpeg_bytes'], board, known_parts=known_parts,
            try_vision=try_vision, timeout=timeout, extractor=extractor,
            detector=lambda *args: selected['endpoint_detection'])
        if auto_grid:
            result['grid_proposal'] = selected['grid_proposal']
    return {'schema_version':'ml1-video-1', 'status':'needs_circuit_review',
            'selected_frame_id':selected['id'], 'ml1':result, 'frames':frames,
            'video':{'sha256':record['source_sha256'], 'size_bytes':path.stat().st_size,
                     'duration_s':record['duration_s'], 'fps':record['fps'],
                     'frame_count':record['frame_count']},
            'selection': ('explicit_frame_id' if selected_frame_id else
                          'sharpest_grid_proposal' if auto_grid and aligned else 'maximum_sampled_sharpness'),
            'limitations':['Sharpness is not a board-visibility or correctness guarantee.',
                          'Coordinates refer to returned JPEGs, not original video pixels.',
                          'No calibration transfer, wire pairing or multi-view fusion.',
                          'Changing selected frame requires a new image-bound review.']}
