import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import MagicMock,patch
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from firebase_admin import auth,exceptions
from google.auth.exceptions import RefreshError
from backend.firebase_credentials import load_certificate,CredentialConfigurationError
from backend.firebase_diagnostic import diagnose
from backend.preflight import check
from backend.config import Settings


class CredentialTests(TestCase):
    @classmethod
    def setUpClass(cls):
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        cls.info={'type':'service_account','project_id':'synthetic-project','private_key_id':'synthetic-key',
            'private_key':key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()).decode(),
            'client_email':'synthetic@synthetic-project.iam.gserviceaccount.com','token_uri':'https://oauth2.googleapis.com/token'}

    def test_valid_environment_certificate_is_loaded_offline(self):
        with patch.dict(os.environ,{'FIREBASE_SERVICE_ACCOUNT_JSON':json.dumps(self.info)},clear=True),patch('google.auth.transport.requests.Request') as network:
            certificate=load_certificate('synthetic-project')
        self.assertEqual(certificate.project_id,'synthetic-project');network.assert_not_called()

    def test_secret_file_and_blank_environment_value(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/'synthetic.json';path.write_text(json.dumps(self.info))
            with patch.dict(os.environ,{'FIREBASE_SERVICE_ACCOUNT_JSON':'','GOOGLE_APPLICATION_CREDENTIALS':str(path)},clear=True):
                self.assertEqual(load_certificate('synthetic-project').project_id,'synthetic-project')

    def test_missing_unreadable_malformed_wrong_project_and_invalid_key(self):
        cases=[({},'missing_credentials'),({'GOOGLE_APPLICATION_CREDENTIALS':'/nonexistent/synthetic.json'},'unreadable_credentials'),
            ({'FIREBASE_SERVICE_ACCOUNT_JSON':'not JSON'},'invalid_credentials_json'),
            ({'FIREBASE_SERVICE_ACCOUNT_JSON':'[]'},'not_service_account'),
            ({'FIREBASE_SERVICE_ACCOUNT_JSON':'{"type":"authorized_user"}'},'not_service_account'),
            ({'FIREBASE_SERVICE_ACCOUNT_JSON':json.dumps({**self.info,'project_id':'another-project'})},'project_mismatch'),
            ({'FIREBASE_SERVICE_ACCOUNT_JSON':json.dumps({**self.info,'client_email':None})},'invalid_service_account'),
            ({'FIREBASE_SERVICE_ACCOUNT_JSON':json.dumps({**self.info,'private_key':'sensitive-invalid-key'})},'invalid_service_account')]
        for environment,expected in cases:
            with self.subTest(code=expected),patch.dict(os.environ,environment,clear=True):
                with self.assertRaises(CredentialConfigurationError) as caught:load_certificate('synthetic-project')
                self.assertEqual(caught.exception.code,expected)
                self.assertNotIn('sensitive-invalid-key',str(caught.exception))

    def test_preflight_rejects_invalid_key_even_when_json_exists(self):
        with TemporaryDirectory() as directory,patch.dict(os.environ,{'FIREBASE_SERVICE_ACCOUNT_JSON':json.dumps({**self.info,'private_key':'sensitive-invalid-key'})},clear=True):
            result=check(Settings(data_dir=Path(directory),firebase_project='synthetic-project',vision_enabled=False,qwen_enabled=False))
        self.assertFalse(result['checks']['firebase_credentials'])
        self.assertEqual(result['firebase_credential_error'],'invalid_service_account')
        self.assertFalse(result['firebase_permissions_verified'])
        self.assertNotIn('sensitive-invalid-key',json.dumps(result))

    def test_preflight_valid_key_does_not_claim_live_permission_checks(self):
        with TemporaryDirectory() as directory,patch.dict(os.environ,{'FIREBASE_SERVICE_ACCOUNT_JSON':json.dumps(self.info)},clear=True),patch('backend.preflight.find_ngspice',return_value='synthetic-solver'):
            result=check(Settings(data_dir=Path(directory),firebase_project='synthetic-project',vision_enabled=False,qwen_enabled=False))
        self.assertEqual(result['status'],'ready')
        self.assertFalse(result['firebase_permissions_verified'])
        self.assertFalse(result['live_providers_verified'])


class LiveDiagnosticTests(TestCase):
    def test_cli_requires_explicit_live_opt_in(self):
        from backend.firebase_diagnostic import main
        from contextlib import redirect_stderr
        from io import StringIO
        with patch('sys.argv',['diagnostic']),patch('backend.firebase_diagnostic.diagnose') as run,redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as caught:main()
        self.assertEqual(caught.exception.code,2);run.assert_not_called()

    def test_oauth_and_auth_user_read_succeed_without_printing_user_or_token(self):
        certificate=MagicMock()
        with patch('backend.firebase_diagnostic.load_certificate',return_value=certificate),patch('firebase_admin.initialize_app',return_value=object()),patch('firebase_admin.delete_app') as delete,patch('firebase_admin.auth.get_user',side_effect=auth.UserNotFoundError('synthetic-user-not-found')):
            result=diagnose('synthetic-project')
        self.assertEqual(result['status'],'passed')
        self.assertTrue(all(result['checks'].values()))
        certificate.get_credential.return_value.refresh.assert_called_once()
        delete.assert_called_once()
        self.assertNotIn('synthetic-user-not-found',json.dumps(result))

    def test_oauth_failure_does_not_attempt_user_lookup(self):
        certificate=MagicMock();certificate.get_credential.return_value.refresh.side_effect=RefreshError('sensitive-token')
        with patch('backend.firebase_diagnostic.load_certificate',return_value=certificate),patch('firebase_admin.auth.get_user') as user:
            result=diagnose('synthetic-project')
        self.assertEqual(result['error_stage'],'oauth_access');user.assert_not_called()
        self.assertNotIn('sensitive-token',json.dumps(result))

    def test_permission_failure_keeps_oauth_success_separate(self):
        with patch('backend.firebase_diagnostic.load_certificate',return_value=MagicMock()),patch('firebase_admin.initialize_app',return_value=object()),patch('firebase_admin.delete_app') as delete,patch('firebase_admin.auth.get_user',side_effect=exceptions.PermissionDeniedError('private-account-details')):
            result=diagnose('synthetic-project')
        self.assertEqual(result['status'],'failed')
        self.assertTrue(result['checks']['oauth_access'])
        self.assertFalse(result['checks']['firebase_user_read'])
        self.assertEqual(result['exception_type'],'PermissionDeniedError')
        self.assertNotIn('private-account-details',json.dumps(result));delete.assert_called_once()
