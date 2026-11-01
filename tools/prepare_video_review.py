"""Prepare one video keyframe for the existing calibrated circuit review UI."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from labvision.annotation import new_session
from labvision.detector_review import import_predictions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--board', type=Path, required=True)
    parser.add_argument('--weights', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        parser.error('Use a new or empty output directory')
    board = json.loads(args.board.read_text(encoding='utf-8-sig'))
    from labvision.video import extract_frames
    args.out.mkdir(parents=True, exist_ok=True)
    frames_dir = args.out/'capture'
    record = extract_frames(args.video, frames_dir/'frames')
    record.update(id='capture', frame_directory='frames')
    (frames_dir/'manifest.json').write_text(json.dumps({'videos': [record]}, indent=2), encoding='utf-8')
    subprocess.run([sys.executable, str(Path(__file__).with_name('predict_video_ends.py')),
                    '--frames', str(frames_dir), '--weights', str(args.weights),
                    '--out', str(args.out/'detections'), '--device', args.device,
                    '--confidence', '0.5'], check=True)
    best = max(record['selected'], key=lambda frame: frame['sharpness'])
    image = frames_dir/'frames'/best['file']
    session = new_session(image, [best['width'], best['height']], board,
                          'video-'+record['source_sha256'][:12])
    report = json.loads((args.out/'detections'/'predictions.json').read_text())
    count = import_predictions(session, report)
    session['video_source'] = {'sha256': record['source_sha256'],
                               'timestamp_s': best['timestamp_s'],
                               'selection': 'maximum sampled full-frame sharpness, not guaranteed best board view'}
    session_path = args.out/'review-session.json'
    session_path.write_text(json.dumps(session, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'image': str(image.resolve()), 'session': str(session_path.resolve()),
                      'proposals': count, 'status': 'needs_calibration_and_circuit_review'}))
    if args.open:
        from labvision.annotator import launch
        launch(image, board, session['assembly_id'], session_path=session_path)


if __name__ == '__main__':
    main()
