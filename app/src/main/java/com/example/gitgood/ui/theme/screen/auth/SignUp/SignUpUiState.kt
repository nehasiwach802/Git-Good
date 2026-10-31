package com.example.gitgood.ui.screen.auth.register
data class RegisterUiState(
    val email: String = "",
    val password: String = "",
    val confirmPassword: String = "",

    val isPasswordVisible: Boolean = false,
    val isConfirmPasswordVisible: Boolean = false,

    val isLoading: Boolean = false,

)
