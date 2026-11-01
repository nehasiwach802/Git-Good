"""Actual ML1/ML2/ML3 interfaces; no product calls on import or in tests."""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import json
import os
from lab_memory import MekoMemory, MemoryServiceError, SessionOutcome
from knowledge_lifecycle import KnowledgeStore, Principal
from outcome_writer import OutcomeWriter
from ml3_service import ML3Service
from mentor import DiagnosticResult, EvidenceItem, explain_diagnostic
from meko_transport import MekoTransport
from qwen_transport import QwenTransport
from labvision.upload import extract_upload
from labvision.handoff import reasoning_input
from reasoning.api import diagnose_input, validate_input
from reasoning.observations import validate_reference
from reasoning.media import process_video,restore_capture
from reasoning.ml3_bridge import explain as explain_ml2_result


class UnavailableMemory:
    def __getattr__(self, name):
        def unavailable(*args, **kwargs):
            raise MemoryServiceError('Personal memory is not configured for this account')
        return unavailable


def diagnostic_result(record):
    diagnostic = record['diagnostic']
    support = {k: diagnostic['hypotheses'][k]['support'] for k in ('wiring','concept','apparatus')}
    supported = [k for k,v in support.items() if v == 'supported']
    evidence = {}
    for item in diagnostic.get('findings', []):
        evidence[item['id']] = EvidenceItem(item['id'], json.dumps(item, ensure_ascii=True, allow_nan=False),
                                           'ml2', 'unverified' if item.get('certainty') in ('possible','unresolved') else 'ml2_computed')
    probabilities=diagnostic.get('cause_probabilities')
    return DiagnosticResult(record['session_id'], diagnostic.get('suspected_cause',supported[0] if len(supported)==1 else 'undetermined'),
                            probabilities, tuple(evidence.values()), tuple(diagnostic.get('limitations', [])),
                            diagnostic['next_check']['reason'], hypothesis_support=support)


def session_outcome(record):
    readings = []
    for reading in record['measurements']:
        if 'probe_id' in reading:
            readings.append({'node':reading['probe_id'],'value':reading['value'],'unit':reading['unit']})
        else:
            readings.append({'node':'logic_input_'+str(reading['input']),'value':reading['output'],'unit':'logic'})
    return SessionOutcome(record['session_id'], record['experiment_id'], record['equipment_id'], record['channel'],
        record['candidate'] is not None and record['candidate']['reviewed_revision']==record['candidate']['revision'],
        tuple(readings), record['diagnostic'], tuple(record['checks_performed']), record['resolved'], record['simulated'])


class Integrations:
    def __init__(self, settings):
        self.settings = settings

    def extract(self, data, experiment):
        return extract_upload(data, experiment['board'], known_parts=experiment['reported_parts'],
                              try_vision=self.settings.vision_enabled, timeout=20)

    def extract_video(self,path,experiment):
        return process_video(path,experiment['board'],known_parts=experiment['reported_parts'],
            try_vision=self.settings.vision_enabled,deadline_s=self.settings.video_deadline_s,
            auto_grid=self.settings.auto_grid_enabled)

    def capture(self,record,db=None):
        from .store import Store
        if db is None:
            store=Store(self.settings.data_dir)
            with store.connect() as connection:
                rows=connection.execute('SELECT image,metadata FROM media_frames WHERE session_id=?',(record['session_id'],)).fetchall()
        else:
            rows=db.execute('SELECT image,metadata FROM media_frames WHERE session_id=?',(record['session_id'],)).fetchall()
        assets={json.loads(row['metadata'])['asset_id']:bytes(row['image']) for row in rows}
        def read_asset(digest):return assets[digest]
        return restore_capture({'board':record['board'],'candidate':record['candidate'],
            'image':record['image'],'media':record['ml1']['media'],'calibration':record.get('calibration')},read_asset)

    def reasoning_request(self, record):
        experiment = record['experiment']
        request = {'schema_version':'2.0', 'reference':experiment['reference'],
            'input':reasoning_input(record['candidate'], record['board']),
            'component_map':record['component_map'], 'port_map':record['port_map'],
            'problem_description':record['description'], 'measurements':record['measurements'],
            'student_expectations':record['student_expectations'],
            'safety_profile':'instructor_approved_low_voltage' if experiment.get('workflow_approved') else 'unapproved'}
        if record.get('ml1',{}).get('media',{}).get('kind')=='video':
            capture=self.capture(record)
            request=capture.request(experiment['reference'],record['component_map'],
                model_settings=experiment.get('model_settings'),port_map=record['port_map'],
                problem_description=record['description'],measurements=record['measurements'],
                student_expectations=record['student_expectations'],safety_profile=request['safety_profile'])
        # External sources are reported by the student, never copied from the
        # desired reference. Confirmed port connectivity supplies their terminals.
        if experiment.get('source_ports'):
            from reasoning.adapters import adapt_request
            request = adapt_request(request)
            obs = request['observation']
            for source in experiment['source_ports']:
                settings = record['source_settings'].get(source['component_id'])
                ports = obs['ports']
                positive = ports.get(source['positive_port'], {'net':None,'confirmed':False})
                negative = ports.get(source['negative_port'], {'net':None,'confirmed':False})
                sid = source['component_id']
                obs['components'].append({'id':sid,'model':'V','identity_confirmed':bool(settings),
                    'properties_confirmed':bool(settings), 'properties':settings or {'dc':None,'ac':None},
                    'pins':{'+':positive,'-':negative}})
                request['component_map'][sid] = sid
        return request

    def diagnose(self, record):
        return diagnose_input(self.reasoning_request(record))

    @contextmanager
    def service(self):
        memory = UnavailableMemory()
        if self.settings.memory_scopes_file:
            scopes = json.loads(Path(self.settings.memory_scopes_file).read_text())
            memory = MekoMemory(MekoTransport.from_env(), scopes,
                                os.getenv('BUILD_DATAPACK_ID','c3ea833a-a52a-49e5-9a78-23fc4276833e'))
        knowledge = KnowledgeStore(self.settings.data_dir / 'knowledge.sqlite3')
        writer = OutcomeWriter(self.settings.data_dir / 'outcomes.sqlite3', memory)
        try:
            generate = QwenTransport.from_env() if self.settings.qwen_enabled and os.getenv('QWEN_MODEL') else None
            yield ML3Service(memory=memory, knowledge=knowledge, outcome_writer=writer, generate=generate)
        finally:
            writer.close()
            knowledge.close()

    def explain(self, record):
        principal = Principal(record['owner'], record['lab_id'], 'student')
        with self.service() as service:
            return explain_ml2_result(record['diagnostic'],record['session_id'],
                diagnostic_type=DiagnosticResult,evidence_type=EvidenceItem,
                explain_callback=lambda result:service.explain_result(principal,result,query=record['description'],
                    equipment_id=record['equipment_id'],channel=record['channel'],simulated=record['simulated'],now=datetime.now(timezone.utc)))

    def outcome(self, record):
        with self.service() as service:
            return service.store_outcome(Principal(record['owner'],record['lab_id'],'student'),session_outcome(record))
