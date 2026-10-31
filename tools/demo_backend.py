"""Offline synthetic HTTP transcript; no live vision, Qwen or product memory."""
from io import BytesIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from PIL import Image
from backend.app import create_app
from backend.config import Settings
from backend.catalog import load_catalog
from knowledge_lifecycle import Principal


def main():
    root=Path(__file__).resolve().parents[1]
    catalog=load_catalog(root/'backend/catalog.json')
    for item in catalog.values():item['workflow_approved']=True  # Synthetic fixture approval only.
    image=BytesIO();Image.new('RGB',(16,16),'white').save(image,format='PNG')
    transcript=[]
    with TemporaryDirectory() as directory:
        settings=Settings(data_dir=Path(directory),worker_enabled=False,vision_enabled=False,qwen_enabled=False)
        app=create_app(settings,catalog=catalog,verify=lambda token:Principal('synthetic-student','synthetic-lab','student'))
        with TestClient(app) as client:
            headers={'Authorization':'Bearer synthetic-test-token','Idempotency-Key':str(uuid4())}
            response=client.post('/api/v1/sessions',headers=headers,json={'experiment_id':'nand-not-example','description':'Synthetic circuit output check'})
            response.raise_for_status();record=response.json();sid=record['session_id'];url='/api/v1/sessions/'+sid
            transcript.append({'step':'session_created','response':record})
            response=client.post(url+'/image',headers=headers,data={'expected_session_version':record['session_version']},files={'image':('synthetic.png',image.getvalue(),'image/png')})
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
            app.state.workflow.run_one();poll('ml1_manual_observation')
            candidate=json.loads((root/'examples/7400-not.candidate.json').read_text())
            record=event('replace_candidate',candidate_revision=1,candidate=candidate)
            event('confirm_candidate',candidate_revision=record['candidate_revision'],acknowledgement='reviewed_all_connections_and_board')
            app.state.workflow.run_one();record=poll('ml2_diagnosis_ml3_explanation')
            event('measurements',candidate_revision=record['candidate_revision'],measurements=[{'input':0,'output':1},{'input':1,'output':0}],student_expectations=[])
            app.state.workflow.run_one();poll('measured_truth_table')
            event('close_session',resolved=True)
            app.state.workflow.run_one();poll('closed_memory_unavailable')
    output=root/'outputs/backend';output.mkdir(parents=True,exist_ok=True)
    target=output/'synthetic-transcript.json';target.write_text(json.dumps(transcript,indent=2)+'\n')
    print(target.relative_to(root))
    for row in transcript:
        r=row['response'];print(row['step']+': '+r['state'])

if __name__=='__main__':main()
