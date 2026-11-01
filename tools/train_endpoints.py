"""Fine-tune a pretrained detector; weak supervision must be acknowledged explicitly."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from labvision.endpoint_training import audit_groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--weights', type=Path, required=True)
    parser.add_argument('--epochs', type=int, default=30)
    parser.add_argument('--imgsz', type=int, default=768)
    parser.add_argument('--batch', type=int, default=4)
    parser.add_argument('--device', default='0')
    parser.add_argument('--allow-pseudo-labels', action='store_true')
    parser.add_argument('--synthetic-only', action='store_true')
    args = parser.parse_args()
    manifest_bytes = (args.dataset/'manifest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    audit_groups(manifest['records'])
    if not args.synthetic_only and manifest['summary']['contains_pseudo_labels'] and not args.allow_pseudo_labels:
        parser.error('Real labels are unreviewed. Use --allow-pseudo-labels for an experimental run only.')
    if not args.weights.is_file():
        parser.error('Download pretrained weights first; no random-weight fallback')
    if args.out.exists() and any(args.out.iterdir()):
        parser.error('Use a new/empty run directory')
    os.environ.setdefault('YOLO_CONFIG_DIR', str((args.out/'config').resolve()))
    os.environ.setdefault('MPLCONFIGDIR', str((args.out/'matplotlib').resolve()))
    os.environ.setdefault('YOLO_AUTOINSTALL', 'false')
    import torch
    from ultralytics import YOLO, settings
    settings.update({'sync': False})
    if args.device != 'cpu' and not torch.cuda.is_available():
        parser.error('CUDA unavailable in this Python; select the separate GPU environment or --device cpu')
    torch.set_num_threads(4)
    args.out.mkdir(parents=True, exist_ok=True)
    info = {'status': 'training', 'target': 'wire_end_region',
            'supervision': ('synthetic_only' if args.synthetic_only else
                            'synthetic_plus_unreviewed_visual_pseudo_labels' if manifest['summary']['contains_pseudo_labels']
                            else 'synthetic_plus_user_reviewed_regions'),
            'dataset_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
            'pretrained_sha256': hashlib.sha256(args.weights.read_bytes()).hexdigest(),
            'pretrained_file': args.weights.name, 'torch': torch.__version__,
            'cuda_available': torch.cuda.is_available(), 'epochs_requested': args.epochs,
            'real_accuracy_established': False,
            'note': 'Region detection only; no hole assignment, wire pairing or circuit correctness claim.'}
    report = args.out/'training-report.json'
    report.write_text(json.dumps(info, indent=2)+'\n', encoding='utf-8')
    start = time.monotonic()
    try:
        model = YOLO(str(args.weights.resolve()))
        config = args.dataset/('synthetic.yaml' if args.synthetic_only else 'combined.yaml')
        model.train(data=str(config.resolve()), epochs=args.epochs, imgsz=args.imgsz,
                    batch=args.batch, device=args.device, workers=0, seed=42,
                    project=str(args.out.resolve()), name='fit', exist_ok=False,
                    pretrained=True, patience=10, cache=False, amp=False,
                    plots=True, save=True, optimizer='AdamW', lr0=0.001,
                    mosaic=0.2, mixup=0, copy_paste=0, degrees=15,
                    close_mosaic=5, verbose=False)
        checkpoint = args.out/'fit'/'weights'/'best.pt'
        if not checkpoint.is_file():
            raise RuntimeError('Training returned without a checkpoint')
        info.update(status='complete_experimental', checkpoint=str(checkpoint.resolve()),
                    checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest())
    except BaseException as error:
        info.update(status='failed', error_type=type(error).__name__, error=str(error))
        raise
    finally:
        info['elapsed_seconds'] = round(time.monotonic()-start, 2)
        report.write_text(json.dumps(info, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    main()
