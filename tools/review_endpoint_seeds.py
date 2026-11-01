"""Review a small seed batch locally. Original proposals and photos stay untouched."""
import argparse
import hashlib
import json
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageTk


def load_review(seeds, output):
    original = json.loads(seeds.read_text(encoding='utf-8'))
    if not output.exists():
        return original
    saved = json.loads(output.read_text(encoding='utf-8'))
    identity = lambda data: [(r['video_id'], r['image_sha256'], r['image'])
                             for r in data['frames']]
    if identity(saved) != identity(original):
        raise ValueError('Saved review belongs to different seeds; use a different output path')
    return saved


def save_review(data, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    data['human_reviewed'] = all(r.get('reviewed') is True for r in data['frames'])
    temporary = output.with_suffix(output.suffix + '.tmp')
    temporary.write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    temporary.replace(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.seeds.resolve() == args.out.resolve():
        parser.error('Use a separate output file to preserve original proposals')
    data = load_review(args.seeds, args.out)
    frames = data['frames']
    for row in frames:
        if hashlib.sha256(Path(row['image']).read_bytes()).hexdigest() != row['image_sha256']:
            raise ValueError('Seed image hash mismatch')
    root = tk.Tk()
    root.title('ML1 wire-end region review')
    first = next((i for i, row in enumerate(frames)
                  if not row.get('reviewed') and not row.get('exclude_reason')), 0)
    state = {'index': first, 'drag': None, 'scale': 1, 'photo': None}
    label = tk.Label(root, text='Drag a point to move; click empty space to add; right-click to delete. '
                     'Mark complete only after checking all visible wire ends. Loose ends count too.')
    label.pack()
    status = tk.Label(root)
    status.pack()
    saved_status = tk.Label(root, text='Changes save automatically; reopening resumes your review.')
    saved_status.pack()
    canvas = tk.Canvas(root, width=1000, height=760, bg='#222222')
    canvas.pack()

    def current():
        return frames[state['index']]

    def redraw():
        row = current()
        canvas.delete('all')
        with Image.open(row['image']) as original:
            state['scale'] = min(1000/original.width, 760/original.height, 1)
            image = original.resize((round(original.width*state['scale']),
                                     round(original.height*state['scale'])))
        state['photo'] = ImageTk.PhotoImage(image)
        canvas.create_image(0, 0, image=state['photo'], anchor='nw')
        for i, (x, y) in enumerate(row['xy']):
            x, y = x*state['scale'], y*state['scale']
            canvas.create_oval(x-6, y-6, x+6, y+6, outline='cyan', width=2)
            canvas.create_text(x+10, y-10, text=str(i+1), fill='cyan')
        done = sum(r.get('reviewed') is True for r in frames)
        status.config(text=f"{done} reviewed | {state['index']+1}/{len(frames)} {row['video_id']} | "
                      f"{len(row['xy'])} regions | reviewed: {row.get('reviewed', False)} "
                      f"{row.get('exclude_reason', '')}")

    def xy(event):
        return [round(event.x/state['scale'], 1), round(event.y/state['scale'], 1)]

    def nearest(point):
        points = current()['xy']
        distances = [((p[0]-point[0])**2+(p[1]-point[1])**2)**0.5 for p in points]
        return min(range(len(points)), key=distances.__getitem__) if distances and min(distances)*state['scale'] < 18 else None

    def invalidate():
        current()['reviewed'] = False
        current()['completeness'] = 'unknown'

    def press(event):
        point = xy(event)
        w, h = current()['image_size']
        if not (0 <= point[0] < w and 0 <= point[1] < h):
            return
        index = nearest(point)
        if index is None:
            current()['xy'].append(point)
            index = len(current()['xy'])-1
        state['drag'] = index
        invalidate()
        redraw()

    def move(event):
        if state['drag'] is not None:
            x, y = xy(event)
            w, h = current()['image_size']
            current()['xy'][state['drag']] = [min(w-1, max(0, x)), min(h-1, max(0, y))]
            invalidate()
            redraw()

    def remove(event):
        index = nearest(xy(event))
        if index is not None:
            del current()['xy'][index]
            invalidate()
            redraw()
            save()

    def navigate(delta):
        if not save():
            return
        state['drag'] = None
        state['index'] = (state['index']+delta) % len(frames)
        redraw()

    def complete():
        current().update(reviewed=True, source='user_reviewed_region_labels',
                         completeness='reviewed_visible_wire_end_regions')
        current().pop('exclude_reason', None)
        redraw()
        return save()

    def save():
        try:
            save_review(data, args.out)
        except OSError as error:
            messagebox.showerror('Could not save', str(error))
            return False
        saved_status.config(text=f'Saved automatically to {args.out}')
        return True

    def release(event):
        state['drag'] = None
        save()

    def complete_next():
        if not complete():
            return
        pending = [i for i, row in enumerate(frames)
                   if not row.get('reviewed') and not row.get('exclude_reason')]
        if pending:
            state['index'] = next((i for i in pending if i > state['index']), pending[0])
            redraw()
        else:
            messagebox.showinfo('Review saved', 'All non-skipped frames reviewed and saved. '
                                'You can close this window now.')

    def skip():
        invalidate()
        current()['exclude_reason'] = 'Skipped by reviewer: uncertain visible endpoints'
        navigate(1)

    def close():
        if save():
            root.destroy()

    canvas.bind('<Button-1>', press)
    canvas.bind('<B1-Motion>', move)
    canvas.bind('<ButtonRelease-1>', release)
    canvas.bind('<Button-3>', remove)
    buttons = tk.Frame(root)
    buttons.pack()
    for text, command in [('Previous', lambda: navigate(-1)), ('Next', lambda: navigate(1)),
                          ('Confirm & next (Enter)', complete_next),
                          ('Skip uncertain frame', skip), ('Save reviewed copy', save)]:
        tk.Button(buttons, text=text, command=command).pack(side='left')
    redraw()
    root.bind('<Return>', lambda event: complete_next())
    root.protocol('WM_DELETE_WINDOW', close)
    root.mainloop()


if __name__ == '__main__':
    main()
