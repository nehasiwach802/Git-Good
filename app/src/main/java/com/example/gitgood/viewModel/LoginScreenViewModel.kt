package com.example.gitgood.viewModel
import android.content.Context
import android.util.Patterns
import androidx.credentials.exceptions.GetCredentialCancellationException
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.gitgood.data.repository.AuthRepository
import com.example.gitgood.data.repository.GoogleSignInClient
import com.example.gitgood.ui.screen.auth.login.LoginUiState
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject
@HiltViewModel
class LoginViewModel @Inject constructor(
    private val authRepository: AuthRepository,
    private val googleSignInClient: GoogleSignInClient
) : ViewModel() {
    private val _loginUiState = MutableStateFlow(LoginUiState())
    val loginUiState = _loginUiState.asStateFlow()
    val currentUser = authRepository.user.stateIn(viewModelScope, SharingStarted.Eagerly, authRepository.currentUser)
    fun onEmailChange(email: String) { _loginUiState.update { it.copy(email = email, errorMessage = null) } }
    fun onPasswordChange(password: String) { _loginUiState.update { it.copy(password = password, errorMessage = null) } }
    fun togglePasswordVisibility() { _loginUiState.update { it.copy(isPasswordVisible = !it.isPasswordVisible) } }
    fun clearMessage() { _loginUiState.update { it.copy(errorMessage = null, message = null) } }
    private fun validEmail(): Boolean {
        if (Patterns.EMAIL_ADDRESS.matcher(_loginUiState.value.email.trim()).matches()) return true
        _loginUiState.update { it.copy(errorMessage = "Enter a valid email address.") }; return false
    }
    fun onLoginClick() {
        if (!validEmail()) return
        val state = _loginUiState.value
        if (state.password.isBlank()) {
            _loginUiState.update { it.copy(errorMessage = "Enter your password.") }; return
        }
        runAuth { authRepository.signIn(state.email, state.password) }
    }
    fun onSignUpClick(email: String, password: String, confirmation: String) {
        if (!Patterns.EMAIL_ADDRESS.matcher(email.trim()).matches()) {
            _loginUiState.update { it.copy(errorMessage = "Enter a valid email address.") }; return
        }
        if (password.length < 6 || password != confirmation) {
            _loginUiState.update { it.copy(errorMessage = "Passwords must match and contain at least 6 characters.") }; return
        }
        runAuth { authRepository.signUp(email, password) }
    }
    fun onGoogleClick(context: Context) = runAuth {
        authRepository.signInWithGoogle(googleSignInClient.signIn(context))
    }
    fun onForgotPasswordClick() {
        if (!validEmail()) return
        val email = _loginUiState.value.email
        runAuth {
            authRepository.resetPassword(email)
            _loginUiState.update { it.copy(message = "If an account exists, a password reset email will be sent.") }
        }
    }
    fun signOut(context: Context) = runAuth {
        authRepository.signOut()
        googleSignInClient.clear(context)
    }
    private fun runAuth(action: suspend () -> Unit) {
        if (_loginUiState.value.isLoading) return
        _loginUiState.update { it.copy(isLoading = true, errorMessage = null, message = null) }
        viewModelScope.launch {
            try { action(); _loginUiState.update { it.copy(password = "") } }
            catch (_: GetCredentialCancellationException) { /* User dismissed the account picker. */ }
            catch (e: CancellationException) { throw e }
            catch (e: Exception) { _loginUiState.update { it.copy(errorMessage = e.localizedMessage ?: "Authentication failed. Please try again.") } }
            finally { _loginUiState.update { it.copy(isLoading = false) } }
        }
    }
}
