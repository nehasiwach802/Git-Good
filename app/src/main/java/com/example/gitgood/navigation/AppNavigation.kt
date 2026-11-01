package com.example.gitgood.navigation

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.MediaStore
import com.example.gitgood.data.backend.VideoUploadLimits
import androidx.core.content.FileProvider
import java.io.File
import java.io.IOException
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import com.example.gitgood.viewModel.HomeViewModel
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
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
import com.example.gitgood.ui.theme.screen.home.HomeScreen
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
fun HomeDestination(
    viewModel: LoginViewModel,
    homeViewModel: HomeViewModel,
    experimentName: String? = null,
    onChangeExperiment: () -> Unit = {},
    catalogError: String? = null,
    onContinue: () -> Unit = {},
    experimentAvailable: Boolean = true,
    darkTheme: Boolean = false,
    onDarkThemeChange: (Boolean) -> Unit = {}
) {
    val state by viewModel.loginUiState.collectAsStateWithLifecycle()
    val homeState by homeViewModel.uiState.collectAsStateWithLifecycle()
    val context = LocalContext.current
    // Retain the output location while the external camera recreates the activity.
    var pendingVideoPath by rememberSaveable { mutableStateOf<String?>(null) }
    var cameraError by rememberSaveable { mutableStateOf<String?>(null) }
    val camera = rememberLauncherForActivityResult(object : ActivityResultContracts.CaptureVideo() {
        override fun createIntent(context: Context, input: Uri): Intent = super.createIntent(context, input).apply {
            putExtra(MediaStore.EXTRA_DURATION_LIMIT, 60)
            putExtra(MediaStore.EXTRA_SIZE_LIMIT, VideoUploadLimits.MAX_BYTES)
        }
    }) { success ->
        val video = pendingVideoPath?.let(::File)
        pendingVideoPath = null
        if (success && video != null && video.length() > 0L) {
            homeViewModel.selectVideo(
                FileProvider.getUriForFile(context, "${context.packageName}.camera.files", video),
                recordedPath = video.absolutePath
            )
            cameraError = null
        } else {
            video?.delete()
            if (success) cameraError = "The camera could not save the video. Please try again."
        }
    }
    val videoPicker = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        if (uri != null) {
            homeViewModel.selectVideo(uri)
            cameraError = null
        }
    }
    HomeScreen(
        onContinueClick = onContinue,
        experimentAvailable = experimentAvailable,
        onSignOut = { viewModel.signOut(context) },
        isSigningOut = state.isLoading,
        darkTheme = darkTheme,
        onDarkThemeChange = onDarkThemeChange,
        experimentName = experimentName,
        onChangeExperiment = onChangeExperiment,
        selectedVideoUri = homeState.selectedVideoUri,
        onRemoveVideoClick = homeViewModel::removeVideo,
        onUploadVideoClick = {
            try {
                videoPicker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.VideoOnly))
            } catch (_: Exception) {
                cameraError = "Could not open the video picker. Please try again."
            }
        },
        onRecordVideoClick = {
            if (pendingVideoPath == null) {
                cameraError = null
                try {
                    val directory = File(context.cacheDir, "videos")
                    if (!directory.isDirectory && !directory.mkdirs()) {
                        throw IOException("Could not create video directory")
                    }
                    val video = File.createTempFile("recording_", ".mp4", directory)
                    pendingVideoPath = video.absolutePath
                    val uri = FileProvider.getUriForFile(context, "${context.packageName}.camera.files", video)
                    camera.launch(uri)
                } catch (_: ActivityNotFoundException) {
                    pendingVideoPath?.let { File(it).delete() }
                    pendingVideoPath = null
                    cameraError = "No video camera app is available on this device."
                } catch (_: Exception) {
                    pendingVideoPath?.let { File(it).delete() }
                    pendingVideoPath = null
                    cameraError = "Could not open the video camera. Please try again."
                }
            }
        },
        isRecording = pendingVideoPath != null,
        description = homeState.description,
        onDescriptionChange = homeViewModel::onDescriptionChange,
        errorMessage = cameraError ?: catalogError ?: state.errorMessage
    )
}
