"""Bounded DINOv2-base LoRA pilot on the same region-supervision dataset as YOLO."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--pretrained', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--epochs', type=int, default=10)
    parser.add_argument('--batch', type=int, default=2)
    parser.add_argument('--size', type=int, default=448)
    parser.add_argument('--allow-pseudo-labels', action='store_true')
    args = parser.parse_args()
    if args.size % 14 or args.size < 224:
        parser.error('Size must be >=224 and a multiple of14')
    if args.out.exists() and any(args.out.iterdir()):
        parser.error('Use new/empty output directory')
    manifest_bytes = (args.dataset/'manifest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest['summary']['contains_pseudo_labels'] and not args.allow_pseudo_labels:
        parser.error('Unreviewed labels require --allow-pseudo-labels')
    import torch
    from torch import nn
    from PIL import Image
    from labvision.endpoint_training import audit_groups
    from labvision.lora_vision import DinoEndRegions, prepare_image, make_heatmap, decode_heatmap, region_metrics
    audit_groups(manifest['records'])
    if not torch.cuda.is_available():
        parser.error('Use the isolated CUDA training environment')
    torch.manual_seed(42)
    random.seed(42)
    torch.set_num_threads(4)
    model = DinoEndRegions(args.pretrained).cuda()
    trainable = [(name, p) for name, p in model.named_parameters() if p.requires_grad]
    if any(not (name.startswith('head.') or '.lora_' in name) for name, _ in trainable):
        raise ValueError('Base weights unexpectedly trainable')
    optimizer = torch.optim.AdamW([
        {'params': [p for name, p in trainable if '.lora_' in name], 'lr': 1e-4},
        {'params': list(model.head.parameters()), 'lr': 1e-3}], weight_decay=.01)
    scaler = torch.amp.GradScaler('cuda')
    heat_size = (args.size//14)*4
    records = manifest['records']
    cached = {}
    for row in records:
        path = args.dataset/row['image']
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Dataset image hash mismatch')
        proposals = json.loads((args.dataset/'proposals'/f"{row['id']}.json").read_text())
        with Image.open(path) as image:
            tensor, mapping = prepare_image(image, args.size)
        points = [a['xy'] for a in proposals['annotations']]
        cached[row['id']] = (tensor, make_heatmap(points, mapping, heat_size),
                              mapping, [a['box'] for a in proposals['annotations']])
    train = [r for r in records if r['split']=='train']
    val = [r for r in records if r['split']=='val']
    args.out.mkdir(parents=True)
    report = {'status': 'training', 'model': 'facebook/dinov2-base', 'method': 'LoRA',
              'rank': 8, 'alpha': 16, 'size': args.size,
              'total_parameters': sum(p.numel() for p in model.parameters()),
              'trainable_parameters': sum(p.numel() for _, p in trainable),
              'adapter_targets': model.adapter_targets,
              'dataset_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
              'pretrained_sha256': hashlib.sha256((args.pretrained/'model.safetensors').read_bytes()).hexdigest(),
              'supervision': 'same_synthetic_plus_unreviewed_AI_regions_as_YOLO',
              'real_accuracy_established': False, 'epochs': []}
    start, best = time.monotonic(), -1

    def predictions(rows):
        model.eval()
        output = []
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.float16):
            for row in rows:
                tensor, _, mapping, boxes = cached[row['id']]
                probability = model(tensor[None].cuda()).float().sigmoid()[0]
                output.append({'id': row['id'], 'source': row['source'], 'truth': boxes,
                               'predictions': decode_heatmap(probability, mapping)})
        return output

    try:
        for epoch in range(args.epochs):
            model.train()
            random.shuffle(train)
            losses = []
            for i in range(0, len(train), args.batch):
                subset = train[i:i+args.batch]
                tensors = torch.stack([cached[r['id']][0] for r in subset]).cuda()
                target = torch.stack([cached[r['id']][1] for r in subset]).cuda()
                optimizer.zero_grad(set_to_none=True)
                with torch.autocast('cuda', dtype=torch.float16):
                    logits = model(tensors)
                logits = logits.float()
                bce = nn.functional.binary_cross_entropy_with_logits(
                    logits, target, pos_weight=torch.tensor(25., device='cuda'))
                probability = logits.sigmoid()
                dice = 1-(2*(probability*target).sum()+1)/(probability.sum()+target.sum()+1)
                loss = bce+.5*dice
                if not torch.isfinite(loss):
                    raise ValueError('Non-finite training loss')
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                nn.utils.clip_grad_norm_([p for _, p in trainable], 1.)
                scaler.step(optimizer)
                scaler.update()
                losses.append(float(loss.detach()))
            validation = predictions(val)
            metric = max((region_metrics(validation, t/10) for t in range(1, 10)), key=lambda m: m['f1'])
            record = {'epoch': epoch+1, 'loss': sum(losses)/len(losses), 'validation': metric}
            report['epochs'].append(record)
            if metric['f1'] > best:
                best = metric['f1']
                torch.save({'trainable_state': model.trainable_state(), 'rank': 8, 'alpha':16,
                            'size':args.size, 'threshold':metric['threshold'], 'epoch':epoch+1,
                            'pretrained_sha256': report['pretrained_sha256']}, args.out/'best-adapter.pt')
                report['best_epoch'] = epoch+1
            print(json.dumps(record), flush=True)
            (args.out/'training-report.json').write_text(json.dumps(report, indent=2)+'\n')
        checkpoint = torch.load(args.out/'best-adapter.pt', weights_only=True, map_location='cpu')
        model.load_state_dict(checkpoint['trainable_state'], strict=False)
        report['test'] = {}
        for source in ('synthetic_ground_truth', 'assistant_visual_pseudo_label'):
            rows = [r for r in records if r['split']=='test' and r['source']==source]
            output = predictions(rows)
            report['test'][source] = region_metrics(output, checkpoint['threshold'])
            (args.out/f'{source}-test-predictions.json').write_text(json.dumps(output, indent=2)+'\n')
        report.update(status='complete_experimental',
                      peak_gpu_memory_bytes=torch.cuda.max_memory_allocated(),
                      selected_threshold=checkpoint['threshold'])
    except BaseException as error:
        report.update(status='failed', error_type=type(error).__name__, error=str(error))
        raise
    finally:
        report['elapsed_s'] = round(time.monotonic()-start, 3)
        (args.out/'training-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in {'epochs','adapter_targets'}}, indent=2))


if __name__ == '__main__':
    main()
