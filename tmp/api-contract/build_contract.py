import json
from pathlib import Path
OUT=Path('docs/api-v1')
def ref(n): return {'$ref':'#/components/schemas/'+n}
def obj(props,required=None): return {'type':'object','additionalProperties':False,'properties':props,'required':list(props) if required is None else required}
def string(**kw):return {'type':'string',**kw}
def enum(*v):return string(enum=list(v))
def arr(item,**kw):return {'type':'array','items':item,**kw}
def nullable(schema):return {'oneOf':[schema,{'type':'null'}]}
UUID=string(format='uuid');DT=string(format='date-time');ID=string(minLength=1,maxLength=100,pattern='^[A-Za-z0-9_-]+$');VER={'type':'integer','minimum':1};TEXT=string(minLength=1,maxLength=4000,pattern='\\S')
S={}
S['Experiment']=obj({'id':ID,'name':string(minLength=1),'version':string(minLength=1),'description':string(),'support_status':enum('available','coming_soon','unavailable'),'support_reason':nullable(string()),'capabilities':obj({'image_analysis':{'type':'boolean'},'follow_up_images':{'type':'boolean'},'measurements':{'type':'boolean'},'instructor_help':{'type':'boolean'}})})
S['ExperimentList']=obj({'experiments':arr(ref('Experiment'))})
S['CreateSession']=obj({'experiment_id':ID,'experiment_version':string(minLength=1)})
S['ImageReceipt']=obj({'image_id':UUID,'content_type':enum('image/jpeg','image/png'),'size_bytes':{'type':'integer','minimum':1,'maximum':5242880},'width':{'type':'integer','minimum':1},'height':{'type':'integer','minimum':1},'sha256':string(pattern='^[a-f0-9]{64}$')})
S['Attachment']=obj({'type':{'const':'image'},'image':ref('ImageReceipt'),'url':string(format='uri'),'url_expires_at':DT})
S['Message']=obj({'message_id':UUID,'role':enum('user','assistant','system'),'text':string(maxLength=8000),'attachments':arr(ref('Attachment')),'created_at':DT})
S['Endpoint']=obj({'component_id':ID,'pin':string(minLength=1,maxLength=80)})
S['Component']=obj({'id':ID,'type':string(minLength=1),'label':string(),'value':nullable(string()),'pins':arr(string(minLength=1),uniqueItems=True)})
S['Connection']=obj({'id':ID,'from':ref('Endpoint'),'to':ref('Endpoint')})
S['Candidate']=obj({'revision':VER,'image_id':UUID,'components':arr(ref('Component')),'connections':arr(ref('Connection')),'confirmed':{'type':'boolean'}})
S['Job']=obj({'job_id':UUID,'type':enum('extraction','analysis','reply'),'status':enum('queued','running'),'retry_after_ms':{'type':'integer','minimum':1000,'maximum':30000}})
S['Finding']=obj({'code':ID,'severity':enum('info','warning','error'),'message':string(minLength=1),'component_ids':arr(ID),'connection_ids':arr(ID)})
S['Assessment']=obj({'candidate_revision':VER,'verdict':enum('correct','incorrect','inconclusive'),'explanation':string(minLength=1),'findings':arr(ref('Finding')),'created_at':DT})
base={'action_id':UUID,'label':string(minLength=1),'candidate_revision':nullable(VER)}
def action(name,typ,extra,revision=False):
 p={**base,'type':{'const':typ},**extra}
 if revision:p['candidate_revision']=VER
 S[name]=obj(p)
