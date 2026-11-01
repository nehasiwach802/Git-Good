import json, re, copy
from pathlib import Path
p=Path('docs/api-v1');api=json.loads((p/'openapi.json').read_text());examples=json.loads((p/'examples.json').read_text())
def resolve(ref):
 node=api
 for part in ref.removeprefix('#/').split('/'):node=node[part]
 return node
def valid(s,v):
 if '$ref' in s:return valid(resolve(s['$ref']),v)
 if 'oneOf' in s and sum(valid(x,v) for x in s['oneOf'])!=1:return False
 if 'allOf' in s and not all(valid(x,v) for x in s['allOf']):return False
 if 'if' in s and valid(s['if'],v) and not valid(s.get('then',{}),v):return False
 if 'const' in s and s['const']!=v:return False
 if 'enum' in s and v not in s['enum']:return False
 typ=s.get('type')
 if typ=='null' and v is not None:return False
 if typ=='object' and not isinstance(v,dict):return False
 if typ=='array' and not isinstance(v,list):return False
 if typ=='string' and not isinstance(v,str):return False
 if typ=='integer' and (not isinstance(v,int) or isinstance(v,bool)):return False
 if typ=='number' and (not isinstance(v,(float,int)) or isinstance(v,bool)):return False
 if typ=='boolean' and not isinstance(v,bool):return False
 if isinstance(v,dict):
  props=s.get('properties',{})
  if any(k not in v for k in s.get('required',[])):return False
  if s.get('additionalProperties') is False and any(k not in props for k in v):return False
  if any(k in v and not valid(t,v[k]) for k,t in props.items()):return False
 if isinstance(v,list):
  if len(v)<s.get('minItems',0) or len(v)>s.get('maxItems',float('inf')):return False
  if any(not valid(s.get('items',{}),x) for x in v):return False
 if isinstance(v,str):
  if len(v)<s.get('minLength',0) or len(v)>s.get('maxLength',float('inf')):return False
  if 'pattern' in s and not re.search(s['pattern'],v):return False
 if isinstance(v,(int,float)) and not isinstance(v,bool):
  if v<s.get('minimum',-float('inf')) or v>s.get('maximum',float('inf')):return False
 return True
def refs(node):
 if isinstance(node,dict):
  if '$ref' in node:resolve(node['$ref'])
  for value in node.values():refs(value)
 elif isinstance(node,list):
  for value in node:refs(value)
refs(api)
for name,value in examples.items():
 schema='CreateSession' if name=='create_session' else 'SessionResponse' if name=='session_response' else 'Error' if name.endswith('_error') else 'Event'
 assert valid(api['components']['schemas'][schema],value),name
bad=copy.deepcopy(examples['confirm_event']);bad.pop('candidate_revision');assert not valid(api['components']['schemas']['Event'],bad)
bad=copy.deepcopy(examples['session_response']);bad['data']['assessment']={'candidate_revision':3,'verdict':'correct','explanation':'fake','findings':[],'created_at':'2026-11-01T10:00:00Z'};assert not valid(api['components']['schemas']['SessionResponse'],bad)
print('JSON parse, references, example structure and negative revision/stub checks passed.')
