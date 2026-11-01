"""Exploratory same-data comparison; real pseudo-label agreement is not accuracy."""
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
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--adapter', type=Path, required=True)
    parser.add_argument('--pretrained', type=Path, required=True)
    parser.add_argument('--yolo', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        parser.error('Use new/empty output directory')
    args.out.mkdir(parents=True)
    os.environ.setdefault('YOLO_CONFIG_DIR', str((args.out/'config').resolve()))
    os.environ.setdefault('MPLCONFIGDIR', str((args.out/'matplotlib').resolve()))
    os.environ.setdefault('YOLO_AUTOINSTALL', 'false')
    from PIL import Image, ImageDraw, ImageOps
    import torch
    from ultralytics import YOLO, settings
    from labvision.lora_vision import DinoEndRegions, prepare_image, decode_heatmap, region_metrics
    from labvision.endpoint_training import audit_groups, region_box
    settings.update({'sync': False})
    torch.set_num_threads(4)
    torch.manual_seed(42)
    manifest = json.loads((args.dataset/'manifest.json').read_text())
    audit_groups(manifest['records'])
    checkpoint = torch.load(args.adapter, weights_only=True, map_location='cpu')
    if hashlib.sha256((args.pretrained/'model.safetensors').read_bytes()).hexdigest() != checkpoint['pretrained_sha256']:
        raise ValueError('Adapter/base-model identity mismatch')
    lora = DinoEndRegions(args.pretrained, checkpoint['rank'], checkpoint['alpha'])
    if set(lora.trainable_state()) != set(checkpoint['trainable_state']):
        raise ValueError('Adapter checkpoint is incomplete or contains base weights')
    lora.load_state_dict(checkpoint['trainable_state'], strict=False)
    lora.cuda().eval()
    yolo = YOLO(str(args.yolo.resolve()))
    outputs, elapsed = {'lora': [], 'yolo': []}, {'lora': 0., 'yolo': 0.}
    rows = [r for r in manifest['records'] if r['split'] in {'val', 'test'}]
    for row in rows:
        path = args.dataset/row['image']
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Dataset image hash mismatch')
        proposal = json.loads((args.dataset/'proposals'/f"{row['id']}.json").read_text())
        truth = [a['box'] for a in proposal['annotations']]
        with Image.open(path) as opened:
            image = opened.convert('RGB')
        tensor, mapping = prepare_image(image, checkpoint['size'])
        torch.cuda.synchronize()
        start = time.monotonic()
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.float16):
            probability = lora(tensor[None].cuda()).float().sigmoid()[0]
        lora_predictions = decode_heatmap(probability, mapping)
        torch.cuda.synchronize()
        elapsed['lora'] += time.monotonic()-start
        start = time.monotonic()
        prediction = yolo.predict(str(path.resolve()), imgsz=768, conf=.05,
                                  iou=.7, max_det=100, device=0, verbose=False)[0]
        yolo_predictions = []
        for box, score in zip(prediction.boxes.xyxy.cpu().tolist(), prediction.boxes.conf.cpu().tolist()):
            center = [(box[0]+box[2])/2, (box[1]+box[3])/2]
            yolo_predictions.append({'box': region_box(center, image.width, image.height), 'score': score})
        elapsed['yolo'] += time.monotonic()-start
        common = {'id': row['id'], 'source': row['source'], 'split': row['split'],
                  'image': str(path.resolve()), 'truth': truth}
        outputs['lora'].append({**common, 'predictions': lora_predictions})
        outputs['yolo'].append({**common, 'predictions': yolo_predictions})
    report = {'real_accuracy_established': False, 'method':
              'Same dataset/splits; center proposals converted to the same native-size regions; '
              'greedy one-to-one IoU>=0.5. Each threshold selected only on mixed validation F1. '
              'Different architectures, training objectives, augmentations and input resolutions; exploratory comparison.',
              'models': {}}
    thresholds = {}
    for name, predictions in outputs.items():
        validation = [r for r in predictions if r['split']=='val']
        best = max((region_metrics(validation, t/10) for t in range(1, 10)), key=lambda m: m['f1'])
        thresholds[name] = best['threshold']
        result = {'selected_threshold': best['threshold'], 'validation': best,
                  'inference_s': round(elapsed[name], 3), 'test': {}}
        for source in ('synthetic_ground_truth', 'assistant_visual_pseudo_label'):
            result['test'][source] = region_metrics(
                [r for r in predictions if r['split']=='test' and r['source']==source], best['threshold'])
        report['models'][name] = result
        (args.out/f'{name}-predictions.json').write_text(json.dumps(predictions, indent=2)+'\n')
    real_test = [r for r in rows if r['split']=='test' and r['source']=='assistant_visual_pseudo_label']
    sheet = Image.new('RGB', (800, 350*len(real_test)), '#111111')
    for i, row in enumerate(real_test):
        for j, name in enumerate(('yolo', 'lora')):
            prediction = next(p for p in outputs[name] if p['id']==row['id'])
            image = Image.open(prediction['image']).convert('RGB')
            draw = ImageDraw.Draw(image)
            selected = [p for p in prediction['predictions'] if p['score'] >= thresholds[name]]
            for p in selected:
                draw.rectangle(p['box'], outline='#00ffff', width=2)
            thumb = ImageOps.contain(image, (400, 320))
            tile = Image.new('RGB', (400, 350), '#222222')
            tile.paste(thumb, ((400-thumb.width)//2, 0))
            ImageDraw.Draw(tile).text((8, 327), f"{name} {row['id'].split('-frame')[0]}: {len(selected)} proposals", fill='white')
            sheet.paste(tile, (j*400, i*350))
    sheet.save(args.out/'comparison.jpg', quality=95)
    (args.out/'comparison.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