action('ReviewConnectionAction','review_connection',{'connection_id':ID,'prompt':string(minLength=1)},True)
action('ConfirmRevisionAction','confirm_revision',{'prompt':string(minLength=1)},True)
action('MeasurementAction','enter_measurement',{'measurement_id':ID,'prompt':string(minLength=1),'quantity':enum('voltage','current','resistance','frequency','other'),'unit':string(minLength=1),'minimum':nullable({'type':'number'}),'maximum':nullable({'type':'number'}),'probe_points':arr(ref('Endpoint'))},True)
action('CheckAction','perform_check',{'check_id':ID,'instructions':string(minLength=1)},True)
action('InstructorAction','request_instructor_help',{'reason':string(minLength=1)})
action('RetryJobAction','retry_job',{'failed_job_id':UUID,'reason':string(minLength=1)})
action('UploadImageAction','upload_image',{'prompt':string(minLength=1),'accepted_content_types':arr(enum('image/jpeg','image/png'),minItems=1),'max_size_bytes':{'const':5242880},'description_required':{'const':True}})
S['Action']={'oneOf':[ref(n) for n in ['UploadImageAction','ReviewConnectionAction','ConfirmRevisionAction','MeasurementAction','CheckAction','InstructorAction','RetryJobAction']],'discriminator':{'propertyName':'type'}}
S['Session']=obj({'session_id':UUID,'mode':enum('stub','live'),'experiment_id':ID,'experiment_version':string(minLength=1),'session_version':VER,'status':enum('awaiting_image','extracting','awaiting_input','analyzing','ready','failed','closed'),'candidate':nullable(ref('Candidate')),'messages':arr(ref('Message')),'pending_actions':arr(ref('Action')),'job':nullable(ref('Job')),'assessment':nullable(ref('Assessment')),'created_at':DT,'updated_at':DT})
S['Session']['allOf']=[{'if':{'properties':{'mode':{'const':'stub'}},'required':['mode']},'then':{'properties':{'assessment':{'type':'null'}}}}]
S['MessagePayload']=obj({'text':TEXT})
S['ConfirmPayload']=obj({'action_id':UUID})
S['MeasurementPayload']=obj({'action_id':UUID,'measurement_id':ID,'value':{'type':'number'},'unit':string(minLength=1)})
S['CheckPayload']=obj({'action_id':UUID,'check_id':ID,'result':enum('passed','failed','inconclusive'),'observation':string(maxLength=2000)},['action_id','check_id','result'])
ops=[]
for typ,props in [('add',{'from':ref('Endpoint'),'to':ref('Endpoint')}),('remove',{'connection_id':ID}),('replace',{'connection_id':ID,'from':ref('Endpoint'),'to':ref('Endpoint')})]:
 ops.append(obj({'operation':{'const':typ},**props}))
S['CorrectionPayload']=obj({'action_id':UUID,'connection_changes':{'type':'array','items':{'oneOf':ops},'minItems':1,'maxItems':50},'note':string(maxLength=2000)},['action_id','connection_changes'])
S['InstructorPayload']=obj({'action_id':UUID,'reason':string(minLength=1,maxLength=2000)})
S['RetryJobPayload']=obj({'action_id':UUID,'failed_job_id':UUID})
S['ClosePayload']=obj({'reason':enum('user_exit')})
events=[]
for typ,payload,revision in [('message','MessagePayload',False),('confirm_candidate','ConfirmPayload',True),('submit_correction','CorrectionPayload',True),('submit_measurement','MeasurementPayload',True),('submit_check_result','CheckPayload',True),('request_instructor_help','InstructorPayload',False),('retry_job','RetryJobPayload',False),('close_session','ClosePayload',False)]:
 name=''.join(x.title() for x in typ.split('_'))+'Event'
 props={'event_id':UUID,'expected_session_version':VER,'type':{'const':typ},'payload':ref(payload)}
 if revision:props['candidate_revision']=VER
 S[name]=obj(props);events.append(ref(name))
S['Event']={'oneOf':events,'discriminator':{'propertyName':'type'}}
S['FieldError']=obj({'field':string(),'message':string()})
S['Error']=obj({'request_id':UUID,'error':obj({'code':enum('UNAUTHENTICATED','FORBIDDEN','NOT_FOUND','EXPERIMENT_UNAVAILABLE','EXPERIMENT_VERSION_UNAVAILABLE','STALE_SESSION','STALE_CANDIDATE','ACTION_UNAVAILABLE','SESSION_CLOSED','JOB_IN_PROGRESS','IDEMPOTENCY_CONFLICT','IMAGE_TOO_LARGE','UNSUPPORTED_IMAGE','VALIDATION_ERROR','RATE_LIMITED','SERVICE_UNAVAILABLE','INTERNAL_ERROR'),'message':string(minLength=1),'retryable':{'type':'boolean'},'field_errors':arr(ref('FieldError')),'current_session':nullable(ref('Session'))})})
for name,model in [('SessionResponse','Session'),('ExperimentsResponse','ExperimentList')]:S[name]=obj({'request_id':UUID,'data':ref(model)})
S['UploadImage']=obj({'expected_session_version':VER,'description':string(minLength=1,maxLength=2000,pattern='\\S'),'image':string(format='binary')})
S['HealthResponse']=obj({'status':enum('ok','degraded'),'service':{'const':'circuitly-api'},'api_version':{'const':'1'},'mode':enum('stub','live')})
err={str(c):{'description':d,'content':{'application/json':{'schema':ref('Error')}}} for c,d in [(401,'Missing/expired Firebase token'),(403,'Forbidden'),(404,'Not found or session not owned by caller'),(409,'Version/action/state/idempotency conflict'),(413,'Image exceeds limit'),(415,'Invalid or unsupported image'),(422,'Invalid request fields'),(429,'Rate limited; obey Retry-After'),(503,'Service unavailable; obey Retry-After'),(500,'Unexpected server error')]}
def success(code,model,desc):return {str(code):{'description':desc,'content':{'application/json':{'schema':ref(model)}}}}
def body(model):return {'required':True,'content':{'application/json':{'schema':ref(model)}}}
sid={'name':'session_id','in':'path','required':True,'schema':UUID}
idem={'name':'Idempotency-Key','in':'header','required':True,'schema':UUID,'description':'Persist across uncertain retries. Same key and payload replays original response for 24 hours; different payload is 409.'}
def op(summary,model='SessionResponse',code=200,**kw):
 return {'summary':summary,'responses':{**success(code,model,'Authoritative response; see normative semantics in contract.md'),**err},**kw}
