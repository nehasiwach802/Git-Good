"""ML2-only media boundary. ML3 still receives the existing diagnostic result."""
from copy import deepcopy
from dataclasses import dataclass,field
from hashlib import sha256
from io import BytesIO
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from PIL import Image
from labvision.core import validate,confirm,endpoints,CandidateError
from labvision.handoff import reasoning_input
from labvision.upload import extract_upload
from .api import diagnose_input,validate_input
from .adapters import adapt_request

MAX_VIDEO_BYTES=50*1024*1024
MAX_IMAGE_BYTES=5*1024*1024


class MediaError(ValueError):
    """Safe, stable error code; no decoder output or private filesystem paths."""


def require(condition,code):
    if not condition:raise MediaError(code)


def finite(value):
    try:return type(value) in (int,float) and math.isfinite(value)
    except OverflowError:return False


def detector_metadata(report,receipt):
    """Publish only bounded unreviewed overlays, not arbitrary provider fields."""
    if not isinstance(report,dict):return {'status':'unavailable'}
    status=report.get('status')
    if status in ('disabled','unavailable'):return {'status':status}
    try:
        frame=report['videos'][0]['frames'][0]
        require(frame['sha256']==receipt['sha256'] and frame['image_size']==[receipt['width'],receipt['height']],'detector_image_mismatch')
        require(isinstance(frame['proposals'],list) and len(frame['proposals'])<=100,'invalid_proposals')
        proposals=[]
        for i,p in enumerate(frame['proposals']):
            box=p['box'];score=p['score']
            require(isinstance(box,list) and len(box)==4 and all(finite(n) for n in box) and
                0<=box[0]<box[2]<=receipt['width'] and 0<=box[1]<box[3]<=receipt['height'] and
                finite(score) and 0<=score<=1,'invalid_proposal')
            proposals.append({'id':'P'+str(i+1),'box':list(box),'score':score,'hole':None,'confirmed':False,'reviewed':False})
        return {'status':'unreviewed_region_proposals','real_accuracy_established':False,'proposals':proposals}
    except (KeyError,TypeError,IndexError,MediaError):return {'status':'unavailable'}


def image_receipt(data):
    require(isinstance(data,bytes) and 0<len(data)<=MAX_IMAGE_BYTES,'invalid_image_size')
    try:
        with Image.open(BytesIO(data)) as picture:
            kind={'JPEG':'image/jpeg','PNG':'image/png'}.get(picture.format)
            require(kind is not None and picture.width*picture.height<=20_000_000,'invalid_image_format_or_pixels')
            width,height=picture.size;picture.verify()
    except (OSError,ValueError,Image.DecompressionBombError) as exc:
        if isinstance(exc,MediaError):raise
        raise MediaError('invalid_image') from None
    return dict(sha256=sha256(data).hexdigest(),size_bytes=len(data),content_type=kind,width=width,height=height)


def reset_review(candidate):
    candidate['reviewed_revision']=None;candidate['board_confirmed']=False
    for part in candidate['components']:
        part['identity_confirmed']=False
        if 'value_confirmed' in part:part['value_confirmed']=False
    for _,point,_ in endpoints(candidate):point['confirmed']=False
    for wire in candidate['wires']:
        if 'pairing_reviewed' in wire:wire['pairing_reviewed']=False


