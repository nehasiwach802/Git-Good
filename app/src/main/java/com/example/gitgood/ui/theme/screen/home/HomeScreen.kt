package com.example.gitgood.ui.theme.screen.home

import android.net.Uri
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.VideoLibrary
import androidx.compose.material.icons.outlined.Videocam
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.gitgood.ui.theme.*

@Composable
fun HomeScreen(
    onUploadVideoClick: () -> Unit,
    onRecordVideoClick: () -> Unit,
    onContinueClick: () -> Unit = {},
    experimentAvailable: Boolean = true,
    experimentName: String? = null,
    onChangeExperiment: () -> Unit = {},
    selectedVideoUri: Uri? = null,
    description: String = "",
    onDescriptionChange: (String) -> Unit = {},
    onRemoveVideoClick: () -> Unit = {},
    onSignOut: () -> Unit = {},
    isSigningOut: Boolean = false,
    darkTheme: Boolean = false,
    onDarkThemeChange: (Boolean) -> Unit = {},
    isRecording: Boolean = false,
    errorMessage: String? = null,
    modifier: Modifier = Modifier
) {
    var settingsOpen by rememberSaveable { mutableStateOf(false) }
    if (settingsOpen) {
        HomeSettingsSheet(
            darkTheme = darkTheme,
            onDarkThemeChange = onDarkThemeChange,
            onSignOut = { settingsOpen = false; onSignOut() },
            onDismiss = { settingsOpen = false },
            isSigningOut = isSigningOut
        )
    }
    Column(
        modifier.fillMaxSize().background(BackgroundColor)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 28.dp).padding(top = 10.dp, bottom = 24.dp),
        verticalArrangement = Arrangement.spacedBy(24.dp)
    ) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
            TextButton(onClick = { settingsOpen = true }, enabled = !isSigningOut && !isRecording) {
                Icon(Icons.Outlined.Settings, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(8.dp))
                Text("Settings", fontWeight = FontWeight.SemiBold)
            }
        }
        experimentName?.let { name ->
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Selected experiment", fontSize = 12.sp, color = SecondaryTextColor)
                    Text(name, fontSize = 16.sp, fontWeight = FontWeight.Medium, color = PrimaryTextColor)
                }
                TextButton(onClick = onChangeExperiment, enabled = !isRecording) { Text("Change") }
            }
        }
        Column(Modifier.padding(top = 16.dp, bottom = 12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Add a circuit video.", fontSize = 34.sp, lineHeight = 40.sp,
                fontWeight = FontWeight.Medium, letterSpacing = (-1.3).sp, color = PrimaryTextColor)
            Text("Upload a video or record your circuit using the camera.",
                fontSize = 15.sp, lineHeight = 22.sp, color = SecondaryTextColor)
        }
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Button(
                onClick = onUploadVideoClick, enabled = !isRecording && !isSigningOut,
                modifier = Modifier.fillMaxWidth().heightIn(min = 54.dp), shape = RoundedCornerShape(14.dp)
            ) {
                Icon(Icons.Outlined.VideoLibrary, contentDescription = null)
                Spacer(Modifier.width(12.dp))
                Text("Upload video", fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
            }
            OutlinedButton(
                onClick = onRecordVideoClick, enabled = !isRecording && !isSigningOut,
                modifier = Modifier.fillMaxWidth().heightIn(min = 54.dp), shape = RoundedCornerShape(14.dp),
                border = BorderStroke(1.dp, BorderColor)
            ) {
                Icon(Icons.Outlined.Videocam, contentDescription = null)
                Spacer(Modifier.width(12.dp))
                Text(if (isRecording) "Recording…" else "Record video", fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
            }
        }
        Surface(
            modifier = Modifier.fillMaxWidth().heightIn(min = 240.dp),
            shape = RoundedCornerShape(12.dp), color = SurfaceColor, border = BorderStroke(1.dp, BorderColor)
        ) {
            if (selectedVideoUri != null) {
                VideoPreview(uri = selectedVideoUri, modifier = Modifier.fillMaxWidth())
            } else {
                Column(Modifier.padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center) {
                    Icon(Icons.Outlined.Videocam, contentDescription = null, modifier = Modifier.size(44.dp), tint = PrimaryGreen)
                    Spacer(Modifier.height(16.dp))
                    Text("Your video preview", fontSize = 14.sp, fontWeight = FontWeight.Medium, color = PrimaryTextColor)
                    Spacer(Modifier.height(8.dp))
                    Text("No video selected yet", fontSize = 13.sp, color = SecondaryTextColor)
                }
            }
        }
        if (selectedVideoUri != null) {
            TextButton(onClick = onRemoveVideoClick, enabled = !isRecording, modifier = Modifier.align(Alignment.End)) { Text("Remove video") }
        }
        Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
            Text("Description", fontSize = 14.sp, fontWeight = FontWeight.Medium, color = PrimaryTextColor)
            OutlinedTextField(
                value = description, onValueChange = onDescriptionChange, modifier = Modifier.fillMaxWidth(),
                placeholder = { Text("Describe your circuit or what you want to check", fontSize = 14.sp) },
                isError = description.codePointCount(0, description.length) > 2000,
                supportingText = { Text("Required · ${description.codePointCount(0, description.length)}/2000 characters") },
                minLines = 3, maxLines = 5, shape = RoundedCornerShape(12.dp),
                colors = OutlinedTextFieldDefaults.colors(focusedContainerColor = SurfaceColor, unfocusedContainerColor = SurfaceColor)
            )
        }
        errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Surface(color = LightGreen, shape = RoundedCornerShape(12.dp)) {
            Text("MP4 video · up to 60 seconds and 50 MiB. Keep the circuit steady and clearly visible; 1080p is recommended.",
                modifier = Modifier.padding(14.dp), color = PrimaryTextColor, fontSize = 13.sp, lineHeight = 19.sp)
        }
        Button(onClick = onContinueClick,
            enabled = experimentAvailable && selectedVideoUri != null && !isRecording && !isSigningOut &&
                description.isNotBlank() && description.codePointCount(0, description.length) <= 2000,
            modifier = Modifier.fillMaxWidth().heightIn(min = 54.dp), shape = RoundedCornerShape(14.dp)) {
            Text("Continue", fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
        }
    }
}

@Preview(name = "Video home · light", showBackground = true, showSystemUi = true)
@Composable
private fun HomeLightPreview() {
    GitGoodTheme(darkTheme = false) { HomeScreen(onUploadVideoClick = {}, onRecordVideoClick = {}) }
}

@Preview(name = "Video home · dark", showBackground = true, showSystemUi = true)
@Composable
private fun HomeDarkPreview() {
    GitGoodTheme(darkTheme = true) { HomeScreen(onUploadVideoClick = {}, onRecordVideoClick = {}, darkTheme = true) }
}
