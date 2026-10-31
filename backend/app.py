"""Authenticated Android API and durable ML1 -> ML2 -> ML3 workflow."""
from contextlib import asynccontextmanager
from hashlib import sha256
from io import BytesIO
from threading import Thread
from typing import Annotated
from uuid import UUID
import warnings
from fastapi import FastAPI, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from PIL import Image, UnidentifiedImageError
from .auth import firebase_principal
from .catalog import load_catalog
from .config import Settings
from .integrations import Integrations
from .models import SessionEvent, SessionResponse
from .store import Store
from .workflow import Workflow, public
from .smoke import MAX_IMAGE_BYTES, MAX_PIXELS, upload as smoke_upload
from .limits import BodyLimit


def validate_image(data, content_type):
    if len(data)>MAX_IMAGE_BYTES: raise HTTPException(413,'Image exceeds 5 MiB')
    if content_type not in ('image/png','image/jpeg'): raise HTTPException(415,'JPEG or PNG required')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as picture:
                if {'PNG':'image/png','JPEG':'image/jpeg'}.get(picture.format)!=content_type:
                    raise HTTPException(415,'Image content type mismatch')
                width,height=picture.size
                if width*height>MAX_PIXELS: raise HTTPException(413,'Image exceeds 20 megapixels')
                picture.verify()
    except (UnidentifiedImageError,OSError,ValueError,SyntaxError,Image.DecompressionBombWarning,Image.DecompressionBombError):
        raise HTTPException(415,'Invalid image') from None
    return {'content_type':content_type,'size_bytes':len(data),'sha256':sha256(data).hexdigest(),'width':width,'height':height}


