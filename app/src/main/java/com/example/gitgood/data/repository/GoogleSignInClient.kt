package com.example.gitgood.data.repository
import android.content.Context
import androidx.credentials.ClearCredentialStateRequest
import androidx.credentials.CredentialManager
import androidx.credentials.CustomCredential
import androidx.credentials.GetCredentialRequest
import com.example.gitgood.R
import com.google.android.libraries.identity.googleid.GetSignInWithGoogleOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential
import javax.inject.Inject
class GoogleSignInClient @Inject constructor() {
    suspend fun signIn(context: Context): String {
        val option = GetSignInWithGoogleOption.Builder(context.getString(R.string.default_web_client_id)).build()
        val response = CredentialManager.create(context).getCredential(
            context, GetCredentialRequest.Builder().addCredentialOption(option).build()
        )
        val credential = response.credential
        require(credential is CustomCredential && credential.type == GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL) {
            "Google did not return a valid sign-in credential."
        }
        return GoogleIdTokenCredential.createFrom(credential.data).idToken
    }
    suspend fun clear(context: Context) {
        CredentialManager.create(context).clearCredentialState(ClearCredentialStateRequest())
    }
}
