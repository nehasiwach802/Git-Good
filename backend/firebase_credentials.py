"""Offline service-account validation shared by auth and deployment checks."""
import json
import os
from pathlib import Path
from firebase_admin import credentials
from google.auth.exceptions import GoogleAuthError
from cryptography.exceptions import UnsupportedAlgorithm


class CredentialConfigurationError(ValueError):
    def __init__(self,code,exception_type=None):
        super().__init__(code)
        self.code=code
        self.exception_type=exception_type or type(self).__name__


def load_certificate(project):
    if not isinstance(project,str) or not project.strip():
        raise CredentialConfigurationError('missing_project')
    raw=os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')
    if not raw or not raw.strip():
        filename=os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if not filename:raise CredentialConfigurationError('missing_credentials')
        try:
            with Path(filename).open(encoding='utf-8') as stream:raw=stream.read(131073)
        except (OSError,UnicodeError) as exc:
            raise CredentialConfigurationError('unreadable_credentials',type(exc).__name__) from None
    if len(raw)>131072:raise CredentialConfigurationError('invalid_credentials_json')
    try:info=json.loads(raw)
    except (ValueError,RecursionError) as exc:
        raise CredentialConfigurationError('invalid_credentials_json',type(exc).__name__) from None
    if not isinstance(info,dict) or info.get('type')!='service_account':
        raise CredentialConfigurationError('not_service_account')
    if info.get('project_id')!=project:
        raise CredentialConfigurationError('project_mismatch')
    if any(not isinstance(info.get(name),str) or not info[name].strip()
           for name in ('private_key','client_email','token_uri')):
        raise CredentialConfigurationError('invalid_service_account')
    try:return credentials.Certificate(info)
    except (ValueError,TypeError,KeyError,GoogleAuthError,UnsupportedAlgorithm) as exc:
        raise CredentialConfigurationError('invalid_service_account',type(exc).__name__) from None
