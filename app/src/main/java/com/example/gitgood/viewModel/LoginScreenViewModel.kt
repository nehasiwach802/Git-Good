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
import com.example.gitgood.ui.theme.screen.auth.forgotpassword.ForgotPasswordUiState
import kotlinx.coroutines.Job
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
    private val _forgotPasswordUiState = MutableStateFlow(ForgotPasswordUiState())
    val forgotPasswordUiState = _forgotPasswordUiState.asStateFlow()
    private var passwordResetJob: Job? = null
    private var passwordResetGeneration = 0
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
    fun openForgotPassword() {
        passwordResetGeneration++
        passwordResetJob?.cancel()
        clearMessage()
        _forgotPasswordUiState.value = ForgotPasswordUiState(email = _loginUiState.value.email.trim())
    }
    fun onResetEmailChange(email: String) {
        if (!_forgotPasswordUiState.value.isLoading) {
            _forgotPasswordUiState.update { it.copy(email = email, errorMessage = null, message = null) }
        }
    }
    fun sendPasswordReset() {
        val state = _forgotPasswordUiState.value
        if (state.isLoading || state.message != null) return
        val email = state.email.trim()
        if (!Patterns.EMAIL_ADDRESS.matcher(email).matches()) {
            _forgotPasswordUiState.update { it.copy(errorMessage = "Enter a valid email address.") }
            return
        }
        _forgotPasswordUiState.update { it.copy(isLoading = true, errorMessage = null) }
        val generation = passwordResetGeneration
        passwordResetJob = viewModelScope.launch {
            try {
                authRepository.resetPassword(email)
                if (generation == passwordResetGeneration) {
                    _forgotPasswordUiState.update { it.copy(message = "If an account exists for this email, a password reset link has been sent. Check your inbox and spam folder.") }
                }
            } catch (cancelled: CancellationException) { throw cancelled
            } catch (_: Exception) {
                if (generation == passwordResetGeneration) {
                    _forgotPasswordUiState.update { it.copy(errorMessage = "Could not request a reset link. Check your connection and try again.") }
                }
            } finally {
                if (generation == passwordResetGeneration) _forgotPasswordUiState.update { it.copy(isLoading = false) }
            }
        }
    }
    fun leaveForgotPassword() {
        passwordResetGeneration++
        passwordResetJob?.cancel()
        _forgotPasswordUiState.value = ForgotPasswordUiState()
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
