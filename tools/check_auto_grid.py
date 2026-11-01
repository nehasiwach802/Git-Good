"""Detect a central grid and save an inspectable overlay plus image-bound JSON."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from labvision.autocalibration import detect_grid
from labvision.core import make_board


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image',type=Path)
    parser.add_argument('--rows',type=int,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        parser.error('Use a new or empty output directory')
    board = make_board(args.rows)
    result = detect_grid(args.image.read_bytes(),board)
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'grid.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (args.out/'board.json').write_text(json.dumps(board,indent=2)+'\n',encoding='utf-8')
    from PIL import Image,ImageDraw
    with Image.open(args.image) as original:
        overlay = original.convert('RGB')
    draw = ImageDraw.Draw(overlay)
    for name,(x,y) in result['holes'].items():
        draw.ellipse((x-2,y-2,x+2,y+2),outline='#00ffbf',width=1)
        if name in ('A1','J1',f'A{args.rows}',f'J{args.rows}'):
            draw.text((x+4,y),name+'?',fill='#ff5500')
    overlay.save(args.out/'overlay.png')
    print(json.dumps({k:v for k,v in result.items() if k not in ('holes','calibration')}))


if __name__ == '__main__':
    main()