@dataclass
class Capture:
    board:dict
    candidate:dict
    selected_frame_id:str
    frames:list
    media:dict
    _bytes:dict=field(repr=False)
    calibration:dict|None=None

    @property
    def image(self):return deepcopy(next(f for f in self.frames if f['id']==self.selected_frame_id)['image'])

    @property
    def image_bytes(self):return self._bytes[self.selected_frame_id]

    def snapshot(self):
        """JSON-safe metadata for the existing backend to persist, not for ML3."""
        return deepcopy(dict(board=self.board,candidate=self.candidate,image=self.image,
            media={**self.media,'selected_frame_id':self.selected_frame_id,'frames':self.frames},
            calibration=self.calibration))

    def persist_assets(self,directory):
        """Immutable JPEG/PNG assets; caller owns authorization and retention.

        Returns opaque content hashes, never public paths. Backend must resolve
        asset IDs behind its existing authenticated session boundary.
        """
        root=Path(directory);root.mkdir(parents=True,exist_ok=True)
        for frame in self.frames:
            data=self._bytes[frame['id']];digest=frame['image']['sha256']
            require(sha256(data).hexdigest()==digest,'asset_hash_mismatch')
            target=root/digest
            try:
                with target.open('xb') as stream:stream.write(data)
            except FileExistsError:
                require(sha256(target.read_bytes()).hexdigest()==digest,'stored_asset_hash_mismatch')
        return [dict(frame_id=f['id'],asset_id=f['image']['sha256']) for f in self.frames]

    def apply_to_record(self,record):
        """Worker-side update for the existing authoritative backend record.

        Caller must perform ownership/version/job checks and persist atomically.
        No callbacks, external writes or ML3 calls happen in this function.
        """
        require(isinstance(record,dict),'invalid_session_record')
        previous=record.get('candidate')
        if previous and previous.get('image_sha256')!=self.image['sha256']:
            require(self.candidate['revision']>previous['revision'],'stale_capture_revision')
        updated=deepcopy(record)
        updated.update(candidate=deepcopy(self.candidate),board=deepcopy(self.board),image=self.image,
            media=self.snapshot()['media'],calibration=deepcopy(self.calibration),
            state='awaiting_review',diagnostic=None,explanation=None,error=None,
            measurements=[],checks_performed=[],source_settings={},resolved=False)
        if 'student_expectations' in updated:
            updated['student_expectations']=[] if isinstance(updated['student_expectations'],list) else {}
        if 'component_map' in updated:updated['component_map']={}
        if 'port_map' in updated:updated['port_map']={}
        return updated

    def select_frame(self,frame_id,*,known_parts=None,try_vision=False):
        require(frame_id in self._bytes,'unknown_frame')
        if frame_id==self.selected_frame_id:return deepcopy(self)
        result=extract_upload(self._bytes[frame_id],self.board,known_parts=known_parts or
            [p['part'] for p in self.candidate['components']],try_vision=try_vision)
        require(result['candidate'].get('image_sha256')==sha256(self._bytes[frame_id]).hexdigest(),'candidate_image_mismatch')
        updated=deepcopy(self)
        updated.selected_frame_id=frame_id
        updated.candidate=deepcopy(result['candidate'])
        updated.candidate.update(candidate_id=self.candidate['candidate_id'],revision=self.candidate['revision']+1)
        reset_review(updated.candidate)
        updated.calibration=None
        validate(updated.candidate,updated.board)
        return updated

    def confirm(self,expected_revision,*,acknowledgement):
        require(acknowledgement=='reviewed_all_connections_and_board','explicit_review_required')
        self.candidate=confirm(self.candidate,self.board,expected_revision)
        return self

    def request(self,reference,component_map,*,model_settings=None,**context):
        """Backend-owned references/settings; no reference goes to extraction."""
        validate(self.candidate,self.board)
        require(image_receipt(self.image_bytes)==self.image,'frame_receipt_mismatch')
        require(self.candidate.get('image_sha256')==self.image['sha256'],'candidate_image_mismatch')
        request={'schema_version':'2.0','reference':deepcopy(reference),
            'component_map':deepcopy(component_map),'input':reasoning_input(self.candidate,self.board),**deepcopy(context)}
        require(set(context)<= {'safety_profile','measurements','student_expectations','problem_description','equipment_evidence','port_map'},'unknown_request_context')
        request=adapt_request(request)
        source=request['observation'].setdefault('source',{})
        source['image_sha256']=self.image['sha256']
        source['media_binding']={'kind':self.media['kind'],'frame_id':self.selected_frame_id,
            'image_sha256':self.image['sha256'],'video_sha256':self.media.get('video',{}).get('sha256')}
        if model_settings:
            parts={c['id']:c for c in request['observation']['components']}
            refs={c['id']:c for c in reference['circuit']['components']}
            require(isinstance(model_settings,dict),'invalid_model_settings')
            for cid,settings in model_settings.items():
                require(cid in parts and parts[cid]['model']=='OPAMP' and isinstance(settings,dict) and set(settings)=={'gain'},'invalid_model_settings')
                gain=settings['gain'];target=refs.get(component_map.get(cid),{})
                require(finite(gain) and gain>0 and
                    target.get('type')=='OPAMP' and target.get('gain')==gain,'inconsistent_ideal_model')
                parts[cid]['properties']={'gain':gain};parts[cid]['properties_confirmed']=True
            source['ideal_model_assumptions']=deepcopy(model_settings)
        validate_input(request)
        return request

    def diagnose(self,reference,component_map,*,simulator=None,**kwargs):
        request=self.request(reference,component_map,**kwargs)
        result=diagnose_input(request) if simulator is None else diagnose_input(request,simulator)
        if request['observation']['source'].get('ideal_model_assumptions'):
            result['limitations'].append('Op-amp gain is an explicitly configured ideal-model assumption, not a measured component property.')
        # No media/candidate/assets/raw bytes are added to the ML3 result contract.
        return result


