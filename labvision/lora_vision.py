"""Optional DINOv2 LoRA endpoint heatmaps. Requires the training environment."""
import math
import hashlib
from pathlib import Path

import torch
from torch import nn


class LoRALinear(nn.Module):
    """W(x) + alpha/r * B(A(x)); pretrained W is always frozen."""
    def __init__(self, base, rank=8, alpha=16, dropout=0.05):
        super().__init__()
        self.base = base.requires_grad_(False)
        self.lora_A = nn.Linear(base.in_features, rank, bias=False)
        self.lora_B = nn.Linear(rank, base.out_features, bias=False)
        nn.init.kaiming_uniform_(self.lora_A.weight, a=math.sqrt(5))
        nn.init.zeros_(self.lora_B.weight)
        self.dropout = nn.Dropout(dropout)
        self.scale = alpha/rank

    def forward(self, x):
        return self.base(x) + self.lora_B(self.lora_A(self.dropout(x)))*self.scale


class DinoEndRegions(nn.Module):
    def __init__(self, pretrained_path, rank=8, alpha=16):
        super().__init__()
        from transformers import Dinov2Model
        self.encoder = Dinov2Model.from_pretrained(
            str(pretrained_path), local_files_only=True, attn_implementation='sdpa')
        self.encoder.requires_grad_(False)
        targets = [(name, module) for name, module in self.encoder.named_modules()
                   if isinstance(module, nn.Linear)
                   and name.split('.')[-1] in {'query', 'value', 'q_proj', 'v_proj'}]
        if len(targets) != self.encoder.config.num_hidden_layers*2:
            raise ValueError(f'Unexpected DINO attention layout: {len(targets)} targets')
        self.adapter_targets = []
        for name, module in targets:
            parent_name, leaf = name.rsplit('.', 1)
            parent = self.encoder.get_submodule(parent_name)
            setattr(parent, leaf, LoRALinear(module, rank, alpha))
            self.adapter_targets.append(name)
        dim = self.encoder.config.hidden_size
        self.patch_size = self.encoder.config.patch_size
        self.head = nn.Sequential(
            nn.Conv2d(dim, 128, 1), nn.GELU(),
            nn.ConvTranspose2d(128, 64, 4, stride=2, padding=1), nn.GELU(),
            nn.ConvTranspose2d(64, 32, 4, stride=2, padding=1), nn.GELU(),
            nn.Conv2d(32, 1, 3, padding=1))
        nn.init.constant_(self.head[-1].bias, -2.)

    def forward(self, images):
        tokens = self.encoder(pixel_values=images).last_hidden_state[:, 1:, :]
        h, w = images.shape[-2]//self.patch_size, images.shape[-1]//self.patch_size
        features = tokens.transpose(1, 2).reshape(images.shape[0], -1, h, w)
        return self.head(features)

    def trainable_state(self):
        names = {name for name, p in self.named_parameters() if p.requires_grad}
        return {k: v.detach().cpu().clone() for k, v in self.state_dict().items() if k in names}


def prepare_image(image, size=448):
    """Aspect-preserving letterbox and ImageNet normalization; native mapping retained."""
    import numpy as np
    from PIL import Image
    image = image.convert('RGB')
    scale = min(size/image.width, size/image.height)
    width, height = round(image.width*scale), round(image.height*scale)
    left, top = (size-width)//2, (size-height)//2
    canvas = Image.new('RGB', (size, size), (124, 116, 104))
    canvas.paste(image.resize((width, height), Image.Resampling.BILINEAR), (left, top))
    tensor = torch.from_numpy(np.asarray(canvas).copy()).permute(2, 0, 1).float()/255
    tensor = (tensor-torch.tensor([.485, .456, .406])[:, None, None])/torch.tensor([.229, .224, .225])[:, None, None]
    return tensor, {'sx': width/image.width, 'sy': height/image.height,
                    'left': left, 'top': top, 'size': size,
                    'width': image.width, 'height': image.height}


def make_heatmap(points, mapping, heat_size):
    axis = torch.arange(heat_size, dtype=torch.float32)
    yy, xx = torch.meshgrid(axis, axis, indexing='ij')
    heat = torch.zeros(heat_size, heat_size)
    for x, y in points:
        hx = ((x*mapping['sx']+mapping['left']+.5)*heat_size/mapping['size'])-.5
        hy = ((y*mapping['sy']+mapping['top']+.5)*heat_size/mapping['size'])-.5
        gaussian = torch.exp(-((xx-hx)**2+(yy-hy)**2)/(2*1.1**2))
        heat = torch.maximum(heat, gaussian)
    return heat.unsqueeze(0)


def decode_heatmap(probability, mapping, minimum=0.05, limit=100):
    from .endpoint_training import region_box
    probability = probability.detach().float().cpu().squeeze()
    pooled = torch.nn.functional.max_pool2d(probability[None, None], 3, 1, 1)[0, 0]
    yy, xx = torch.where((probability >= minimum) & (probability == pooled))
    scores = probability[yy, xx]
    order = scores.argsort(descending=True)[:limit]
    proposals = []
    for index in order:
        x = (((float(xx[index])+.5)*mapping['size']/probability.shape[1])-.5-mapping['left'])/mapping['sx']
        y = (((float(yy[index])+.5)*mapping['size']/probability.shape[0])-.5-mapping['top'])/mapping['sy']
        if 0 <= x < mapping['width'] and 0 <= y < mapping['height']:
            proposals.append({'box': region_box([x, y], mapping['width'], mapping['height']),
                              'score': float(scores[index]), 'xy': [x, y],
                              'confirmed': False, 'hole': None, 'reviewed': False})
    return proposals


def box_iou(a, b):
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0]))*max(0, min(a[3], b[3])-max(a[1], b[1]))
    union = (a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection
    return intersection/union if union else 0.


def region_metrics(rows, threshold):
    tp = fp = fn = 0
    for row in rows:
        remaining = set(range(len(row['truth'])))
        for prediction in sorted(row['predictions'], key=lambda p: p['score'], reverse=True):
            if prediction['score'] < threshold:
                continue
            best = max(remaining, key=lambda i: box_iou(prediction['box'], row['truth'][i]), default=None)
            if best is not None and box_iou(prediction['box'], row['truth'][best]) >= .5:
                tp += 1
                remaining.remove(best)
            else:
                fp += 1
        fn += len(remaining)
    precision, recall = tp/max(1, tp+fp), tp/max(1, tp+fn)
    return {'tp': tp, 'fp': fp, 'fn': fn, 'precision': precision, 'recall': recall,
            'f1': 2*precision*recall/max(1e-12, precision+recall), 'threshold': threshold}


def load_adapter(pretrained_path, adapter_path, device='cpu'):
    checkpoint = torch.load(adapter_path, weights_only=True, map_location='cpu')
    path = Path(pretrained_path)/'model.safetensors'
    if hashlib.sha256(path.read_bytes()).hexdigest() != checkpoint['pretrained_sha256']:
        raise ValueError('Adapter/base-model identity mismatch')
    model = DinoEndRegions(pretrained_path, checkpoint['rank'], checkpoint['alpha'])
    if set(model.trainable_state()) != set(checkpoint['trainable_state']):
        raise ValueError('Incomplete adapter checkpoint or unexpected base weights')
    model.load_state_dict(checkpoint['trainable_state'], strict=False)
    return model.to(device).eval(), checkpoint
