"""Select temporally spread sharp frames; no labels or split assignments inferred."""
import argparse
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from labvision.video import extract_frames as extract


def tile(path, label, size=(300, 250)):
    with Image.open(path) as source:
        thumb = ImageOps.contain(source.convert('RGB'), (size[0], size[1] - 28))
    canvas = Image.new('RGB', size, '#222222')
    canvas.paste(thumb, ((size[0] - thumb.width) // 2, 0))
    ImageDraw.Draw(canvas).text((5, size[1] - 24), label, fill='white')
    return canvas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--frames', type=int, default=6)
    parser.add_argument('--samples', type=int, default=48)
    args = parser.parse_args()
    paths = sorted(p for p in args.input.iterdir()
                   if p.suffix.lower() in {'.mp4', '.mov', '.avi', '.mkv'})
    if not paths:
        raise SystemExit('No video files found')
    if args.out.exists() and any(args.out.iterdir()):
        parser.error('Use a new or empty output directory to preserve earlier artifacts')
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = {'schema': 'ml1-video-frames-v1',
                'note': 'Unlabelled proposals. Review layouts before assigning splits. '
                        'All clips of the same layout must share a split. '
                        'Sharpness does not measure board visibility.',
                'videos': [], 'errors': []}
    overview = Image.new('RGB', (1200, 250 * ((len(paths) + 3) // 4)), '#111111')
    for i, path in enumerate(paths):
        video_id = f'video-{i+1:02d}'
        folder = args.out / video_id
        try:
            record = extract(path, folder, args.frames, args.samples)
            record.update(id=video_id, source=str(path.resolve()), frame_directory=video_id)
            sheet = Image.new('RGB', (300 * len(record['selected']), 250), '#111111')
            for j, frame in enumerate(record['selected']):
                sheet.paste(tile(folder / frame['file'], f"{video_id} {frame['timestamp_s']:.1f}s"), (300*j, 0))
            sheet.save(folder / 'contact.jpg', quality=90)
            best = max(record['selected'], key=lambda f: f['sharpness'])
            overview.paste(tile(folder / best['file'], f"{video_id}: {path.stem[-11:]}"),
                           ((i % 4)*300, (i // 4)*250))
            manifest['videos'].append(record)
            print(f"{video_id}: {record['duration_s']:.1f}s, {len(record['selected'])} frames", flush=True)
        except Exception as error:
            manifest['errors'].append({'source': str(path), 'error': str(error)})
            print(f'{video_id}: ERROR {error}', flush=True)
    overview.save(args.out / 'overview.jpg', quality=92)
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    if manifest['errors']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
