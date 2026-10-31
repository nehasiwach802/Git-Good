from unittest import TestCase
from unittest.mock import patch
from fastapi import HTTPException
from backend.auth import firebase_principal


class FirebaseTests(TestCase):
    def test_unconfigured_auth_fails_closed(self):
        with self.assertRaises(HTTPException) as caught:firebase_principal('test','')
        self.assertEqual(caught.exception.status_code,503)

    def test_verified_identity_and_custom_claims(self):
        with patch('firebase_admin.get_app',return_value=object()), patch('firebase_admin.auth.verify_id_token',return_value={'uid':'synthetic-user','lab_id':'synthetic-lab','role':'instructor'}) as verify:
            principal=firebase_principal('synthetic-token','synthetic-project')
        self.assertEqual((principal.actor_id,principal.lab_id,principal.role),('synthetic-user','synthetic-lab','instructor'))
        self.assertTrue(verify.call_args.kwargs['check_revoked'])

    def test_token_failure_does_not_echo_provider_details(self):
        with patch('firebase_admin.get_app',return_value=object()),patch('firebase_admin.auth.verify_id_token',side_effect=ValueError('private provider error')):
            with self.assertRaises(HTTPException) as caught:firebase_principal('synthetic-token','synthetic-project')
        self.assertEqual(caught.exception.status_code,401)
        self.assertNotIn('private provider error',str(caught.exception.detail))