def normalize_video(result,board):
    """Validate an actual ML1 Python result and split assets from metadata."""
    require(isinstance(result,dict) and result.get('schema_version')=='ml1-video-1','invalid_video_result')
    frames=result.get('frames');video=result.get('video')
    require(isinstance(frames,list) and 1<=len(frames)<=6 and isinstance(video,dict),'invalid_video_frames')
    require(re.fullmatch('[0-9a-f]{64}',str(video.get('sha256',''))) is not None,'invalid_video_hash')
    require(type(video.get('size_bytes')) is int and 0<video['size_bytes']<=MAX_VIDEO_BYTES,'invalid_video_size')
    for key in ('fps','duration_s'):
        require(finite(video.get(key)) and video[key]>0,'invalid_video_metadata')
    require(video['duration_s']<=60 and type(video.get('frame_count')) is int and video['frame_count']>0,'invalid_video_metadata')
    blobs={};metadata=[]
    for frame in frames:
        require(isinstance(frame,dict),'invalid_frame')
        fid=frame.get('id')
        require(isinstance(fid,str) and re.fullmatch(r'F[1-6]',fid) is not None and fid not in blobs,'invalid_frame_id')
        data=frame.get('jpeg_bytes');receipt=image_receipt(data)
        require(receipt['content_type']=='image/jpeg','frame_must_be_jpeg')
        require(max(receipt['width'],receipt['height'])<=2000,'frame_pixels_exceed_limit')
        require(all(frame.get(k)==receipt[k] for k in ('sha256','size_bytes','content_type','width','height')),'frame_receipt_mismatch')
        require(type(frame.get('frame_index')) is int and 0<=frame['frame_index']<video['frame_count'],'invalid_frame_index')
        for key in ('timestamp_s','sharpness'):
            require(finite(frame.get(key)) and frame[key]>=0,'invalid_frame_metadata')
        blobs[fid]=data
        metadata.append({'id':fid,'image':receipt,'frame_index':frame['frame_index'],
            'timestamp_s':frame['timestamp_s'],'timestamp_source':frame.get('timestamp_source'),
            'sharpness':frame['sharpness'],'asset_id':receipt['sha256'],
            'endpoint_detection':detector_metadata(frame.get('endpoint_detection'),receipt)})
    selected=result.get('selected_frame_id');ml1=result.get('ml1')
    require(isinstance(selected,str) and selected in blobs and isinstance(ml1,dict),'invalid_selected_frame')
    receipt=next(f['image'] for f in metadata if f['id']==selected)
    require(isinstance(ml1.get('image'),dict) and all(ml1['image'].get(k)==v for k,v in receipt.items()),'selected_image_mismatch')
    candidate=deepcopy(ml1.get('candidate'))
    validate(candidate,board)
    require(candidate.get('image_sha256')==receipt['sha256'],'candidate_image_mismatch')
    reset_review(candidate)
    return Capture(deepcopy(board),candidate,selected,metadata,
        {'kind':'video','video':{k:video[k] for k in ('sha256','size_bytes','duration_s','fps','frame_count')},
         'selection':result.get('selection'),'calibration_required':True,
         'extraction_mode':ml1.get('mode','manual'),'extraction_status':ml1.get('status','manual_entry_required')},blobs)


