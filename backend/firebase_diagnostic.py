"""Operator-only live OAuth and Firebase Auth permission diagnostic.

Run explicitly on the deployment host: python -m backend.firebase_diagnostic --live
No credentials, access tokens or user records are printed. Never called by /ready.
"""
import argparse
import json
from uuid import uuid4
import firebase_admin
from firebase_admin import auth
from google.auth.transport.requests import Request
from .config import Settings
from .firebase_credentials import load_certificate


def diagnose(project,uid=None):
    checks={'credentials':False,'oauth_access':False,'firebase_user_read':False}
    stage='credentials';app=None
    try:
        certificate=load_certificate(project)
        checks['credentials']=True
        stage='oauth_access'
        transport=Request()
        def bounded_request(*args,**kwargs):
            kwargs['timeout']=10
            return transport(*args,**kwargs)
        certificate.get_credential().refresh(bounded_request)
        checks['oauth_access']=True
        stage='firebase_user_read'
        app=firebase_admin.initialize_app(certificate,{'projectId':project,'httpTimeout':10},name='gitgood-diagnostic-'+uuid4().hex)
        # Default to a synthetic nonexistent UID, not a scan of student accounts.
        try:auth.get_user(uid or 'gitgood-check-'+uuid4().hex,app=app)
        except auth.UserNotFoundError:pass
        checks['firebase_user_read']=True
        return {'status':'passed','checks':checks}
    except Exception as exc:
        return {'status':'failed','checks':checks,'error_stage':stage,
                'exception_type':getattr(exc,'exception_type',type(exc).__name__)}
    finally:
        if app is not None:firebase_admin.delete_app(app)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Explicitly enable Google network calls')
    parser.add_argument('--uid',help='Optional test UID; otherwise use a random nonexistent UID')
    args=parser.parse_args()
    if not args.live:parser.error('Pass --live to run network diagnostics on the deployment host')
    result=diagnose(Settings.from_env().firebase_project,args.uid)
    print(json.dumps(result,indent=2))
    return 0 if result['status']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
