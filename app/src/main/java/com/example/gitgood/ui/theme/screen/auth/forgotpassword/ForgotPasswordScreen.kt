package com.example.gitgood.ui.theme.screen.auth.forgotpassword

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.gitgood.ui.theme.*

data class ForgotPasswordUiState(
    val email: String = "",
    val isLoading: Boolean = false,
    val errorMessage: String? = null,
    val message: String? = null
)

@Composable
fun ForgotPasswordScreen(
    state: ForgotPasswordUiState,
    onEmailChange: (String) -> Unit,
    onSendResetLink: () -> Unit,
    onBackToLogin: () -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier.fillMaxSize().background(BackgroundColor).imePadding()
            .verticalScroll(rememberScrollState()).padding(horizontal = 28.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp)
    ) {
        IconButton(onClick = onBackToLogin) {
            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back to login", tint = PrimaryTextColor)
        }
        Spacer(Modifier.height(12.dp))
        Text("Forgot your password?", fontSize = 34.sp, lineHeight = 40.sp,
            fontWeight = FontWeight.Medium, letterSpacing = (-1.2).sp, color = PrimaryTextColor)
        Text("Enter your account’s email address. We’ll send you a link to reset your password.",
            color = SecondaryTextColor, fontSize = 15.sp, lineHeight = 22.sp)
        OutlinedTextField(
            value = state.email, onValueChange = onEmailChange,
            modifier = Modifier.fillMaxWidth(), label = { Text("Email address") },
            singleLine = true, enabled = !state.isLoading,
            isError = state.errorMessage != null,
            shape = RoundedCornerShape(14.dp),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Done),
            keyboardActions = KeyboardActions(onDone = {
                if (!state.isLoading && state.email.isNotBlank() && state.message == null) onSendResetLink()
            }),
            colors = OutlinedTextFieldDefaults.colors(
                focusedContainerColor = SurfaceColor, unfocusedContainerColor = SurfaceColor
            )
        )
        state.errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error, fontSize = 14.sp) }
        state.message?.let {
            Surface(color = LightGreen, shape = RoundedCornerShape(14.dp)) {
                Text(it, Modifier.padding(16.dp), color = PrimaryTextColor, fontSize = 14.sp, lineHeight = 21.sp)
            }
        }
        Button(
            onClick = onSendResetLink,
            enabled = !state.isLoading && state.email.isNotBlank() && state.message == null,
            modifier = Modifier.fillMaxWidth().heightIn(min = 54.dp),
            shape = RoundedCornerShape(14.dp)
        ) {
            if (state.isLoading) CircularProgressIndicator(Modifier.size(20.dp), color = OnPrimaryColor, strokeWidth = 2.dp)
            else Text(if (state.message == null) "Send reset link" else "Email requested", fontWeight = FontWeight.SemiBold)
        }
        TextButton(onClick = onBackToLogin, modifier = Modifier.fillMaxWidth()) { Text("Back to login") }
    }
}

@Preview(name = "Forgot password · light", showBackground = true)
@Composable
private fun ForgotPasswordLightPreview() {
    GitGoodTheme(darkTheme = false) { ForgotPasswordScreen(ForgotPasswordUiState(), {}, {}, {}) }
}

@Preview(name = "Forgot password · dark", showBackground = true)
@Composable
private fun ForgotPasswordDarkPreview() {
    GitGoodTheme(darkTheme = true) {
        ForgotPasswordScreen(ForgotPasswordUiState(email = "student@example.com", message = "If an account exists for this email, a password reset link has been sent. Check your inbox and spam folder."), {}, {}, {})
    }
}
