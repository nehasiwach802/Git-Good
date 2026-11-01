package com.example.gitgood.viewModel

import android.net.Uri
import androidx.lifecycle.ViewModel
import com.example.gitgood.ui.theme.screen.home.HomeUiState
import dagger.hilt.android.lifecycle.HiltViewModel
import java.io.File
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

@HiltViewModel
class HomeViewModel @Inject constructor() : ViewModel() {
    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState = _uiState.asStateFlow()
    // Only camera files created by this app are owned here. Gallery videos are never deleted.
    private var recordedVideoPath: String? = null

    fun reset() {
        releaseRecording()
        _uiState.value = HomeUiState()
    }
    fun onDescriptionChange(description: String) {
        _uiState.update { it.copy(description = description) }
    }
    fun selectVideo(uri: Uri, recordedPath: String? = null) {
        if (recordedVideoPath != recordedPath) releaseRecording()
        recordedVideoPath = recordedPath
        _uiState.update { it.copy(selectedVideoUri = uri) }
    }
    fun removeVideo() {
        releaseRecording()
        _uiState.update { it.copy(selectedVideoUri = null) }
    }
    private fun releaseRecording() {
        recordedVideoPath?.let { File(it).delete() }
        recordedVideoPath = null
    }
    override fun onCleared() { releaseRecording() }
}
