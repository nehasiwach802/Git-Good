"""Register video views, select consensus on validation, compare reviewed development F1."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predictions', type=Path, required=True)
    parser.add_argument('--labels', type=Path, required=True)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--video-manifest', type=Path, help='Optional original videos for intermediate-frame optical flow')
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        parser.error('Use new/empty output directory')
    args.out.mkdir(parents=True, exist_ok=True)
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageOps
    from labvision.multiview import register_view, warp_proposals, consensus, track_video_views
    from labvision.endpoint_training import region_box
    from labvision.lora_vision import region_metrics
    predictions = json.loads(args.predictions.read_text())
    seeds = json.loads(args.labels.read_text())
    records = json.loads((args.dataset/'manifest.json').read_text())['records']
    splits = {r['video_id']: r['split'] for r in records if r.get('video_id')}
    labels = {r['video_id']: r for r in seeds['frames'] if r.get('reviewed') and not r.get('exclude_reason')}
    rows, alignment = [], []
    sources = ({v['id']: v for v in json.loads(args.video_manifest.read_text())['videos']}
               if args.video_manifest else {})
    def load(frame):
        path = Path(frame['image'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != frame['sha256']:
            raise ValueError('Prediction image hash mismatch')
        data = cv2.imread(str(path))
        if data is None or list(data.shape[1::-1]) != frame['image_size']:
            raise ValueError('Image unreadable or dimensions mismatch')
        return data
    for video in predictions['videos']:
        vid = video['video_id']
        if vid not in labels:
            continue
        seed = labels[vid]
        refs = [f for f in video['frames'] if f['sha256'] == seed['image_sha256']]
        if len(refs) != 1:
            raise ValueError('Missing or duplicate reference image')
        reference = refs[0]
        image = load(reference)
        size = reference['image_size']
        points = []
        tracked = {}
        if vid in sources:
            source = sources[vid]
            path = Path(source['source'])
            if hashlib.sha256(path.read_bytes()).hexdigest() != source['source_sha256']:
                raise ValueError('Video source hash mismatch')
            tracked = track_video_views(path, reference['frame_index'],
                                        [f['frame_index'] for f in video['frames']])
        for frame in video['frames']:
            if frame is reference:
                matrix, diagnostic = np.eye(3), {'accepted': True, 'reason': 'reference_identity'}
            else:
                matrix, diagnostic = register_view(load(frame), image)
                if matrix is None and frame['frame_index'] in tracked:
                    matrix, diagnostic = tracked[frame['frame_index']]
            alignment.append({'video_id': vid, 'source': frame['sha256'],
                              'reference': reference['sha256'], **diagnostic,
                              'matrix': matrix.tolist() if matrix is not None else None})
            if matrix is not None:
                points.extend(warp_proposals(frame['proposals'], matrix, size, str(frame['frame_index'])))
        single = warp_proposals(reference['proposals'], np.eye(3), size, str(reference['frame_index']))
        rows.append({'id': vid, 'split': splits[vid], 'image': reference['image'],
                     'sha256': reference['sha256'], 'size': size, 'points': points,
                     'single': single, 'truth': [region_box(xy, *size) for xy in seed['xy']]})
        print(f'{vid}: {sum(a["accepted"] for a in alignment if a["video_id"]==vid)} accepted views', flush=True)
    def scored(subset, threshold, support, multi):
        return [{'truth': r['truth'], 'predictions': consensus(
            r['points'] if multi else r['single'], r['size'], threshold, support)} for r in subset]
    validation = [r for r in rows if r['split']=='val']
    if not validation:
        raise ValueError('No validation frames')
    selections = {}
    for name, supports in [('single', [1]), ('multiview', [1,2,3])]:
        choices = []
        for support in supports:
            for threshold in (.25,.35,.45,.5,.55,.65,.75):
                metric = region_metrics(scored(validation, threshold, support, name=='multiview'), 0)
                choices.append({'threshold': threshold, 'minimum_views': support, 'validation': metric})
        best = max(choices, key=lambda item: item['validation']['f1'])
        test = [r for r in rows if r['split']=='test']
        best['reviewed_development'] = region_metrics(scored(test, best['threshold'], best['minimum_views'], name=='multiview'), 0)
        selections[name] = best
    report = {'real_accuracy_established': False, 'model_sha256': predictions['model_sha256'],
              'method': 'SIFT/RANSAC planar homography, optional chained optical-flow fallback; region-center matching IoU>=0.5; thresholds/support selected only on 2 real validation frames',
              'limitations': ['Four evaluation frames seen during earlier development; layout independence unverified.',
                             'Planar mapping may misplace raised or moving wires; no physical endpoint correspondence guarantee.',
                             'Repeated breadboard holes can create incorrect registration; feature gates reduce but do not eliminate it.',
                             'Input predictions truncated at their original confidence threshold; no retraining.'],
              'models': selections, 'alignments': alignment}
    (args.out/'comparison.json').write_text(json.dumps(report, indent=2)+'\n')
    best = selections['multiview']
    export = {'model_sha256': predictions['model_sha256'], 'status': 'unreviewed_multiview_proposals',
              'real_accuracy_established': False, 'videos': []}
    overview = Image.new('RGB', (1200, 300*((len(rows)+3)//4)), '#111111')
    for i, row in enumerate(rows):
        proposals = consensus(row['points'], row['size'], best['threshold'], best['minimum_views'])
        for j, p in enumerate(proposals):
            p['id'] = f'P{j+1}'
        export['videos'].append({'video_id': row['id'], 'frames': [{'image': row['image'],
            'sha256': row['sha256'], 'image_size': row['size'], 'proposals': proposals}]})
        with Image.open(row['image']) as opened:
            image = opened.convert('RGB')
        draw = ImageDraw.Draw(image)
        for box in row['truth']:
            draw.rectangle(box, outline='#00ff00', width=2)
        for p in proposals:
            draw.rectangle(p['box'], outline='#00ffff', width=2)
        tile = Image.new('RGB', (300,300), '#222222')
        thumb = ImageOps.contain(image, (300,270))
        tile.paste(thumb, ((300-thumb.width)//2,0))
        ImageDraw.Draw(tile).text((4,278), f'{row["id"]} {row["split"]} {len(proposals)} proposals', fill='white')
        overview.paste(tile, ((i%4)*300,(i//4)*300))
    overview.save(args.out/'comparison.jpg')
    (args.out/'predictions.json').write_text(json.dumps(export, indent=2)+'\n')
    print(json.dumps(selections, indent=2))


if __name__ == '__main__':
    main()
