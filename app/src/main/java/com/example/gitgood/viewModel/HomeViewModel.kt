package com.example.gitgood.viewModel

import android.net.Uri
import androidx.lifecycle.ViewModel
import com.example.gitgood.ui.theme.screen.home.HomeUiState
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

@HiltViewModel
class HomeViewModel @Inject constructor() : ViewModel() {
    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState = _uiState.asStateFlow()

    fun reset() { _uiState.value = HomeUiState() }

    fun onDescriptionChange(description: String) {
        _uiState.update { it.copy(description = description) }
    }

    fun selectImage(uri: Uri) {
        _uiState.update { it.copy(selectedImageUri = uri, selectedVideoUri = null) }
    }

    fun selectVideo(uri: Uri) {
        _uiState.update { it.copy(selectedVideoUri = uri, selectedImageUri = null) }
    }

    fun removeVideo() {
        _uiState.update { it.copy(selectedVideoUri = null) }
    }

    fun removeImage() {
        _uiState.update { it.copy(selectedImageUri = null) }
    }
}
