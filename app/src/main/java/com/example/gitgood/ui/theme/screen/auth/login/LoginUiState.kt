package com.example.gitgood.ui.screen.auth.login

data class LoginUiState(
    val email: String = "",
    val password: String = "",
    val isPasswordVisible: Boolean = false,
    val errorMessage: String? = null,
    val message: String? = null,
    val isLoading: Boolean = false
)