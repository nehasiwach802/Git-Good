package com.example.gitgood.navigation

import android.content.ActivityNotFoundException
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
    onContinue: () -> Unit = {},
    experimentAvailable: Boolean = true,
    catalogError: String? = null
) {
    val state by viewModel.loginUiState.collectAsStateWithLifecycle()
    val homeState by homeViewModel.uiState.collectAsStateWithLifecycle()
    val context = LocalContext.current
    // Save the destination across activity recreation while the camera is open.
    var pendingPhotoPath by rememberSaveable { mutableStateOf<String?>(null) }
    var cameraError by rememberSaveable { mutableStateOf<String?>(null) }
    val camera = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { success ->
        val photo = pendingPhotoPath?.let(::File)
        pendingPhotoPath = null
        if (success && photo != null && photo.length() > 0L) {
            homeViewModel.selectImage(
                FileProvider.getUriForFile(context, "${context.packageName}.camera.files", photo)
            )
            cameraError = null
        } else {
            photo?.delete()
            if (success) cameraError = "The camera could not save the photo. Please try again."
        }
    }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        if (uri != null) {
            homeViewModel.selectImage(uri)
            cameraError = null
        }
    }
    val videoPicker = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        if (uri != null) {
            homeViewModel.selectVideo(uri)
            cameraError = null
        }
    }
    HomeScreen(
        onSignOut = { viewModel.signOut(context) },
        isSigningOut = state.isLoading,
        experimentName = experimentName,
        onChangeExperiment = onChangeExperiment,
        selectedImageUri = homeState.selectedImageUri,
        selectedVideoUri = homeState.selectedVideoUri,
        onRemoveVideoClick = homeViewModel::removeVideo,
        onUploadVideoClick = {
            try {
                videoPicker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.VideoOnly))
            } catch (_: Exception) {
                cameraError = "Could not open the video picker. Please try again."
            }
        },
        description = homeState.description,
        onDescriptionChange = homeViewModel::onDescriptionChange,
        onRemoveImageClick = homeViewModel::removeImage,
        onUploadClick = {
            picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
        },
        onTakePhotoClick = {
            if (pendingPhotoPath == null) {
                cameraError = null
                try {
                    val directory = File(context.cacheDir, "camera")
                    if (!directory.exists() && !directory.mkdirs()) {
                        throw IOException("Could not create photo directory")
                    }
                    val photo = File.createTempFile("capture_", ".jpg", directory)
                    pendingPhotoPath = photo.absolutePath
                    val uri = FileProvider.getUriForFile(
                        context, "${context.packageName}.camera.files", photo
                    )
                    camera.launch(uri)
                } catch (_: ActivityNotFoundException) {
                    pendingPhotoPath?.let { File(it).delete() }
                    pendingPhotoPath = null
                    cameraError = "No camera app is available on this device."
                } catch (_: Exception) {
                    pendingPhotoPath?.let { File(it).delete() }
                    pendingPhotoPath = null
                    cameraError = "Could not open the camera. Please try again."
                }
            }
        },
        onContinueClick = onContinue,
        canContinue = experimentAvailable,
        errorMessage = cameraError ?: catalogError ?: state.errorMessage
    )
}
