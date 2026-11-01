"""ML2-owned compatibility boundary. No ML3 imports, media or product calls.

The backend injects ML3's actual types/callback. Strict historical ML3 contracts
require probabilities; absence of calibrated scores must never become fake ones.
"""
from copy import deepcopy
import inspect
import json
import math
import re


CAUSES=('wiring','concept','apparatus')
UNSAFE=re.compile(r'\b(?:mains|wall\s+(?:outlet|socket)|live\s+prob(?:e|ing)|prob(?:e|ing)\s+(?:a\s+)?live|live\s+(?:circuit|wire|node)|large\s+capacitors?|high\s+voltage)\b',re.I)


def facts(diagnostic,session_id):
    if not isinstance(diagnostic,dict) or diagnostic.get('schema_version')!='2.0':
        raise ValueError('Expected the existing ML2 schema2.0 diagnostic')
    if not isinstance(session_id,str) or not session_id.strip():raise ValueError('Session ID required')
    support={cause:diagnostic['hypotheses'][cause]['support'] for cause in CAUSES}
    if any(value not in ('supported','unresolved') for value in support.values()):raise ValueError('Invalid hypothesis support')
    supported=[cause for cause,value in support.items() if value=='supported']
    return support,supported[0] if len(supported)==1 else 'undetermined'


def validate_probabilities(probabilities,source):
    if probabilities is None:return
    if not isinstance(source,str) or not source.strip():
        raise ValueError('An explicit trusted probability-model source is required')
    if not isinstance(probabilities,dict) or set(probabilities)!=set(CAUSES):
        raise ValueError('Provide all three model probabilities')
    for value in probabilities.values():
        if type(value) not in (int,float) or not 0<=value<=1 or not math.isfinite(value):
            raise ValueError('Probabilities must be finite values in [0,1]')


def fallback(diagnostic,session_id,support,cause,status,probabilities=None):
    action=diagnostic['next_check']['reason']
    if UNSAFE.search(action+' '+json.dumps(diagnostic.get('findings',[]))):
        return {'status':'refused','session_id':session_id,
            'explanation':'Stop and ask your instructor for help.',
            'next_action':'Ask your instructor for help.','suspected_cause':cause,
            'cause_probabilities':deepcopy(probabilities),'hypothesis_support':deepcopy(support),
            'probability_status':'provided_by_ml2' if probabilities is not None else 'not_calibrated',
            'limitations':deepcopy(diagnostic.get('limitations',[])),'evidence':[],
            'context':{'personal':[],'approved_equipment':[],'memory_status':'not_requested'},
            'wording_source':'ml2_template','model_status':status}
    text=('The evidence does not identify a cause yet.' if cause=='undetermined' else
          'The diagnostic engine currently supports a '+cause+' hypothesis.')
    return {'status':'fallback','session_id':session_id,
        'explanation':text+' Next check: '+action,'next_action':action,'suspected_cause':cause,
        'cause_probabilities':deepcopy(probabilities),'hypothesis_support':deepcopy(support),
        'probability_status':'provided_by_ml2' if probabilities is not None else 'not_calibrated',
        'limitations':deepcopy(diagnostic.get('limitations',[])),
        'evidence':[{'evidence_id':f['id'],'description':json.dumps(f,allow_nan=False),
                     'source':'ml2','verification':'unverified' if f.get('certainty') in ('possible','unresolved') else 'ml2_computed'}
                    for f in diagnostic.get('findings',[])],
        'context':{'personal':[],'approved_equipment':[],'memory_status':'not_requested'},
        'wording_source':'ml2_template','model_status':status}


def explain(diagnostic,session_id,*,diagnostic_type,evidence_type,explain_callback,
            probabilities=None,probability_source=None):
    """Preserve ML2 facts and adapt to the injected, unchanged ML3 implementation.

    Normal backend ML3 (optional probabilities) receives its usual structured
    result. Historical strict ML3 is invoked only with explicitly supplied model
    probabilities. Otherwise return grounded fallback text with a visible reason.
    Do not supply probabilities, source IDs, callbacks or consumer types from a
    mobile request. Backend owns principal, authorized context and model setup.
    """
    support,cause=facts(diagnostic,session_id)
    validate_probabilities(probabilities,probability_source)
    accepts_support='hypothesis_support' in inspect.signature(diagnostic_type).parameters
    if probabilities is None and not accepts_support:
        return fallback(diagnostic,session_id,support,cause,'ml3_requires_probabilities')
    evidence=tuple(evidence_type(f['id'],json.dumps(f,allow_nan=False),'ml2',
        'unverified' if f.get('certainty') in ('possible','unresolved') else 'ml2_computed')
        for f in diagnostic.get('findings',[]))
    kwargs={'hypothesis_support':deepcopy(support)} if accepts_support else {}
    result=diagnostic_type(session_id,cause,deepcopy(probabilities),evidence,
        tuple(diagnostic.get('limitations',[])),diagnostic['next_check']['reason'],**kwargs)
    try:
        response=explain_callback(result)
        if not isinstance(response,dict):raise TypeError('Invalid explanation response')
        return response
    except Exception:
        return fallback(diagnostic,session_id,support,cause,'ml3_unavailable',probabilities)