paths={
'/health':{'get':{'summary':'Check API deployment mode','security':[],'responses':success(200,'HealthResponse','Reports stub or live mode')}} ,
'/experiments':{'get':op('List experiments and current support status','ExperimentsResponse')},
'/sessions':{'post':op('Create a session pinned to one experiment version',code=201,parameters=[idem],requestBody=body('CreateSession'))},
'/sessions/{session_id}/images':{'post':op('Upload image, append user message and queue extraction',code=202,parameters=[sid,idem],requestBody={'required':True,'content':{'multipart/form-data':{'schema':ref('UploadImage')}}})},
'/sessions/{session_id}':{'get':op('Restore the complete authoritative session',parameters=[sid])},
'/sessions/{session_id}/events':{'post':op('Apply an idempotent typed session event',parameters=[sid],requestBody=body('Event'))}}
# Events that queue work use the same response schema and a distinct accepted status.
paths['/sessions/{session_id}/events']['post']['responses'].update(success(202,'SessionResponse','Accepted; processing continues. Poll the session while job is non-null.'))
api={'openapi':'3.1.0','info':{'title':'Circuitly API - finalized v1 design','version':'1.0.0','description':'Normative target contract. NOT implemented by the existing upload-only dummy service. Read contract.md for concurrency, job and lifecycle rules.'},'servers':[{'url':'https://git-good-1.onrender.com/api/v1','description':'Target route prefix; not a claim of current deployment'}],'security':[{'firebaseBearer':[]}],'paths':paths,'components':{'securitySchemes':{'firebaseBearer':{'type':'http','scheme':'bearer','bearerFormat':'Firebase ID token'}},'schemas':S}}
(OUT/'openapi.json').write_text(json.dumps(api,ensure_ascii=False,indent=2)+'\n')
# Examples use fixed valid UUIDs so they are immediately schema-testable.
u=lambda n:f'00000000-0000-4000-8000-{n:012d}'
ts='2026-11-01T10:00:00Z'
candidate={'revision':3,'image_id':u(2),'components':[{'id':'r1','type':'resistor','label':'R1','value':'1000 ohm','pins':['1','2']},{'id':'gnd','type':'ground','label':'GND','value':None,'pins':['0']}],'connections':[{'id':'wire-1','from':{'component_id':'r1','pin':'2'},'to':{'component_id':'gnd','pin':'0'}}],'confirmed':False}
session={'session_id':u(1),'mode':'stub','experiment_id':'ohms-law','experiment_version':'1','session_version':8,'status':'awaiting_input','candidate':candidate,'messages':[{'message_id':u(3),'role':'assistant','text':'Review the extracted connection between R1 pin 2 and ground before confirming the wiring.','attachments':[],'created_at':ts}],'pending_actions':[{'action_id':u(4),'type':'review_connection','label':'Review connection','candidate_revision':3,'connection_id':'wire-1','prompt':'Is R1 pin 2 connected to ground?'},{'action_id':u(5),'type':'confirm_revision','label':'Confirm wiring','candidate_revision':3,'prompt':'Confirm only after reviewing all extracted wiring.'}],'job':None,'assessment':None,'created_at':ts,'updated_at':ts}
examples={'create_session':{'experiment_id':'ohms-law','experiment_version':'1'},'session_response':{'request_id':u(6),'data':session},'confirm_event':{'event_id':u(7),'expected_session_version':8,'type':'confirm_candidate','candidate_revision':3,'payload':{'action_id':u(5)}},'message_event':{'event_id':u(8),'expected_session_version':8,'type':'message','payload':{'text':'Why should R1 pin 2 be connected to ground?'}},'measurement_event':{'event_id':u(9),'expected_session_version':10,'type':'submit_measurement','candidate_revision':3,'payload':{'action_id':u(10),'measurement_id':'voltage-r1','value':5.0,'unit':'V'}},'close_event':{'event_id':u(11),'expected_session_version':12,'type':'close_session','payload':{'reason':'user_exit'}},'stale_confirmation_error':{'request_id':u(12),'error':{'code':'STALE_CANDIDATE','message':'Wiring changed. Review the current revision before confirming.','retryable':False,'field_errors':[],'current_session':{**session,'session_version':9,'candidate':{**candidate,'revision':4},'pending_actions':[]}}}}
(OUT/'examples.json').write_text(json.dumps(examples,ensure_ascii=False,indent=2)+'\n')
print('Wrote OpenAPI and example JSON')
