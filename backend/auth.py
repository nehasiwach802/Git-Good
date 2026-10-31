"""Firebase identity verification; Android never supplies trusted UID/role fields."""
import json
import os
import threading
from fastapi import HTTPException
from knowledge_lifecycle import Principal

_lock = threading.Lock()


def firebase_principal(token, project):
    if not project:
        raise HTTPException(503, detail={'code':'auth_not_configured','message':'Firebase verification is not configured'})
    try:
        import firebase_admin
        from firebase_admin import auth, credentials
        with _lock:
            try:
                app = firebase_admin.get_app('gitgood-backend')
            except ValueError:
                raw = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')
                credential = credentials.Certificate(json.loads(raw)) if raw else credentials.ApplicationDefault()
                app = firebase_admin.initialize_app(credential, {'projectId':project}, name='gitgood-backend')
        claims = auth.verify_id_token(token, app=app, check_revoked=True)
        uid = claims['uid']
        lab = claims.get('lab_id', os.getenv('DEFAULT_LAB_ID','default-lab'))
        role = claims.get('role','student')
        return Principal(uid,lab,role)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, detail={'code':'invalid_token','message':'Valid Firebase ID token required'}) from None
