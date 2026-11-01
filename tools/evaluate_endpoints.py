"""Keep synthetic benchmark results separate from agreement with AI proposals."""
import argparse
import json
import os
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--weights', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--device', default='0')
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        parser.error('Use a new/empty output directory')
    args.out.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('YOLO_CONFIG_DIR', str((args.out/'config').resolve()))
    os.environ.setdefault('MPLCONFIGDIR', str((args.out/'matplotlib').resolve()))
    os.environ.setdefault('YOLO_AUTOINSTALL', 'false')
    import torch
    from ultralytics import YOLO, settings
    settings.update({'sync': False})
    torch.set_num_threads(4)
    manifest = json.loads((args.dataset/'manifest.json').read_text())
    real = [r for r in manifest['records'] if r['split']=='test' and r['source']!='synthetic_ground_truth']
    pseudo = [r for r in real if not r.get('reviewed_real_ground_truth')]
    reviewed = [r for r in real if r.get('reviewed_real_ground_truth')]
    (args.out/'pseudo-test.txt').write_text('\n'.join(str((args.dataset/r['image']).resolve()) for r in pseudo)+'\n')
    config = {'path': str(args.dataset.resolve()), 'train': 'combined-train.txt',
              'val': 'combined-val.txt', 'test': str((args.out/'pseudo-test.txt').resolve()),
              'names': {0: 'wire_end_region'}}
    import yaml
    (args.out/'pseudo.yaml').write_text(yaml.safe_dump(config))
    (args.out/'reviewed-test.txt').write_text('\n'.join(str((args.dataset/r['image']).resolve()) for r in reviewed)+'\n')
    (args.out/'reviewed.yaml').write_text(yaml.safe_dump({**config, 'test': str((args.out/'reviewed-test.txt').resolve())}))
    model = YOLO(str(args.weights.resolve()))
    report = {'real_accuracy_established': False,
              'note': 'Regions, not exact points or holes. Real frames were used during development; physical layout independence remains unverified. Reviewed scores are development checks, not independent generalization estimates.',
              'benchmarks': {}}
    benchmarks = [('synthetic', args.dataset/'synthetic.yaml')]
    if pseudo:
        benchmarks.append(('ai_label_agreement', args.out/'pseudo.yaml'))
    if reviewed:
        benchmarks.append(('reviewed_development', args.out/'reviewed.yaml'))
    for name, config_path in benchmarks:
        start = time.monotonic()
        metrics = model.val(data=str(config_path.resolve()), split='test',
                            imgsz=768, batch=4, device=args.device, workers=0,
                            project=str(args.out.resolve()), name=name,
                            plots=False, verbose=False)
        report['benchmarks'][name] = {'results': {k: float(v) for k, v in metrics.results_dict.items()},
                                      'elapsed_s': round(time.monotonic()-start, 3),
                                      'interpretation': {'synthetic': 'Stylized synthetic test only', 'ai_label_agreement': 'Agreement with unreviewed AI region proposals; not real accuracy', 'reviewed_development': 'User-reviewed regions on development-seen frames; layout independence unverified'}[name]}
    (args.out/'evaluation.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
