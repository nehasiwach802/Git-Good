from unittest import TestCase
from unittest.mock import patch
from fastapi import HTTPException
from firebase_admin import auth,exceptions
from google.auth.exceptions import RefreshError
from backend.auth import firebase_principal,firebase_app
from backend.firebase_credentials import CredentialConfigurationError


class FirebaseTests(TestCase):
    def test_unconfigured_auth_fails_closed(self):
        with self.assertRaises(HTTPException) as caught:firebase_principal('test','')
        self.assertEqual(caught.exception.status_code,503)

    def test_verified_identity_and_custom_claims(self):
        with patch('backend.auth.firebase_app',return_value=object()),patch('firebase_admin.auth.verify_id_token',return_value={'uid':'synthetic-user','lab_id':'synthetic-lab','role':'instructor'}) as verify:
            principal=firebase_principal('synthetic-token','synthetic-project')
        self.assertEqual((principal.actor_id,principal.lab_id,principal.role),('synthetic-user','synthetic-lab','instructor'))
        self.assertTrue(verify.call_args.kwargs['check_revoked'])

    def test_token_errors_are_401_and_logs_do_not_echo_secret_details(self):
        errors=[auth.InvalidIdTokenError('sensitive-token'),auth.ExpiredIdTokenError('sensitive-token',None),auth.RevokedIdTokenError('sensitive-token'),auth.UserDisabledError('sensitive-token'),auth.UserNotFoundError('sensitive-token')]
        for error in errors:
            with self.subTest(type=type(error).__name__),patch('backend.auth.firebase_app',return_value=object()),patch('firebase_admin.auth.verify_id_token',side_effect=error),self.assertLogs('backend.auth') as logs:
                with self.assertRaises(HTTPException) as caught:firebase_principal('synthetic-token','synthetic-project')
                self.assertEqual(caught.exception.status_code,401)
                self.assertIn(type(error).__name__,str(logs.output))
                self.assertNotIn('sensitive-token',str(logs.output)+str(caught.exception.detail))

    def test_configuration_errors_are_503(self):
        with patch('backend.auth.firebase_app',side_effect=CredentialConfigurationError('invalid_service_account','ValueError')):
            with self.assertRaises(HTTPException) as caught:firebase_principal('test','synthetic-project')
        self.assertEqual(caught.exception.status_code,503)

    def test_permission_refresh_and_provider_failures_are_503(self):
        errors=[exceptions.PermissionDeniedError('sensitive'),exceptions.UnauthenticatedError('sensitive'),exceptions.UnavailableError('sensitive'),auth.CertificateFetchError('sensitive',None),RefreshError('sensitive')]
        for error in errors:
            with self.subTest(type=type(error).__name__),patch('backend.auth.firebase_app',return_value=object()),patch('firebase_admin.auth.verify_id_token',side_effect=error):
                with self.assertRaises(HTTPException) as caught:firebase_principal('test','synthetic-project')
                self.assertEqual(caught.exception.status_code,503)
                self.assertNotIn('sensitive',str(caught.exception.detail))

    def test_unexpected_failures_are_500(self):
        for error in (RuntimeError('sensitive'),ValueError('sensitive')):
            with patch('backend.auth.firebase_app',return_value=object()),patch('firebase_admin.auth.verify_id_token',side_effect=error):
                with self.assertRaises(HTTPException) as caught:firebase_principal('test','synthetic-project')
                self.assertEqual(caught.exception.status_code,500)
                self.assertNotIn('sensitive',str(caught.exception.detail))

    def test_cached_app_project_mismatch_is_configuration_error(self):
        from types import SimpleNamespace
        with patch('firebase_admin.get_app',return_value=SimpleNamespace(project_id='another-project')):
            with self.assertRaises(CredentialConfigurationError):firebase_app('synthetic-project')

    def test_empty_token_does_not_call_verifier(self):
        with patch('firebase_admin.auth.verify_id_token') as verify:
            with self.assertRaises(HTTPException) as caught:firebase_principal('','synthetic-project')
        self.assertEqual(caught.exception.status_code,401);verify.assert_not_called()

    def test_unexpected_initialization_and_claims_failures_are_500(self):
        with patch('backend.auth.firebase_app',side_effect=RuntimeError('private initialization detail')):
            with self.assertRaises(HTTPException) as caught:firebase_principal('test','synthetic-project')
        self.assertEqual(caught.exception.status_code,500)
        with patch('backend.auth.firebase_app',return_value=object()),patch('firebase_admin.auth.verify_id_token',return_value={}):
            with self.assertRaises(HTTPException) as caught:firebase_principal('test','synthetic-project')
        self.assertEqual(caught.exception.status_code,500)
