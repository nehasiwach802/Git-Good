"""Offline synthetic HTTP transcript; no live vision, Qwen or product memory."""
from io import BytesIO
import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
import cv2
import numpy as np
from backend.app import create_app
from backend.config import Settings
from backend.catalog import load_catalog
from knowledge_lifecycle import Principal


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--grid',action='store_true',help='Exercise public grid-review-1 with a synthetic drawn grid')
    parser.add_argument('--wire-only',action='store_true',help='Run the wire-only exercise without fake components or measurements')
    options=parser.parse_args()
    if options.wire_only:options.grid=True
    root=Path(__file__).resolve().parents[1]
    catalog=load_catalog(root/'backend/catalog.json')
    for item in catalog.values():item['workflow_approved']=True  # Synthetic fixture approval only.
    with TemporaryDirectory() as clip_directory:
        clip=Path(clip_directory)/'synthetic.mp4'
        pixels=None
        if options.grid:
            from labvision.geometry import hole_positions,project
            image=Image.new('RGB',(300,504),'white');draw=ImageDraw.Draw(image)
            for point in hole_positions(catalog[('nand-not-example','1')]['board']).values():
                x,y=project([[14,.035,65],[0,14,40],[0,0,1]],point)
                draw.rectangle((x-2,y-2,x+2,y+2),fill='black')
            pixels=cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2BGR)
        writer=cv2.VideoWriter(str(clip),cv2.VideoWriter_fourcc(*'mp4v'),10,(300,504) if options.grid else (64,48))
        if not writer.isOpened():raise RuntimeError('Synthetic MP4 writer unavailable')
        for i in range(12):writer.write(pixels if pixels is not None else np.full((48,64,3),i*15,dtype=np.uint8))
        writer.release();video=clip.read_bytes()
    transcript=[]
    with TemporaryDirectory() as directory:
        settings=Settings(data_dir=Path(directory),worker_enabled=False,vision_enabled=False,qwen_enabled=False,
            auto_grid_enabled=options.grid)
        app=create_app(settings,catalog=catalog,verify=lambda token:Principal('synthetic-student','synthetic-lab','student'))
        with TestClient(app) as client:
            headers={'Authorization':'Bearer synthetic-test-token','Idempotency-Key':str(uuid4())}
            response=client.post('/api/v1/sessions',headers=headers,json={'experiment_id':'wire-hole-practice-v1' if options.wire_only else 'nand-not-example','description':'Synthetic circuit output check'})
            response.raise_for_status();record=response.json();sid=record['session_id'];url='/api/v1/sessions/'+sid
            transcript.append({'step':'session_created','response':record})
            response=client.post(url+'/image',headers=headers,data={'expected_session_version':record['session_version']},files={'image':('synthetic.mp4',video,'video/mp4')})
            response.raise_for_status()
            transcript.append({'step':'upload_accepted','response':response.json()})
            def poll(step):
                response=client.get(url,headers=headers);response.raise_for_status()
                record=response.json()
                if record['error']:raise RuntimeError(record['error'])
                transcript.append({'step':step,'response':record});return record
            def event(kind,**values):
                latest=client.get(url,headers=headers).json()
                response=client.post(url+'/events',headers=headers,json=dict(type=kind,event_id=str(uuid4()),expected_session_version=latest['session_version'],payload=values))
                response.raise_for_status();return response.json()
            app.state.workflow.run_one();record=poll('ml1_manual_observation')
            if options.grid:
                def binding():
                    latest=client.get(url,headers=headers).json()
                    return dict(candidate_revision=latest['candidate_revision'],
                        frame_id=latest['ml1']['media']['selected_frame_id'],image_sha256=latest['image']['sha256'],
                        board_fingerprint=latest['ml1']['grid_proposal']['board_fingerprint'])
                holes=record['ml1']['grid_proposal']['holes']
                request={**binding(),'expected_session_version':record['session_version'],'xy':holes['E20']}
                preview=client.post(url+'/grid/suggest',headers=headers,json=request)
                preview.raise_for_status()
                print('Provisional preview:',preview.json()['suggestion']['provisional_hole'])
                event('accept_grid',**binding(),left_top='A30',right_top='F1',
                    acknowledgement='reviewed_grid_alignment_and_printed_labels')
                poll('grid_labels_accepted')
                event('add_wire',**binding(),wire_id='Wdemo',a_xy=holes['E20'],b_xy=holes['F20'],
                    acknowledgement='reviewed_same_physical_wire')
                poll('wire_added')
                event('tap_endpoint',**binding(),target='Wdemo.b',xy=holes['F21'])
                poll('wire_endpoint_changed')
                event('remove_wire',candidate_revision=binding()['candidate_revision'],wire_id='Wdemo')
                record=poll('wire_removed')
            if options.wire_only:
                event('add_wire',**binding(),wire_id='Wobserved',a_xy=holes['E5'],b_xy=holes['F5'],
                    acknowledgement='reviewed_same_physical_wire')
                record=poll('wire_ready_for_review')
            else:
                candidate=json.loads((root/'examples/7400-not.candidate.json').read_text())
                record=event('replace_candidate',candidate_revision=record['candidate_revision'],candidate=candidate)
            event('confirm_candidate',candidate_revision=record['candidate_revision'],acknowledgement='reviewed_all_connections_and_board')
            app.state.workflow.run_one();record=poll('ml2_diagnosis_ml3_explanation')
            if not options.wire_only:
                event('measurements',candidate_revision=record['candidate_revision'],measurements=[{'input':0,'output':1},{'input':1,'output':0}],student_expectations=[])
                app.state.workflow.run_one();poll('measured_truth_table')
            event('close_session',resolved=True)
            app.state.workflow.run_one();poll('closed_memory_unavailable')
    output=root/'outputs/backend';output.mkdir(parents=True,exist_ok=True)
    target=output/('synthetic-wire-transcript.json' if options.wire_only else 'synthetic-grid-transcript.json' if options.grid else 'synthetic-transcript.json')
    target.write_text(json.dumps(transcript,indent=2)+'\n')
    print(target.relative_to(root))
    for row in transcript:
        r=row['response'];print(row['step']+': '+r['state'])

if __name__=='__main__':main()
