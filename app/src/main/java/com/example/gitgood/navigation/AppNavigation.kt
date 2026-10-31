package com.example.gitgood.navigation

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.gitgood.ui.screen.auth.register.RegisterScreenLayout
import com.example.gitgood.ui.screen.auth.register.RegisterUiState
import com.example.gitgood.viewModel.LoginViewModel

@Composable
fun RegisterDestination(viewModel: LoginViewModel, onLogin: () -> Unit) {
    val state by viewModel.loginUiState.collectAsStateWithLifecycle()
    val context = LocalContext.current
    var email by rememberSaveable { mutableStateOf("") }
    // Passwords remain in memory and are discarded when this destination is removed.
    var password by remember { mutableStateOf("") }
    var confirmation by remember { mutableStateOf("") }
    var showPassword by remember { mutableStateOf(false) }
    var showConfirmation by remember { mutableStateOf(false) }
    Column {
        state.errorMessage?.let {
            Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(16.dp))
        }
        RegisterScreenLayout(
            uiState = RegisterUiState(email, password, confirmation, showPassword, showConfirmation, state.isLoading),
            onEmailInput = { email = it },
            onPasswordInput = { password = it },
            onConfirmPasswordInput = { confirmation = it },
            onPasswordVisibilityToggle = { showPassword = !showPassword },
            onConfirmPasswordVisibilityToggle = { showConfirmation = !showConfirmation },
            onSignUpClick = { viewModel.onSignUpClick(email, password, confirmation) },
            onGoogleClick = { viewModel.onGoogleClick(context) },
            onLoginClick = onLogin
        )
    }
}

@Composable
fun HomeDestination(viewModel: LoginViewModel) {
    val state by viewModel.loginUiState.collectAsStateWithLifecycle()
    val user by viewModel.currentUser.collectAsStateWithLifecycle()
    val context = LocalContext.current
    Column(Modifier.padding(24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("Welcome to Git Good", style = MaterialTheme.typography.headlineMedium)
        Text(user?.email ?: "Signed in")
        state.errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Button(onClick = { viewModel.signOut(context) }, enabled = !state.isLoading) {
            Text("Sign out")
        }
    }
}
