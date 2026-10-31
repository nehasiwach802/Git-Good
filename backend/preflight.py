"""Offline deployment checks. Never calls model providers or product memory."""
import argparse
import json
import os
from pathlib import Path
import tempfile
from .catalog import load_catalog
from .config import Settings
from reasoning.spice import find_ngspice
from .firebase_credentials import load_certificate,CredentialConfigurationError


def check(settings, *, production=False, authenticated=False, catalog=None):
    checks={}
    checks['firebase_project']=bool(settings.firebase_project) or authenticated
    credential_error=None
    if authenticated:checks['firebase_credentials']=True
    else:
        try:
            load_certificate(settings.firebase_project)
            checks['firebase_credentials']=True
        except CredentialConfigurationError as exc:
            checks['firebase_credentials']=False
            credential_error=exc.code
    checks['ngspice']=bool(find_ngspice())
    checks['worker']=settings.worker_enabled
    try:
        settings.data_dir.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryFile(dir=settings.data_dir) as probe:probe.write(b'ready');probe.flush()
        checks['writable_storage']=True
    except OSError:checks['writable_storage']=False
    try:
        records=catalog if catalog is not None else load_catalog(settings.catalog_path)
        checks['catalog']=bool(records)
        approved=sum(x.get('workflow_approved') is True and x['reference']['approval']=='approved' and not x.get('simulated',False) for x in records.values())
    except (OSError,ValueError,KeyError,TypeError):
        checks['catalog']=False;approved=0
    if production:checks['approved_real_experiments']=approved>0
    if settings.vision_enabled:
        checks['vision_configuration']=bool(os.getenv('GEMINI_API_KEY') and os.getenv('GEMINI_MODEL'))
    if settings.qwen_enabled and os.getenv('QWEN_MODEL'):
        checks['qwen_configuration']=bool(os.getenv('QWEN_BASE_URL') and os.getenv('DASHSCOPE_API_KEY'))
    if settings.memory_scopes_file:
        checks['memory_configuration']=Path(settings.memory_scopes_file).is_file() and bool(os.getenv('MEKO_MCP_URL') and os.getenv('MEKO_API_TOKEN'))
    return {'status':'ready' if all(checks.values()) else 'not_ready','checks':checks,
            'firebase_credential_error':credential_error,'firebase_permissions_verified':False,
            'approved_real_experiments':approved,'live_providers_verified':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--production',action='store_true',help='Also require approved real experiments')
    args=parser.parse_args()
    result=check(Settings.from_env(),production=args.production)
    print(json.dumps(result,indent=2))
    return 0 if result['status']=='ready' else 1


if __name__=='__main__':raise SystemExit(main())
