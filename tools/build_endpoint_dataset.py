"""Build an explicitly weakly supervised region-detector pilot dataset."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sys

from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from labvision.endpoint_training import audit_groups, propose_regions, region_box, yolo_region


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--videos', type=Path, required=True)
    parser.add_argument('--synthetic', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seed-labels', type=Path,
                        help='Use only image-hash-bound visual seed proposals; other frames are excluded')
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        parser.error('Use a new/empty output directory')
    records, overview = [], []
    for split in ('train', 'val', 'test'):
        for kind in ('images', 'labels'):
            (args.out/kind/split).mkdir(parents=True, exist_ok=True)
    (args.out/'proposals').mkdir()

    def add(image_path, stem, split, assembly, annotations, source, **extra):
        data = image_path.read_bytes()
        with Image.open(image_path) as opened:
            w, h = opened.size
        image_rel = f'images/{split}/{stem}{image_path.suffix.lower()}'
        label_rel = f'labels/{split}/{stem}.txt'
        shutil.copyfile(image_path, args.out/image_rel)
        (args.out/label_rel).write_text(''.join(yolo_region(a['box'], w, h)+'\n' for a in annotations), encoding='utf-8')
        row = {'id': stem, 'image': image_rel, 'labels': label_rel,
               'sha256': hashlib.sha256(data).hexdigest(), 'split': split,
               'assembly_id': assembly, 'source': source, 'regions': len(annotations),
               'reviewed_real_ground_truth': False, **extra}
        records.append(row)
        (args.out/'proposals'/f'{stem}.json').write_text(json.dumps(
            {**row, 'image_size': [w, h], 'annotations': annotations}, indent=2)+'\n', encoding='utf-8')

    manifest = json.loads((args.videos/'manifest.json').read_text())
    videos = manifest['videos']
    seeds = None
    if args.seed_labels:
        seeds = {r['video_id']: r for r in json.loads(args.seed_labels.read_text())['frames']}
    if len(videos) < 6:
        raise ValueError('Need at least 6 video groups for this pilot builder')
    hashes = [v['source_sha256'] for v in videos]
    if len(set(hashes)) != len(hashes):
        raise ValueError('Duplicate source videos; resolve groups first')
    # Provisional clip groups only: layouts repeated across clips still need review.
    for i, video in enumerate(videos):
        split = 'train' if i < len(videos)-6 else 'val' if i < len(videos)-4 else 'test'
        best = max(video['selected'], key=lambda f: f['sharpness'])
        for frame in video['selected']:
            seed = seeds.get(video['id']) if seeds is not None else None
            if seeds is not None and (not seed or seed.get('exclude_reason')
                                       or seed['image_sha256'] != frame['sha256']):
                continue
            path = args.videos/video['frame_directory']/frame['file']
            if hashlib.sha256(path.read_bytes()).hexdigest() != frame['sha256']:
                raise ValueError('Video frame hash mismatch')
            with Image.open(path) as image:
                image = image.convert('RGB')
                reviewed = bool(seed and seed.get('reviewed') is True
                                and seed.get('source') == 'user_reviewed_region_labels'
                                and seed.get('completeness') == 'reviewed_visible_wire_end_regions')
                proposals = ([{'id': f'P{k+1}', 'xy': xy,
                               'box': region_box(xy, image.width, image.height),
                               'source': 'user_reviewed_region_labels' if reviewed else 'assistant_visual_proposal',
                               'reviewed': reviewed,
                               'kind': 'unknown', 'confirmed': False, 'hole': None}
                              for k, xy in enumerate(seed['xy'])]
                             if seed is not None else propose_regions(image))
                stem = video['id']+'-'+path.stem
                add(path, stem, split, 'provisional-'+video['id'], proposals,
                    'user_reviewed_region_labels' if reviewed else 'assistant_visual_pseudo_label' if seed is not None else 'heuristic_pseudo_label', video_id=video['id'],
                    timestamp_s=frame['timestamp_s'],
                    reviewed_real_ground_truth=reviewed,
                    completeness='reviewed_visible_wire_end_regions' if reviewed else 'unknown',
                    layout_group_verified=False)
                if frame == best:
                    draw = ImageDraw.Draw(image)
                    for p in proposals:
                        draw.rectangle(p['box'], outline='#00ffff', width=2)
                        draw.text((p['xy'][0]+3, p['xy'][1]), p['id'], fill='#00ffff')
                    thumb = ImageOps.contain(image, (300, 270))
                    tile = Image.new('RGB', (300, 300), '#222222')
                    tile.paste(thumb, ((300-thumb.width)//2, 0))
                    ImageDraw.Draw(tile).text((5, 278), f"{video['id']} {split}: {len(proposals)} proposals", fill='white')
                    overview.append(tile)
        print(f"{video['id']}: {split} (see manifest for label provenance)", flush=True)

    for line in (args.synthetic/'manifest.jsonl').read_text().splitlines():
        row = json.loads(line)
        labels = json.loads((args.synthetic/row['labels']).read_text())
        w, h = labels['image_size']
        annotations = []
        for wire in labels['wires']:
            for side in ('a', 'b'):
                endpoint = wire[side]
                if endpoint['visible']:
                    annotations.append({'id': wire['id']+'.'+side, 'xy': endpoint['xy'],
                                        'box': region_box(endpoint['xy'], w, h),
                                        'source': 'synthetic_visible_endpoint', 'reviewed': False})
        add(args.synthetic/row['image'], row['scene_id'], row['split'],
            row['assembly_id'], annotations, 'synthetic_ground_truth',
            completeness='visible_synthetic_wire_ends_only', layout_group_verified=True)

    audit_groups(records)
    counts = Counter((r['source'], r['split']) for r in records)
    summary = {'target': 'wire_end_region', 'status': 'experimental_weak_supervision',
               'contains_pseudo_labels': any(r['source'] in {'heuristic_pseudo_label', 'assistant_visual_pseudo_label'} for r in records),
               'reviewed_real_ground_truth_images': sum(r['reviewed_real_ground_truth'] for r in records),
               'layout_groups_provisional': True,
               'counts': {f'{source}/{split}': count for (source, split), count in counts.items()},
               'regions': sum(r['regions'] for r in records),
               'excluded_seeds': [r['video_id'] for r in (seeds or {}).values() if r.get('exclude_reason')],
               'warnings': ['No exact insertion-point, wire pairing, loose-end class or hole supervision.',
                            'Teacher omissions/false positives are not corrected ground truth.',
                            'Same-layout clips may remain related despite unique source hashes.',
                            'Real validation/test labels are pseudo labels: metrics are teacher agreement only.']}
    if not summary['contains_pseudo_labels']:
        summary['status'] = 'experimental_reviewed_regions'
        summary['warnings'] = [
            'No exact insertion-point, wire pairing, loose-end class or hole supervision.',
            'Same-layout clips may remain related despite unique source hashes.',
            'Reviewed real validation/test frames were seen during development; not an independent benchmark.']
    (args.out/'manifest.json').write_text(json.dumps({'summary': summary, 'records': records}, indent=2)+'\n', encoding='utf-8')
    for mode in ('combined', 'synthetic'):
        for split in ('train', 'val', 'test'):
            paths = [str((args.out/r['image']).resolve()) for r in records if r['split']==split
                     and (mode=='combined' or r['source']=='synthetic_ground_truth')]
            (args.out/f'{mode}-{split}.txt').write_text('\n'.join(paths)+'\n', encoding='utf-8')
        config = f'path: {json.dumps(str(args.out.resolve()))}\n'
        config += ''.join(f'{s}: {mode}-{s}.txt\n' for s in ('train', 'val', 'test'))
        config += 'names:\n  0: wire_end_region\n'
        (args.out/f'{mode}.yaml').write_text(config, encoding='utf-8')
    sheet = Image.new('RGB', (1200, ((len(overview)+3)//4)*300), '#111111')
    for i, tile in enumerate(overview):
        sheet.paste(tile, ((i%4)*300, (i//4)*300))
    sheet.save(args.out/'proposal-overview.jpg', quality=95)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
