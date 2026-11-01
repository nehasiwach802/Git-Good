"""Durable session orchestration. All external operations run outside transactions."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import threading
from uuid import uuid4
from fastapi import HTTPException
from labvision.core import validate, confirm, endpoints, pending, CandidateError
from .store import encode


def error(status, code, message):
    raise HTTPException(status, detail={'code':code,'message':message})


def message(record, role, text):
    record['messages'].append({'id':str(uuid4()),'role':role,'text':text,'created_at':datetime.now(timezone.utc).isoformat()})
    record['messages'] = record['messages'][-100:]


def public(record):
    fields = ('session_id','version','state','experiment_id','experiment_version','description','candidate','board','image',
              'messages','actions','diagnostic','explanation','ml1','ml3','error','simulated','job_id')
    result = {k:deepcopy(record[k]) for k in fields}
    result['api_version'] = '1.0'
    result['candidate_revision'] = record['candidate']['revision'] if record['candidate'] else None
    result['memory_available'] = record['ml3'].get('memory_status') == 'available'
    return result


class Workflow:
    def __init__(self, store, catalog, integrations):
        self.store, self.catalog, self.integrations = store,catalog,integrations
        self.stop = threading.Event()

    def get(self, sid, principal):
        with self.store.connect() as db:
            record = self.store.get(db,sid,principal.actor_id)
        if not record: error(404,'session_not_found','Session not found')
        if record['lab_id']!=principal.lab_id:error(404,'session_not_found','Session not found')
        return record

    def accept_grid(self,sid,principal,*,expected_version,expected_revision,image_sha256,
                    left_top,right_top,acknowledgement):
        """Internal ML2 coordinator; not a new Android route/event.

        Only an authenticated, explicit student review may call this. The
        expensive asset loading happens before a short CAS write transaction.
        A future UI transport must retain these guards, not accept client maps.
        """
        from reasoning.media import MediaError
        from reasoning.grid import GridError
        record=self.get(sid,principal)
        if principal.role!='student':error(403,'student_required','Student role required')
        if type(expected_version) is not int or record['version']!=expected_version:
            error(409,'stale_session','Refresh session before accepting alignment')
        if record['state'] not in ('awaiting_review','awaiting_measurement','awaiting_check_result'):
            error(409,'grid_review_unavailable','Wait for extraction and an editable session')
        try:
            capture=self.integrations.capture(record).accept_grid(expected_revision,
                image_sha256=image_sha256,left_top=left_top,right_top=right_top,acknowledgement=acknowledgement)
        except (MediaError,GridError,CandidateError,KeyError,ValueError):
            error(422,'invalid_grid_review','Grid, labels, frame or candidate revision could not be verified')
        updated=capture.apply_to_record(record)
        # Label acceptance does not change component identity correspondence.
        updated['component_map']=record['component_map']
        updated['port_map']=record['port_map']
        updated['ml1']['media']=capture.snapshot()['media']
        updated['version']+=1
        message(updated,'assistant','Grid alignment and printed labels reviewed. Confirm circuit connections separately.')
        self.actions(updated)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current=self.store.get(db,sid,principal.actor_id)
            if not current or current['lab_id']!=principal.lab_id:error(404,'session_not_found','Session not found')
            if current['version']!=expected_version:error(409,'stale_session','Session changed during grid review')
            self.store.save(db,updated)
        return public(updated)

    def create(self, principal, experiment_id, version, description, data, receipt, request_key):
        if principal.role != 'student': error(403,'student_required','Student role required')
        choices = [x for (eid,v),x in self.catalog.items() if eid==experiment_id and (version is None or v==version)]
        if len(choices)!=1: error(422,'unknown_experiment','Choose a supported experiment ID and version')
        experiment = deepcopy(choices[0])
        digest = hashlib.sha256(encode([experiment_id,experiment['version'],description,receipt['sha256'] if receipt else None]).encode()).hexdigest()
        with self.store.transaction() as db:
            row = db.execute('SELECT record,request_hash FROM sessions WHERE owner=? AND request_key=?', (principal.actor_id,request_key)).fetchone()
            if row:
                if row['request_hash']!=digest: error(409,'idempotency_conflict','Upload key was reused with different data')
                existing=json.loads(row['record'])
                if existing['lab_id']!=principal.lab_id:error(409,'lab_changed','Use a new upload key for the current lab')
                return existing
            sid = str(uuid4())
            record = {'session_id':sid,'owner':principal.actor_id,'lab_id':principal.lab_id,'version':1,'state':'extracting' if receipt else 'awaiting_image',
                'experiment_id':experiment_id,'experiment_version':experiment['version'],'experiment':experiment,
                'description':description,'board':deepcopy(experiment['board']),'candidate':None,'image':receipt,
                'messages':[],'actions':[],'diagnostic':None,'explanation':None,'ml1':{'status':'queued'},'ml3':{'memory_status':'not_requested'},
                'error':None,'simulated':experiment.get('simulated',False),'job_id':None,
                'equipment_id':experiment.get('equipment_id','unassigned'),'channel':experiment.get('channel','unassigned'),
                'component_map':deepcopy(experiment.get('component_map',{})),'port_map':deepcopy(experiment.get('port_map',{})),
                'source_settings':{},'measurements':[],'student_expectations':[] if experiment['reference']['analysis']['engine']=='7400_as_not' else {},
                'checks_performed':[],'resolved':False}
            message(record,'user',description)
            if receipt:
                message(record,'assistant','Image received. Extracting observations; no wiring has been confirmed yet.')
                self.store.enqueue(db,record,'extract')
            else:
                record['ml1']={'status':'awaiting_image'}
                message(record,'assistant','Session created. Upload a circuit video to begin review.')
            self.actions(record)
            db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?)', (sid,principal.actor_id,request_key,digest,encode(record),data or b''))
            return record

    def attach_image(self,sid,principal,data,receipt,request_key,expected_version):
        digest=hashlib.sha256(encode([receipt['sha256'],expected_version]).encode()).hexdigest()
        with self.store.transaction() as db:
            record=self.store.get(db,sid,principal.actor_id)
            if not record or record['lab_id']!=principal.lab_id:error(404,'session_not_found','Session not found')
            if principal.role!='student':error(403,'student_required','Student role required')
            previous=db.execute('SELECT * FROM uploads WHERE session_id=? AND request_key=?',(sid,request_key)).fetchone()
            if previous:
                if previous['digest']!=digest:error(409,'idempotency_conflict','Upload key reused with different content or version')
                return json.loads(previous['response'])
            if record['version']!=expected_version:error(409,'stale_session','Refresh session before uploading')
            if record['state']!='awaiting_image':error(409,'image_already_attached','Image can only be attached to an awaiting_image session')
            record.update(image=receipt,state='extracting',ml1={'status':'queued'},version=record['version']+1)
            self.store.enqueue(db,record,'extract')
            self.actions(record)
            message(record,'assistant','Image received. Extracting observations; review is required before diagnosis.')
            db.execute('UPDATE sessions SET image=? WHERE id=?',(data,sid))
            self.store.save(db,record)
            response=public(record)
            db.execute('INSERT INTO uploads VALUES(?,?,?,?)',(sid,request_key,digest,encode(response)))
            return response

    def attach_video(self,sid,principal,staged,request_key,expected_version):
        digest=hashlib.sha256(encode(['video',staged.receipt['sha256'],expected_version]).encode()).hexdigest()
        with self.store.transaction() as db:
            record=self.store.get(db,sid,principal.actor_id)
            if not record or record['lab_id']!=principal.lab_id:error(404,'session_not_found','Session not found')
            if principal.role!='student':error(403,'student_required','Student role required')
            previous=db.execute('SELECT * FROM uploads WHERE session_id=? AND request_key=?',(sid,request_key)).fetchone()
            if previous:
                if previous['digest']!=digest:error(409,'idempotency_conflict','Upload key reused with different content or version')
                return json.loads(previous['response']),False
            if record['version']!=expected_version:error(409,'stale_session','Refresh session before uploading')
            if record['state']!='awaiting_image':error(409,'media_already_attached','A video is already attached or the session is closed')
            record.update(image=None,state='extracting',version=record['version']+1,
                ml1={'status':'queued','media':{'kind':'video','video':staged.receipt}})
            db.execute('INSERT INTO session_media VALUES(?,?,?)',(sid,staged.asset_id,encode(staged.receipt)))
            self.store.enqueue(db,record,'extract_video')
            self.actions(record)
            message(record,'assistant','Video received. Selecting a frame for circuit review; no connections are confirmed yet.')
            self.store.save(db,record)
            response=public(record)
            db.execute('INSERT INTO uploads VALUES(?,?,?,?)',(sid,request_key,digest,encode(response)))
            return response,True

    def actions(self, record):
        if record['state']=='awaiting_image':
            record['actions']=[{'type':'upload_image','accepted_content_types':['video/mp4']}]
        elif record['state']=='awaiting_review':
            record['actions']=[{'type':'review_candidate','candidate_revision':record['candidate']['revision'],
                               'pending':pending(record['candidate'],record['board']),
                               'reasoning_pending':record['diagnostic'].get('pending',[]) if record.get('diagnostic') else [],
                               'event_types':['correct_endpoint','replace_candidate','confirm_candidate','set_correspondence','source_settings']}]
            if record.get('ml1',{}).get('grid_proposal',{}).get('status')=='needs_orientation_review':
                record['actions'][0]['event_types']+=['accept_grid','reject_grid']
                if record['ml1'].get('media',{}).get('grid_review'):
                    record['actions'][0]['event_types']+=['tap_endpoint','add_wire']
            record['actions'][0]['event_types'].append('remove_wire')
        elif record['state']=='failed':
            record['actions']=[{'type':'retry_extraction','message':'Retry explicitly; previous provider request may have run.'}]
        elif record.get('diagnostic') and record['state'] not in ('completed','completing','closed'):
            record['actions']=[record['diagnostic']['next_check']]
        else: record['actions']=[]

    def grid_capture(self,record,binding,db=None):
        """Validate exact server-owned frame/profile binding before pixel use."""
        from labvision.geometry import board_fingerprint
        if not record.get('candidate') or record['candidate']['revision']!=binding.candidate_revision:
            error(409,'stale_candidate','Refresh the current candidate')
        media=record.get('ml1',{}).get('media',{})
        if (media.get('kind')!='video' or media.get('selected_frame_id')!=binding.frame_id or
            not record.get('image') or record['image']['sha256']!=binding.image_sha256 or
            board_fingerprint(record['board'])!=binding.board_fingerprint):
            error(409,'stale_grid_binding','Refresh the selected frame and board')
        return self.integrations.capture(record,db)

    @staticmethod
    def apply_grid_capture(record,capture):
        maps={k:deepcopy(record[k]) for k in ('component_map','port_map')}
        updated=capture.apply_to_record(record)
        updated.update(maps)
        updated['ml1']['media']=capture.snapshot()['media']
        record.clear();record.update(updated)

    def suggest_hole(self,sid,principal,request):
        """Read-only, version-bound preview. No event/session/candidate mutation."""
        with self.store.connect() as db:
            db.execute('BEGIN')
            record=self.store.get(db,sid,principal.actor_id)
            if not record or record['lab_id']!=principal.lab_id:error(404,'session_not_found','Session not found')
            if principal.role!='student':error(403,'student_required','Student role required')
            if record['version']!=request.expected_session_version:error(409,'stale_session','Refresh the current session')
            if record['state'] not in ('awaiting_review','awaiting_measurement','awaiting_check_result'):
                error(409,'session_not_editable','Wait for an editable session')
            try:
                capture=self.grid_capture(record,request,db)
                suggestion=capture.suggest_hole(request.candidate_revision,image_sha256=request.image_sha256,xy=request.xy)
            except ValueError:error(422,'invalid_grid_touch','Grid or native image coordinates are invalid')
            return {**{k:getattr(request,k) for k in ('candidate_revision','frame_id','image_sha256','board_fingerprint')},
                    'session_version':record['version'],'suggestion':suggestion}

    @staticmethod
    def snapped_endpoint(capture,xy):
        if not capture.media.get('grid_review'):error(422,'grid_acceptance_required','Accept grid alignment and printed labels first')
        suggestion=capture.suggest_hole(capture.candidate['revision'],image_sha256=capture.image['sha256'],xy=xy)
        if suggestion['hole'] is None:
            raise HTTPException(422,detail={'code':'ambiguous_tap','message':'Tap a clear insertion hole',
                'alternatives':suggestion['alternatives']})
        return suggestion

    def event(self, sid, principal, event):
        body = event.model_dump(mode='json')
        try: digest = hashlib.sha256(encode(body).encode()).hexdigest()
        except ValueError: error(422,'non_finite_value','Numeric values must be finite')
        with self.store.transaction() as db:
            record = self.store.get(db,sid,principal.actor_id)
            if not record: error(404,'session_not_found','Session not found')
            if record['lab_id']!=principal.lab_id:error(404,'session_not_found','Session not found')
            old = db.execute('SELECT * FROM events WHERE session_id=? AND event_id=?',(sid,str(event.event_id))).fetchone()
            if old:
                if old['digest']!=digest: error(409,'idempotency_conflict','Event ID reused with different data')
                return json.loads(old['response'])
            if principal.role != 'student': error(403,'student_required','Student role required')
            if record['version']!=event.expected_version: error(409,'stale_session','Refresh session before submitting changes')
            kind = event.type
            if record['state'] in ('extracting','diagnosing','completing'):
                error(409,'session_busy','Wait for processing before submitting an event')
            if record['state'] in ('completed','closed'): error(409,'session_completed','Closed sessions are immutable')
            candidate = record['candidate']
            if hasattr(event,'candidate_revision') and (not candidate or candidate['revision']!=event.candidate_revision):
                error(409,'stale_candidate','Candidate revision changed; review current connections')
            try:
                if kind in ('accept_grid','reject_grid','tap_endpoint','add_wire'):
                    from reasoning.media import reset_review
                    if record['state'] not in ('awaiting_review','awaiting_measurement','awaiting_check_result'):
                        error(409,'session_not_editable','Wait for an editable session')
                    capture=self.grid_capture(record,event,db)
                    if kind=='accept_grid':
                        capture=capture.accept_grid(event.candidate_revision,image_sha256=event.image_sha256,
                            left_top=event.left_top,right_top=event.right_top,acknowledgement=event.acknowledgement)
                    elif kind=='reject_grid':
                        capture.media.pop('grid_review',None)
                        capture.media['grid_rejected']=True
                        capture.candidate['revision']+=1
                        reset_review(capture.candidate)
                        capture.calibration=None
                    elif kind=='tap_endpoint':
                        point=self.snapped_endpoint(capture,event.xy)
                        matches=[p for name,p,_ in endpoints(capture.candidate) if name==event.target]
                        if len(matches)!=1:raise ValueError('Unknown endpoint')
                        matches[0].update(point,external_terminal=None)
                        capture.candidate['revision']+=1
                        reset_review(capture.candidate)
                        validate(capture.candidate,capture.board)
                    else:
                        a=self.snapped_endpoint(capture,event.a_xy)
                        b=self.snapped_endpoint(capture,event.b_xy)
                        capture.candidate['wires'].append({'id':event.wire_id,'a':a,'b':b,'pairing_reviewed':True})
                        capture.candidate['revision']+=1
                        reset_review(capture.candidate)
                        capture.candidate['wires'][-1]['pairing_reviewed']=True
                        validate(capture.candidate,capture.board)
                    self.apply_grid_capture(record,capture)
                    message(record,'assistant','Review updated. Confirm the current circuit separately before diagnosis.')
                elif kind=='remove_wire':
                    from reasoning.media import reset_review
                    updated=deepcopy(candidate)
                    matches=[w for w in updated['wires'] if w['id']==event.wire_id]
                    if len(matches)!=1:raise ValueError('Unknown wire')
                    updated['wires'].remove(matches[0]);updated['revision']+=1
                    reset_review(updated);validate(updated,record['board'])
                    record.update(candidate=updated,diagnostic=None,explanation=None,state='awaiting_review',
                        measurements=[],student_expectations=[] if isinstance(record.get('student_expectations'),list) else {},
                        checks_performed=[],source_settings={},resolved=False)
                    message(record,'assistant','Wire removed. Review the current circuit revision.')
                elif kind in ('correct_endpoint','replace_candidate'):
                    if kind=='replace_candidate':
                        updated=deepcopy(event.candidate)
                        updated.update(candidate_id=candidate['candidate_id'],revision=candidate['revision']+1,
                                       board_profile_id=record['board']['id'],image_sha256=record['image']['sha256'])
                    else:
                        if event.hole is not None and event.external_terminal is not None:
                            raise ValueError('Choose hole or external terminal, not both')
                        updated=deepcopy(candidate)
                        matches=[p for name,p,_ in endpoints(updated) if name==event.target]
                        if len(matches)!=1: raise ValueError('Unknown endpoint')
                        if event.external_terminal is not None: updated['schema_version']='0.2'
                        matches[0].update(hole=event.hole,external_terminal=event.external_terminal,alternatives=[],source='manual',reason='Student correction')
                        updated['revision']+=1
                    updated.update(reviewed_revision=None,board_confirmed=False)
                    for c in updated['components']:
                        c['identity_confirmed']=False
                        if c['part'] in ('resistor','capacitor'):c['value_confirmed']=False
                    for _,point,_ in endpoints(updated):point['confirmed']=False
                    validate(updated,record['board'])
                    record.update(candidate=updated,diagnostic=None,explanation=None,state='awaiting_review',
                        measurements=[],student_expectations=[] if isinstance(record.get('student_expectations'),list) else {},
                        checks_performed=[],source_settings={},resolved=False)
                    message(record,'assistant','Observations updated. Review the current revision before diagnosis.')
                elif kind=='confirm_candidate':
                    record['candidate']=confirm(candidate,record['board'],event.candidate_revision)
                    for wire in record['candidate']['wires']:wire['pairing_reviewed']=True
                    record.update(state='diagnosing',diagnostic=None,explanation=None)
                    self.store.enqueue(db,record,'diagnose')
                    message(record,'assistant','Current connections reviewed. Evaluating supported models and evidence.')
                elif kind=='set_correspondence':
                    reference=record['experiment']['reference']
                    source_ids={c['id'] for c in candidate['components']} if candidate else set()
                    target_ids={c['id'] for c in reference['circuit']['components']}
                    targets=[v for v in event.component_map.values() if v is not None]
                    if set(event.component_map)-source_ids or any(v not in target_ids for v in targets) or len(set(targets))!=len(targets):
                        raise ValueError('Invalid one-to-one component correspondence')
                    source_ports={p['id'] for p in candidate['ports']}
                    if set(event.port_map)-source_ports or any(v not in reference['ports'] for v in event.port_map.values()):
                        raise ValueError('Invalid port correspondence')
                    record.update(component_map=event.component_map,port_map=event.port_map,diagnostic=None,explanation=None)
                    if candidate['reviewed_revision']==candidate['revision']:
                        record['state']='diagnosing';self.store.enqueue(db,record,'diagnose')
                elif kind=='measurements':
                    self.validate_readings(record,event.measurements,event.student_expectations)
                    record.update(measurements=event.measurements,student_expectations=event.student_expectations,diagnostic=None,explanation=None)
                    if candidate['reviewed_revision']!=candidate['revision']:raise ValueError('Confirm current circuit first')
                    record['state']='diagnosing';self.store.enqueue(db,record,'diagnose')
                elif kind=='source_settings':
                    allowed={s['component_id'] for s in record['experiment'].get('source_ports',[])}
                    if set(event.sources)!=allowed or any(set(v)!={'dc','ac'} for v in event.sources.values()):raise ValueError('Provide dc/ac for each configured source')
                    record.update(source_settings=event.sources,diagnostic=None,explanation=None)
                    if candidate['reviewed_revision']==candidate['revision']:
                        record['state']='diagnosing';self.store.enqueue(db,record,'diagnose')
                elif kind=='message':
                    message(record,'user',event.text)
                    message(record,'assistant',record['explanation']['explanation'] if record.get('explanation') else 'Use the review controls to confirm connections. Measurements must be entered using their structured fields.')
                elif kind=='check_result':
                    if not record['diagnostic'] or event.check_id!=record['diagnostic']['next_check']['check_id']:raise ValueError('Check does not match current diagnosis')
                    record['checks_performed'].append(event.check_id)
                    message(record,'user',event.observation)
                    message(record,'assistant','Check result recorded as a student report. Submit readings or corrected connections to update the diagnosis.')
                elif kind in ('complete','close_session'):
                    evaluated=record['diagnostic'] and record['diagnostic']['status']=='evaluated'
                    if not evaluated:
                        if kind=='complete':raise ValueError('A reviewed, evaluated diagnosis is required')
                        record.update(state='closed',job_id=None)
                        message(record,'assistant','Session closed without an evaluated outcome; no diagnostic memory was written.')
                    else:
                        record.update(resolved=event.resolved,state='completing')
                        self.store.enqueue(db,record,'outcome')
                elif kind=='retry_extraction':
                    if record['state']!='failed':raise ValueError('Only failed processing can be retried')
                    if record.get('ml3',{}).get('outcome_status')=='needs_reconciliation':raise ValueError('Memory write requires operator reconciliation, not retry')
                    record.update(state='extracting',error=None,candidate=None,diagnostic=None,explanation=None)
                    source=db.execute('SELECT 1 FROM session_media WHERE session_id=?',(sid,)).fetchone()
                    self.store.enqueue(db,record,'extract_video' if source else 'extract')
            except (ValueError,KeyError,TypeError) as exc:
                error(422,'invalid_event',str(exc))
            record['version']+=1
            self.actions(record)
            self.store.save(db,record)
            response=public(record)
            db.execute('INSERT INTO events VALUES(?,?,?,?)',(sid,str(event.event_id),digest,encode(response)))
            return response

    @staticmethod
    def validate_readings(record, readings, expectations):
        from reasoning.generalized import validate_generalized
        from reasoning.adapters import adapt_request
        # Use the established validator on a synthetic unresolved observation;
        # validation is structural and never copies reference wiring to ML1.
        reference=record['experiment']['reference']
        from .integrations import Integrations
        engine=reference['analysis']['engine']
        if engine=='wire_connections':
            if readings or expectations:raise ValueError('Wire connections require no electrical readings or predictions')
            return
        if engine=='7400_as_not':
            for rows in (readings,expectations):
                if not isinstance(rows,list) or len(rows)>2:raise ValueError('Use at most two binary input/output rows')
                seen=set()
                for r in rows:
                    if not isinstance(r,dict) or set(r)!={'input','output'} or any(type(v) is not int or v not in (0,1) for v in r.values()):raise ValueError('Binary rows require integer input/output 0 or 1')
                    if r['input'] in seen:raise ValueError('Duplicate input condition')
                    seen.add(r['input'])
        else:
            from reasoning.validation import validate_request
            probes=[{**p,'positive':'x','negative':'0'} for p in reference['analysis'].get('probes',[])]
            circuit={'components':[{'id':'Vcheck','type':'V','pins':{'+':'x','-':'0'},'dc':0,'ac':1}]}
            validate_request({'schema_version':'1.0','experiment':{'circuit':circuit,'probes':probes},'student_circuit':circuit,
                              'measurements':readings,'student_expectations':expectations})

    def run_one(self):
        job=self.store.claim()
        if not job:return False
        with self.store.connect() as db:
            record=self.store.get(db,job['session_id'])
            row=db.execute('SELECT image FROM sessions WHERE id=?',(job['session_id'],)).fetchone()
            data=bytes(row['image']) if row else None
        try:
            if not record or record['job_id']!=job['id']:return True
            if job['kind']=='extract_video':
                from .video import video_path
                with self.store.connect() as db:
                    media=db.execute('SELECT * FROM session_media WHERE session_id=?',(record['session_id'],)).fetchone()
                if not media:raise ValueError('Video source is missing')
                capture=self.integrations.extract_video(video_path(self.store.directory,media['asset_id']),record['experiment'])
                record=capture.apply_to_record(record)
                record['component_map']=deepcopy(record['experiment'].get('component_map',{}))
                record['port_map']=deepcopy(record['experiment'].get('port_map',{}))
                selected=next(f for f in capture.frames if f['id']==capture.selected_frame_id)
                detection=deepcopy(selected['endpoint_detection'])
                if detection.get('status')=='unreviewed_region_proposals':
                    detection['videos']=[{'video_id':'selected-frame','frames':[{
                        'sha256':capture.image['sha256'],'image_size':[capture.image['width'],capture.image['height']],
                        'proposals':detection.pop('proposals',[])}]}]
                record['ml1']={'mode':capture.media['extraction_mode'],'status':capture.media['extraction_status'],
                    'media':capture.snapshot()['media'],'endpoint_detection':detection,
                    'message':'Review the selected video frame, parts and connections before diagnosis.'}
                if capture.grid_proposal is not None:
                    record['ml1']['grid_proposal']=capture.grid_proposal
                message(record,'assistant',record['ml1']['message'])
            elif job['kind']=='extract':
                extracted=self.integrations.extract(data,record['experiment'])
                record.update(candidate=extracted['candidate'],board=extracted['board'],state='awaiting_review',
                              ml1={k:v for k,v in extracted.items() if k not in ('candidate','board','netlist')},error=None)
                message(record,'assistant',extracted['message'])
            elif job['kind']=='diagnose':
                record['diagnostic']=self.integrations.diagnose(record)
                try:
                    record['explanation']=self.integrations.explain(record)
                    record['ml3']={'memory_status':record['explanation']['context']['memory_status'],'explanation_status':record['explanation']['status']}
                except Exception:
                    from mentor import explain_diagnostic
                    from .integrations import diagnostic_result
                    record['explanation']=explain_diagnostic(diagnostic_result(record),context={'personal':[],'approved_equipment':[],'memory_status':'unavailable'})
                    record['ml3']={'memory_status':'unavailable','explanation_status':'template_fallback'}
                diagnostic=record['diagnostic']
                record['state']='awaiting_review' if diagnostic['status']=='needs_confirmation' else 'awaiting_measurement' if diagnostic['next_check']['kind']=='record_approved_measurement' else 'awaiting_check_result'
                message(record,'assistant',record['explanation']['explanation'])
            else:
                try:status=self.integrations.outcome(record)
                except Exception:status={'status':'needs_reconciliation'}
                record['ml3']['outcome_status']=status['status']
                record['state']='completed'
                message(record,'assistant','Session saved. Memory outcome: '+status['status'])
            record.update(job_id=None,error=None)
        except Exception as exc:
            from reasoning.media import MediaError
            code=str(exc) if isinstance(exc,MediaError) and str(exc) in (
                'video_processing_timeout','video_dependencies_unavailable','invalid_video_or_limits',
                'video_processing_failed','video_source_hash_mismatch') else 'processing_failed'
            record.update(state='failed',job_id=None,error={'code':code,'message':'Processing failed. Current observations are preserved; retry explicitly or contact the instructor.'})
            message(record,'assistant',record['error']['message'])
        finally:
            with self.store.transaction() as db:
                current=self.store.get(db,job['session_id'])
                if record and current and current['job_id']==job['id']:
                    if job['kind']=='extract_video' and record['state']=='awaiting_review':
                        db.execute('DELETE FROM media_frames WHERE session_id=?',(record['session_id'],))
                        for frame in capture.frames:
                            db.execute('INSERT INTO media_frames VALUES(?,?,?,?)',(
                                record['session_id'],frame['id'],capture._bytes[frame['id']],encode(frame)))
                        db.execute('UPDATE sessions SET image=? WHERE id=?',(capture.image_bytes,record['session_id']))
                    record['version']=current['version']+1
                    self.actions(record);self.store.save(db,record)
                db.execute("UPDATE jobs SET state='done' WHERE id=?",(job['id'],))
        return True

    def loop(self):
        while not self.stop.is_set():
            try:
                if not self.run_one():self.stop.wait(.25)
            except Exception:
                self.stop.wait(1)
