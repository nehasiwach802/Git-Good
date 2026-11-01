"""Local MP4 -> keyframes -> unreviewed DINOv2 LoRA wire-end regions."""
import argparse
from contextlib import nullcontext
import json
import hashlib
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--pretrained', type=Path, required=True)
    parser.add_argument('--adapter', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        parser.error('Use new/empty output directory')
    import torch
    from PIL import Image, ImageDraw, ImageOps
    from labvision.lora_vision import load_adapter, prepare_image, decode_heatmap
    from labvision.video import extract_frames
    torch.set_num_threads(4)
    args.out.mkdir(parents=True)
    model, checkpoint = load_adapter(args.pretrained, args.adapter, args.device)
    video = extract_frames(args.video, args.out/'frames')
    report = {'status': 'unreviewed_region_proposals', 'model': 'dinov2-base-lora',
              'video_sha256': video['source_sha256'],
              'adapter_sha256': hashlib.sha256(args.adapter.read_bytes()).hexdigest(),
              'threshold': checkpoint['threshold'], 'real_accuracy_established': False,
              'connectivity': None, 'hole_assignment': None, 'frames': [],
              'limitations': ['Synthetic and unreviewed AI-region supervision only.',
                              'No exact contact/inserted-loose classification, hole mapping, wire pairing or calibrated multi-view fusion.']}
    sheet = Image.new('RGB', (300*len(video['selected']), 300), '#111111')
    start = time.monotonic()
    for i, frame in enumerate(video['selected']):
        path = args.out/'frames'/frame['file']
        image = Image.open(path).convert('RGB')
        tensor, mapping = prepare_image(image, checkpoint['size'])
        context = torch.autocast('cuda', dtype=torch.float16) if args.device=='cuda' else nullcontext()
        with torch.inference_mode(), context:
            probability = model(tensor[None].to(args.device)).float().sigmoid()[0]
        proposals = [p for p in decode_heatmap(probability, mapping) if p['score'] >= checkpoint['threshold']]
        for proposal in proposals:
            proposal.update(source='dinov2_lora_experimental', kind='unknown')
        report['frames'].append({**frame, 'proposals': proposals})
        draw = ImageDraw.Draw(image)
        for proposal in proposals:
            draw.rectangle(proposal['box'], outline='#00ffff', width=2)
        image.save(args.out/frame['file'], quality=95)
        thumb = ImageOps.contain(image, (300, 270))
        tile = Image.new('RGB', (300, 300), '#222222')
        tile.paste(thumb, ((300-thumb.width)//2, 0))
        ImageDraw.Draw(tile).text((5, 278), f"{frame['timestamp_s']:.1f}s: {len(proposals)} regions", fill='white')
        sheet.paste(tile, (i*300, 0))
    report['inference_elapsed_s'] = round(time.monotonic()-start, 3)
    (args.out/'predictions.json').write_text(json.dumps(report, indent=2)+'\n')
    sheet.save(args.out/'contact.jpg', quality=95)
    print(json.dumps({'status':report['status'], 'frames':len(report['frames']),
                      'inference_elapsed_s':report['inference_elapsed_s']}))


if __name__ == '__main__':
    main()
