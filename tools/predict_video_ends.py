"""Run the experimental region detector on a video or an existing frame manifest."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--video', type=Path)
    group.add_argument('--frames', type=Path, help='Directory containing prepare_videos manifest.json')
    parser.add_argument('--weights', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--confidence', type=float, default=0.25)
    args = parser.parse_args()
    if not 0 < args.confidence < 1:
        parser.error('Confidence threshold must be between 0 and 1')
    if args.out.exists() and any(args.out.iterdir()):
        parser.error('Use a new/empty output directory')
    if not args.weights.is_file():
        parser.error('Trained weights file missing')
    args.out.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('YOLO_CONFIG_DIR', str((args.out/'config').resolve()))
    os.environ.setdefault('MPLCONFIGDIR', str((args.out/'matplotlib').resolve()))
    os.environ.setdefault('YOLO_AUTOINSTALL', 'false')
    from PIL import Image, ImageDraw, ImageOps
    import torch
    from ultralytics import YOLO, settings
    settings.update({'sync': False})
    torch.set_num_threads(4)
    from labvision.video import extract_frames
    if args.video:
        record = extract_frames(args.video, args.out/'frames')
        record.update(id='video', frame_directory='frames')
        videos, root = [record], args.out
    else:
        manifest = json.loads((args.frames/'manifest.json').read_text())
        videos, root = manifest['videos'], args.frames
    model = YOLO(str(args.weights.resolve()))
    report = {'status': 'unreviewed_region_proposals', 'target': 'wire_end_region',
              'model_sha256': hashlib.sha256(args.weights.read_bytes()).hexdigest(),
              'confidence_threshold': args.confidence, 'device': args.device,
              'real_accuracy_established': False, 'connectivity': None,
              'limitations': ['Scores are uncalibrated; trained partly on pseudo labels.',
                              'Regions are not exact insertion points or hole IDs.',
                              'No inserted/loose classification, wire pairing or cross-view calibration/fusion.'],
              'videos': []}
    overview = Image.new('RGB', (1200, 300*((len(videos)+3)//4)), '#111111')
    start = time.monotonic()
    for i, video in enumerate(videos):
        folder = args.out/video['id']
        folder.mkdir(exist_ok=True)
        results = []
        best = max(video['selected'], key=lambda f: f['sharpness'])
        for frame in video['selected']:
            path = root/video['frame_directory']/frame['file']
            if hashlib.sha256(path.read_bytes()).hexdigest() != frame['sha256']:
                raise ValueError('Frame image hash differs from manifest')
            prediction = model.predict(source=str(path.resolve()), imgsz=768,
                                       conf=args.confidence, iou=0.7,
                                       device=args.device, verbose=False)[0]
            proposals = []
            boxes = prediction.boxes.xyxy.cpu().tolist()
            scores = prediction.boxes.conf.cpu().tolist()
            for j, (box, score) in enumerate(zip(boxes, scores)):
                proposals.append({'id': f'P{j+1}', 'box': box, 'score': score,
                                  'hole': None, 'kind': 'unknown', 'confirmed': False,
                                  'source': 'experimental_detector', 'reviewed': False})
            results.append({'image': str(path.resolve()), 'sha256': frame['sha256'],
                            'frame_index': frame['frame_index'], 'timestamp_s': frame['timestamp_s'],
                            'image_size': [frame['width'], frame['height']], 'proposals': proposals})
            with Image.open(path) as opened:
                image = opened.convert('RGB')
            draw = ImageDraw.Draw(image)
            for proposal in proposals:
                draw.rectangle(proposal['box'], outline='#00ffff', width=2)
            image.save(folder/frame['file'], quality=92)
            if frame == best:
                thumb = ImageOps.contain(image, (300, 270))
                tile = Image.new('RGB', (300, 300), '#222222')
                tile.paste(thumb, ((300-thumb.width)//2, 0))
                ImageDraw.Draw(tile).text((5, 278), f"{video['id']}: {len(proposals)} regions", fill='white')
                overview.paste(tile, ((i%4)*300, (i//4)*300))
        report['videos'].append({'video_id': video['id'], 'frames': results})
        print(f"{video['id']}: predicted {len(results)} frames", flush=True)
    report['inference_elapsed_s'] = round(time.monotonic()-start, 3)
    (args.out/'predictions.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    overview.save(args.out/'prediction-overview.jpg', quality=95)
    print(json.dumps({'status': report['status'], 'videos': len(videos),
                      'inference_elapsed_s': report['inference_elapsed_s']}))


if __name__ == '__main__':
    main()
