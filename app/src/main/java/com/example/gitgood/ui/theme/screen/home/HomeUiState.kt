package com.example.gitgood.ui.theme.screen.home

import android.net.Uri

data class HomeUiState(
    val selectedImageUri: Uri? = null,
    val description: String = "",
    val selectedVideoUri: Uri? = null
)
