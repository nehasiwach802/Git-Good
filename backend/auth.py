"""Firebase identity verification; Android never supplies trusted UID/role fields."""
import logging
import os
import threading
from fastapi import HTTPException
from knowledge_lifecycle import Principal
from firebase_admin import auth, exceptions, tenant_mgt
from google.auth.exceptions import GoogleAuthError
from requests.exceptions import RequestException
from .firebase_credentials import load_certificate, CredentialConfigurationError

_lock = threading.Lock()
logger = logging.getLogger(__name__)


def firebase_app(project):
    import firebase_admin
    with _lock:
        try:app=firebase_admin.get_app('gitgood-backend')
        except ValueError:
            return firebase_admin.initialize_app(load_certificate(project),{'projectId':project},name='gitgood-backend')
        if app.project_id!=project:raise CredentialConfigurationError('project_mismatch')
        return app


def fail(status,code,message,exc,stage):
    # Exception messages/tracebacks can include tokens, key contents or account data.
    # Only controlled stages and exception class names are logged server-side.
    logger.warning('firebase_auth_failure stage=%s exception_type=%s',stage,
                   getattr(exc,'exception_type',type(exc).__name__))
    raise HTTPException(status,detail={'code':code,'message':message}) from None


def firebase_principal(token, project):
    if not project:
        raise HTTPException(503, detail={'code':'auth_not_configured','message':'Firebase verification is not configured'})
    if not isinstance(token,str) or not token.strip():
        raise HTTPException(401,detail={'code':'invalid_token','message':'Valid Firebase ID token required'})
    try:
        app=firebase_app(project)
    except (CredentialConfigurationError,GoogleAuthError,OSError,exceptions.FirebaseError,RequestException) as exc:
        fail(503,'auth_not_configured','Firebase service credentials are unavailable or invalid',exc,'configuration')
    except Exception as exc:
        fail(500,'auth_backend_failure','Authentication backend failed',exc,'initialization')
    try:
        claims = auth.verify_id_token(token, app=app, check_revoked=True)
    except (auth.InvalidIdTokenError,auth.RevokedIdTokenError,auth.UserDisabledError,
            auth.UserNotFoundError,tenant_mgt.TenantIdMismatchError) as exc:
        fail(401,'invalid_token','Valid Firebase ID token required',exc,'token')
    except (exceptions.FirebaseError,GoogleAuthError,RequestException) as exc:
        fail(503,'auth_service_unavailable','Firebase verification service is unavailable',exc,'verification_service')
    except Exception as exc:
        fail(500,'auth_backend_failure','Authentication backend failed',exc,'verification')
    try:
        uid = claims['uid']
        lab = claims.get('lab_id', os.getenv('DEFAULT_LAB_ID','default-lab'))
        role = claims.get('role','student')
        return Principal(uid,lab,role)
    except Exception as exc:
        fail(500,'auth_backend_failure','Authentication backend failed',exc,'claims')
