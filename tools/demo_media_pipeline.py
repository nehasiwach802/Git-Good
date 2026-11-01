"""Offline synthetic video -> ML2 diagnostic; no live model/Meko calls."""
from pathlib import Path
import json
import os
import sys
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from reasoning.media import process_video


def main():
    root=Path(__file__).resolve().parents[1]
    output=root/'outputs/ml2-media';output.mkdir(parents=True,exist_ok=True)
    board=json.loads((root/'examples/board-30.json').read_text())
    # This reproducible test never loads weights or sends images to a provider.
    previous=os.environ.get('LABVISION_ENDPOINT_WEIGHTS')
    os.environ['LABVISION_ENDPOINT_WEIGHTS']=''
    try:
        with TemporaryDirectory() as directory:
            video=Path(directory)/'synthetic.avi'
            writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'MJPG'),10,(64,48))
            if not writer.isOpened():raise RuntimeError('Synthetic video writer unavailable')
            for index in range(12):writer.write(np.full((48,64,3),index*15,dtype=np.uint8))
            writer.release()
            capture=process_video(video,board,known_parts=['7400'])
        capture.persist_assets(output/'assets')
        (output/'unreviewed.json').write_text(json.dumps(capture.snapshot(),indent=2)+'\n')
        # Synthetic manually reviewed fixture only, not extraction from a circuit photo.
        candidate=json.loads((root/'examples/7400-not.candidate.json').read_text())
        candidate.update(candidate_id=capture.candidate['candidate_id'],revision=capture.candidate['revision'],image_sha256=capture.image['sha256'])
        capture.candidate=candidate
        capture.confirm(candidate['revision'],acknowledgement='reviewed_all_connections_and_board')
        reference=json.loads((root/'examples/generalized/ml1-7400.json').read_text())['reference']
        result=capture.diagnose(reference,{'U1':'U1'},safety_profile='instructor_approved_low_voltage',
            measurements=[{'input':0,'output':1},{'input':1,'output':0}],student_expectations=[])
        (output/'diagnostic.json').write_text(json.dumps(result,indent=2)+'\n')
        changed=capture.select_frame(next(f['id'] for f in capture.frames if f['id']!=capture.selected_frame_id))
        (output/'frame-changed.json').write_text(json.dumps(changed.snapshot(),indent=2)+'\n')
        print('outputs/ml2-media: unreviewed.json, diagnostic.json, frame-changed.json, assets/')
        print('Diagnostic status: '+result['status']+'; ML3 result contract: '+result['schema_version'])
        print('Changed-frame review: '+str(changed.candidate['reviewed_revision']))
    finally:
        if previous is None:os.environ.pop('LABVISION_ENDPOINT_WEIGHTS',None)
        else:os.environ['LABVISION_ENDPOINT_WEIGHTS']=previous


if __name__=='__main__':main()
