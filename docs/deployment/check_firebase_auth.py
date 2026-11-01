"""Run in the backend environment; prints no private keys, tokens, or user records.

Checks the configured project, service-account key, OAuth access, and the
Firebase Auth user-read permission used by check_revoked=True. Does not create,
change, or delete a user. No Android ID token is collected by this script.
"""
import json
import os
import sys

EXPECTED_PROJECT = "circuitly-b1f4c"


def main():
    stage = "environment"
    try:
        project = os.environ.get("FIREBASE_PROJECT_ID", "")
        print("FIREBASE_PROJECT_ID matches Android:", project == EXPECTED_PROJECT)
        if project != EXPECTED_PROJECT:
            print("Set FIREBASE_PROJECT_ID to", EXPECTED_PROJECT)
            return 1

        stage = "service_account_json"
        account = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"])
        if not isinstance(account, dict):
            raise ValueError("Expected an object")
        matches = account.get("project_id") == project
        print("Service-account project matches Android:", matches)
        if not matches:
            print("Use a service-account JSON for", EXPECTED_PROJECT)
            return 1
        required = ("type", "project_id", "client_email", "private_key", "token_uri")
        if not all(isinstance(account.get(key), str) and account[key] for key in required):
            raise ValueError("Missing required service-account fields")
        if account["type"] != "service_account":
            raise ValueError("Expected a service account")

        import firebase_admin
        from firebase_admin import auth, credentials

        stage = "private_key"
        credential = credentials.Certificate(account)
        print("Private-key format: OK")
        stage = "oauth_access"
        credential.get_access_token()  # Never print the returned token.
        print("Service-account OAuth access: OK")

        stage = "firebase_auth_permission"
        app = firebase_admin.initialize_app(
            credential, {"projectId": project}, name="circuitly-auth-diagnostic"
        )
        try:
            try:
                # A read-only probe. A missing user demonstrates a successful,
                # authorized lookup; no record contents are printed if it exists.
                auth.get_user("__circuitly_configuration_probe__", app=app)
            except auth.UserNotFoundError:
                pass
            print("Firebase Auth user-read permission: OK")
        finally:
            firebase_admin.delete_app(app)
        print("Server credentials passed. If Android still gets 401, inspect the token-verification exception type on the backend.")
        return 0
    except Exception as exc:
        # Exception text can contain sensitive request details. Report type only.
        print("FAILED stage:", stage)
        print("Exception type:", type(exc).__name__)
        print("Do not share credentials or tokens; share these diagnostic lines only.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
