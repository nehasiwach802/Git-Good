"""Smoke-test ML1 video callable, saving JPEG artifacts and JSON metadata separately."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video',type=Path,required=True)
    parser.add_argument('--board',type=Path,required=True)
    parser.add_argument('--weights',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        parser.error('Use a new/empty output directory')
    from labvision.video_upload import process_video
    detector = None
    if args.weights:
        from labvision.detection import EndpointDetector
        detector = EndpointDetector(args.weights)
    board = json.loads(args.board.read_text(encoding='utf-8-sig'))
    result = process_video(args.video,board,known_parts=[],detector=detector)
    args.out.mkdir(parents=True,exist_ok=True)
    for frame in result['frames']:
        data = frame.pop('jpeg_bytes')
        filename = f"{frame['id']}.jpg"
        (args.out/filename).write_bytes(data)
        frame['file'] = filename
    (args.out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'selected_frame_id':result['selected_frame_id'],
        'frames':len(result['frames']), 'mode':result['ml1']['mode'],
        'detection_status':result['ml1']['endpoint_detection']['status'],
        'status':result['status'],'output':str(args.out)}))


if __name__ == '__main__':
    main()