def create_app(settings=None, *, catalog=None, integrations=None, verify=None):
    settings=settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        store=Store(settings.data_dir)
        store.recover()
        workflow=Workflow(store,catalog if catalog is not None else load_catalog(settings.catalog_path),integrations or Integrations(settings))
        app.state.workflow=workflow
        worker=Thread(target=workflow.loop,daemon=True,name='session-worker') if settings.worker_enabled else None
        if worker:worker.start()
        try:yield
        finally:
            workflow.stop.set()
            if worker:await run_in_threadpool(worker.join,35)

    app=FastAPI(title='Git-Good circuit mentor API',version='1.0.0',lifespan=lifespan)
    app.add_middleware(BodyLimit)

    @app.exception_handler(RequestValidationError)
    async def invalid(request,exc):
        return JSONResponse(status_code=422,content={'error':'invalid_request','fields':['.'.join(map(str,e['loc'])) for e in exc.errors()]})

    def principal(authorization: Annotated[str | None,Header()]=None):
        if not authorization or not authorization.startswith('Bearer '):raise HTTPException(401,'Firebase bearer token required')
        token=authorization[7:]
        return verify(token) if verify else firebase_principal(token,settings.firebase_project)

    Auth=Annotated[object,Depends(principal)]

    @app.get('/health')
    def health():return {'status':'ok','mode':'integrated','api_version':'1.0'}

    @app.get('/ready')
    def ready():
        from .preflight import check
        report=check(settings,authenticated=verify is not None,catalog=app.state.workflow.catalog)
        with app.state.workflow.store.connect() as db:db.execute('SELECT 1').fetchone()
        return JSONResponse(report,status_code=200 if report['status']=='ready' else 503)

    app.add_api_route('/api/sessions',smoke_upload,methods=['POST'],deprecated=True)

    @app.get('/api/v1/experiments')
    def experiments(user:Auth):
        records=[]
        for item in app.state.workflow.catalog.values():
            record={k:item.get(k) for k in ('experiment_id','version','name','workflow_approved','simulated')}
            record['review_contract']={
                'reported_parts':item['reported_parts'],
                'reference_components':[{'id':c['id'],'model':c['type']} for c in item['reference']['circuit']['components']],
                'reference_ports':list(item['reference']['ports']),
                'analysis':item['reference']['analysis'],
                'source_ports':item.get('source_ports',[])}
            records.append(record)
        return {'experiments':records}

    @app.get('/api/v1/capabilities')
    def capabilities(user:Auth):
        from reasoning.registry import capabilities as supported
        from reasoning.spice import find_ngspice
        return {'reasoning':supported(),'ngspice_available':bool(find_ngspice()),'probabilities_calibrated':False}

    @app.post('/api/v1/sessions',response_model=SessionResponse,status_code=202)
    async def create(user:Auth, experiment_id:Annotated[str,Form(min_length=1,max_length=100)],
                     description:Annotated[str,Form(min_length=1,max_length=2000)],
                     image:Annotated[UploadFile,File()],
                     idempotency_key:Annotated[UUID,Header()],
                     experiment_version:Annotated[str | None,Form(max_length=100)]=None):
        try:
            if not description.strip():raise HTTPException(422,'Description cannot be blank')
            data=await image.read(MAX_IMAGE_BYTES+1)
            receipt=await run_in_threadpool(validate_image,data,image.content_type)
            record=await run_in_threadpool(app.state.workflow.create,user,experiment_id,experiment_version,description.strip(),data,receipt,str(idempotency_key))
            return public(record)
        finally:await image.close()

    @app.get('/api/v1/sessions/{session_id}',response_model=SessionResponse)
    def get(session_id:UUID,user:Auth):return public(app.state.workflow.get(str(session_id),user))

    @app.post('/api/v1/sessions/{session_id}/events',response_model=SessionResponse)
    def event(session_id:UUID,event:SessionEvent,user:Auth):return app.state.workflow.event(str(session_id),user,event)

    @app.get('/api/v1/sessions/{session_id}/image')
    def image(session_id:UUID,user:Auth):
        workflow=app.state.workflow
        record=workflow.get(str(session_id),user)
        with workflow.store.connect() as db:data=db.execute('SELECT image FROM sessions WHERE id=?',(str(session_id),)).fetchone()['image']
        return Response(bytes(data),media_type=record['image']['content_type'],headers={'Cache-Control':'private, no-store'})

    @app.delete('/api/v1/sessions/{session_id}',status_code=204)
    def delete(session_id:UUID,user:Auth):
        workflow=app.state.workflow
        with workflow.store.transaction() as db:
            record=workflow.store.get(db,str(session_id),user.actor_id)
            if not record or record['lab_id']!=user.lab_id:raise HTTPException(404,'Session not found')
            if record['state'] in ('extracting','diagnosing','completing'):raise HTTPException(409,'Wait for processing before deleting')
            for table in ('events','jobs'):db.execute('DELETE FROM '+table+' WHERE session_id=?',(str(session_id),))
            db.execute('DELETE FROM sessions WHERE id=?',(str(session_id),))
        return Response(status_code=204)

    from ml3_http import create_ml3_app
    from .integrations import diagnostic_result, session_outcome

    def authorize(user,sid,equipment,channel,simulated):
        record=app.state.workflow.get(sid,user)
        return (user.lab_id==record['lab_id'] and equipment==record['equipment_id'] and
                channel==record['channel'] and simulated==record['simulated'])

    def resolve_diagnostic(user,sid):
        record=app.state.workflow.get(sid,user)
        if not record['diagnostic']:raise ValueError('Diagnosis is not ready')
        return diagnostic_result(record)

    def resolve_outcome(user,sid):
        record=app.state.workflow.get(sid,user)
        if record['state']!='completed':raise ValueError('Complete the session using an event first')
        return session_outcome(record)

    app.mount('/api/v1/ml3',create_ml3_app(
        service_factory=lambda:app.state.workflow.integrations.service(),
        resolve_principal=lambda request:principal(request.headers.get('authorization')),
        authorize_session=authorize,resolve_diagnostic=resolve_diagnostic,resolve_outcome=resolve_outcome))
    return app


app=create_app()