def process_image(data,board,*,known_parts=None,try_vision=False):
    """Image input uses the same ML1 extractor and the same downstream request."""
    receipt=image_receipt(data)
    result=extract_upload(data,board,known_parts=known_parts,try_vision=try_vision)
    candidate=deepcopy(result['candidate'])
    require(candidate.get('image_sha256')==receipt['sha256'],'candidate_image_mismatch')
    reset_review(candidate)
    frames=[{'id':'I1','image':receipt,'asset_id':receipt['sha256'],
             'endpoint_detection':detector_metadata(result.get('endpoint_detection'),receipt)}]
    return Capture(deepcopy(board),candidate,'I1',frames,{'kind':'image','calibration_required':True},{'I1':data})


def restore_capture(snapshot,read_asset):
    """Restore trusted backend state using an authorized opaque asset reader.

    Do not accept a snapshot or arbitrary asset reader from a mobile request.
    This is for the existing backend's authoritative session/storage layer.
    """
    require(isinstance(snapshot,dict) and callable(read_asset),'invalid_capture_state')
    media=snapshot.get('media',{});frames=media.get('frames')
    require(isinstance(frames,list) and 1<=len(frames)<=6,'invalid_capture_state')
    blobs={}
    for frame in frames:
        require(isinstance(frame,dict) and isinstance(frame.get('image'),dict),'invalid_capture_state')
        fid=frame.get('id');digest=frame.get('asset_id')
        require(isinstance(fid,str) and re.fullmatch(r'(?:F[1-6]|I1)',fid) is not None and fid not in blobs,'invalid_frame_id')
        require(isinstance(digest,str) and re.fullmatch('[0-9a-f]{64}',digest) is not None,'invalid_asset_id')
        data=read_asset(digest)
        require(image_receipt(data)==frame['image'] and sha256(data).hexdigest()==digest,'stored_asset_hash_mismatch')
        blobs[fid]=data
    selected=media.get('selected_frame_id')
    require(isinstance(selected,str) and selected in blobs,'invalid_selected_frame')
    capture=Capture(deepcopy(snapshot['board']),deepcopy(snapshot['candidate']),selected,
        deepcopy(frames),{k:deepcopy(v) for k,v in media.items() if k not in ('frames','selected_frame_id')},blobs,deepcopy(snapshot.get('calibration')))
    validate(capture.candidate,capture.board)
    require(capture.candidate.get('image_sha256')==capture.image['sha256'] and snapshot.get('image')==capture.image,'candidate_image_mismatch')
    return capture


def process_video(path,board,*,known_parts=None,try_vision=False,deadline_s=60):
    """Run ML1 in a killable worker. No decoder executes in the caller/event loop."""
    path=Path(path).resolve()
    require(path.is_file() and 0<path.stat().st_size<=MAX_VIDEO_BYTES,'invalid_video_file_or_size')
    require(finite(deadline_s) and 0<deadline_s<=300,'invalid_deadline')
    require(type(try_vision) is bool,'invalid_vision_flag')
    with tempfile.TemporaryDirectory(prefix='ml2-video-') as directory:
        staged=Path(directory)/'input.video';digest=sha256();size=0
        with path.open('rb') as source,staged.open('wb') as target:
            for block in iter(lambda:source.read(1024*1024),b''):
                size+=len(block);require(size<=MAX_VIDEO_BYTES,'invalid_video_file_or_size')
                target.write(block);digest.update(block)
        require(size>0,'invalid_video_file_or_size')
        request=dict(path=str(staged),board=board,known_parts=known_parts,try_vision=try_vision,output=directory)
        try:
            child=subprocess.run([sys.executable,'-m','reasoning.media_worker'],input=json.dumps(request),
                text=True,capture_output=True,timeout=deadline_s)
        except subprocess.TimeoutExpired:raise MediaError('video_processing_timeout') from None
        require(child.returncode!=3,'video_dependencies_unavailable')
        require(child.returncode!=2,'invalid_video_or_limits')
        require(child.returncode==0,'video_processing_failed')
        record=Path(directory)/'result.json'
        require(record.is_file(),'missing_video_result')
        result=json.loads(record.read_text())
        require(result.get('video',{}).get('sha256')==digest.hexdigest(),'video_source_hash_mismatch')
        for frame in result.get('frames',[]):
            require(re.fullmatch(r'F[1-6]',str(frame.get('id',''))) is not None,'invalid_frame_id')
            frame['jpeg_bytes']=(Path(directory)/(frame['id']+'.jpg')).read_bytes()
        return normalize_video(result,board)
