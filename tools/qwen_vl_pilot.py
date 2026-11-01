"""Bounded Qwen2.5-VL-3B 4-bit QLoRA feasibility and before/after weak-label pilot."""
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
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--steps', type=int, default=32)
    parser.add_argument('--max-pixels', type=int, default=128*28*28)
    parser.add_argument('--allow-pseudo-labels', action='store_true')
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        parser.error('Use a new/empty output directory')
    if not 1 <= args.steps <= 200:
        parser.error('Pilot steps must be 1..200')
    data_bytes = (args.dataset/'manifest.json').read_bytes()
    manifest = json.loads(data_bytes)
    if manifest['summary']['contains_pseudo_labels'] and not args.allow_pseudo_labels:
        parser.error('Unreviewed targets require --allow-pseudo-labels')
    import torch
    from PIL import Image, ImageDraw, ImageOps
    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from labvision.endpoint_training import audit_groups, region_box
    from labvision.lora_vision import region_metrics
    from labvision.vlm_training import PROMPT, target_json, parse_points, answer_labels
    audit_groups(manifest['records'])
    if not torch.cuda.is_available():
        parser.error('CUDA environment required')
    torch.set_num_threads(4)
    torch.manual_seed(42)
    rng = random.Random(42)
    args.out.mkdir(parents=True)
    report = {'status':'loading', 'model':'Qwen/Qwen2.5-VL-3B-Instruct',
              'method':'4-bit NF4 QLoRA, frozen vision tower and base language model',
              'dataset_sha256':hashlib.sha256(data_bytes).hexdigest(),
              'target':'normalized wire-end region centers, not hole assignments',
              'supervision':'unreviewed AI regions plus synthetic targets',
              'real_accuracy_established':False, 'max_pixels':args.max_pixels,
              'steps_requested':args.steps, 'losses':[]}
    start = time.monotonic()

    def save():
        report['elapsed_s'] = round(time.monotonic()-start, 3)
        (args.out/'report.json').write_text(json.dumps(report, indent=2)+'\n')

    save()
    try:
        processor = AutoProcessor.from_pretrained(str(args.model), local_files_only=True,
                                                  min_pixels=64*28*28, max_pixels=args.max_pixels)
        quantization = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                                         bnb_4bit_use_double_quant=True,
                                         bnb_4bit_compute_dtype=torch.float16,
                                         llm_int8_skip_modules=['model.visual','lm_head'])
        model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            str(args.model), local_files_only=True, quantization_config=quantization,
            dtype=torch.float16, device_map={'':0}, attn_implementation='sdpa')
        report['loaded_gpu_bytes'] = torch.cuda.memory_allocated()
        import bitsandbytes as bnb
        vision = getattr(model.model, 'visual', None)
        if vision is None:
            raise ValueError('Missing expected vision tower')
        report['vision_quantized_linear_count'] = sum(isinstance(m,bnb.nn.Linear4bit) for m in vision.modules())
        if report['vision_quantized_linear_count']:
            raise ValueError('Vision quantization exclusion did not match module paths')
        if isinstance(model.get_output_embeddings(),bnb.nn.Linear4bit):
            raise ValueError('Tied output head must remain unquantized')
        model.requires_grad_(False)
        rows = manifest['records']
        real_train = [r for r in rows if r['split']=='train' and r['source']!='synthetic_ground_truth']
        synthetic = [r for r in rows if r['split']=='train' and r['source']=='synthetic_ground_truth']
        train = real_train + rng.sample(synthetic, min(23, len(synthetic)))
        rng.shuffle(train)
        tests = [r for r in rows if r['split']=='test' and r['source']=='assistant_visual_pseudo_label']
        report['train_sample_ids'] = [r['id'] for r in train]
        report['test_sample_ids'] = [r['id'] for r in tests]
        cache = {}

        def sample(row):
            if row['id'] in cache:
                return cache[row['id']]
            path = args.dataset/row['image']
            if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
                raise ValueError('Image hash mismatch')
            annotation = json.loads((args.dataset/'proposals'/f"{row['id']}.json").read_text())
            image = Image.open(path).convert('RGB')
            user = [{'role':'user','content':[{'type':'image','image':image}, {'type':'text','text':PROMPT}]}]
            prefix = processor.apply_chat_template(user, tokenize=True, return_dict=True,
                                                   return_tensors='pt', add_generation_prompt=True)
            answer = target_json(annotation['annotations'], image.width, image.height)
            full = processor.apply_chat_template(user+[{'role':'assistant','content':[{'type':'text','text':answer}]}],
                                                 tokenize=True, return_dict=True, return_tensors='pt')
            labels = answer_labels(full['input_ids'], prefix['input_ids'])
            if full['input_ids'].shape[-1] > 1024:
                raise ValueError('Sample exceeds bounded sequence length')
            cache[row['id']] = (prefix, full, labels, image.size,
                                [a['box'] for a in annotation['annotations']])
            return cache[row['id']]

        def gpu(batch):
            result = {k:v.to('cuda') if isinstance(v, torch.Tensor) else v for k,v in batch.items()}
            if 'pixel_values' in result:
                result['pixel_values'] = result['pixel_values'].to(torch.float16)
            return result

        def evaluate(stage):
            model.eval()
            output = []
            for row in tests:
                prefix, _, _, size, truth = sample(row)
                batch = gpu(prefix)
                with torch.inference_mode(), torch.autocast('cuda', dtype=torch.float16):
                    generated = model.generate(**batch, max_new_tokens=256, do_sample=False, use_cache=True)
                text = processor.batch_decode(generated[:, prefix['input_ids'].shape[-1]:],
                                              skip_special_tokens=True)[0]
                error, predictions = None, []
                try:
                    for xy in parse_points(text, *size):
                        predictions.append({'xy':xy, 'box':region_box(xy,*size),
                                            'confirmed':False,'reviewed':False,'hole':None})
                except (ValueError, TypeError, json.JSONDecodeError) as exc:
                    error = str(exc)
                output.append({'id':row['id'],'image':row['image'],'truth':truth,
                               'raw_output':text,'parse_error':error,'predictions':predictions})
                print(json.dumps({'stage':stage,'image':row['id'],'points':len(predictions),'parse_error':error}), flush=True)
            matching = [{**row, 'predictions':[{**p,'score':1.} for p in row['predictions']]} for row in output]
            result = region_metrics(matching,.5)
            result['valid_json_images'] = sum(r['parse_error'] is None for r in output)
            result['images'] = len(output)
            result['interpretation'] = 'Agreement with four unreviewed AI-labeled seed frames; not real accuracy. All syntactically valid points are evaluated; no model confidence is inferred.'
            (args.out/f'{stage}-predictions.json').write_text(json.dumps(output, indent=2)+'\n')
            return result

        report.update(status='baseline', baseline=evaluate('before'))
        save()
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True,
                         gradient_checkpointing_kwargs={'use_reentrant':False})
        # Keep the frozen vision tower/embeddings in FP16 to preserve 8GB headroom.
        visual = getattr(model, 'visual', None)
        if visual is None:
            visual = getattr(model.model, 'visual', None)
        if visual is None:
            raise ValueError('Cannot locate/freeze the vision tower')
        visual.to(dtype=torch.float16)
        model.get_input_embeddings().to(dtype=torch.float16)
        output_embeddings = model.get_output_embeddings()
        if output_embeddings.__class__.__name__ != 'Linear4bit':
            output_embeddings.to(dtype=torch.float16)
        model = get_peft_model(model, LoraConfig(r=8, lora_alpha=16,
                              target_modules=['q_proj','v_proj'], lora_dropout=.05,
                              bias='none', task_type='CAUSAL_LM'))
        names = [name for name,p in model.named_parameters() if p.requires_grad]
        if any('lora_' not in name or 'visual' in name for name in names):
            raise ValueError('Unexpected trainable base/vision parameters')
        report['trainable_parameters'] = sum(p.numel() for p in model.parameters() if p.requires_grad)
        model.config.use_cache = False
        model.train()
        optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=1e-4)
        scaler = torch.amp.GradScaler('cuda')
        report['status'] = 'training'
        save()
        for step in range(args.steps):
            row = train[step % len(train)]
            _, full, labels, _, _ = sample(row)
            optimizer.zero_grad(set_to_none=True)
            batch = gpu(full)
            with torch.autocast('cuda', dtype=torch.float16):
                loss = model(**batch, labels=labels.to('cuda'), use_cache=False).loss
            if not torch.isfinite(loss):
                raise ValueError('Non-finite loss')
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],1.)
            scaler.step(optimizer)
            scaler.update()
            record = {'step':step+1,'loss':float(loss.detach()),'sample':row['id']}
            report['losses'].append(record)
            print(json.dumps(record), flush=True)
            save()
        model.save_pretrained(args.out/'adapter')
        processor.save_pretrained(args.out/'adapter')
        model.gradient_checkpointing_disable()
        model.config.use_cache = True
        report['after'] = evaluate('after')
        report.update(status='complete_experimental', peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated())
    except BaseException as exc:
        report.update(status='failed',error_type=type(exc).__name__,error=str(exc),
                      peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated())
        raise
    finally:
        save()
    print(json.dumps({k:v for k,v in report.items() if k not in {'losses','train_sample_ids','test_sample_ids'}},indent=2))


if __name__ == '__main__':
    main()
