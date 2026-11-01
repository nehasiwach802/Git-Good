package com.example.gitgood.ui.theme.screen.home

import android.net.Uri
import androidx.compose.ui.layout.ContentScale
import coil3.compose.AsyncImage
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.AddPhotoAlternate
import androidx.compose.material.icons.outlined.Image
import androidx.compose.material.icons.outlined.PhotoCamera
import androidx.compose.material.icons.outlined.VideoLibrary
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.compose.ui.unit.dp
import com.example.gitgood.ui.theme.*

@Composable
fun HomeScreen(
    onUploadClick: () -> Unit,
    onTakePhotoClick: () -> Unit,
    onContinueClick: () -> Unit,
    experimentName: String? = null,
    onChangeExperiment: () -> Unit = {},
    selectedImageUri: Uri? = null,
    description: String = "",
    onDescriptionChange: (String) -> Unit = {},
    onRemoveImageClick: () -> Unit = {},
    modifier: Modifier = Modifier,
    errorMessage: String? = null,
    canContinue: Boolean = true,
    onSignOut: () -> Unit = {},
    isSigningOut: Boolean = false,
    selectedVideoUri: Uri? = null,
    onUploadVideoClick: () -> Unit = {},
    onRemoveVideoClick: () -> Unit = {}
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .background(BackgroundColor)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 28.dp)
            .padding(top = 10.dp, bottom = 24.dp),
        verticalArrangement = Arrangement.spacedBy(24.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.End,
            verticalAlignment = Alignment.CenterVertically
        ) {
            TextButton(onClick = onSignOut, enabled = !isSigningOut) {
                Text(if (isSigningOut) "Signing out…" else "Sign out", fontWeight = FontWeight.SemiBold)
            }
        }

        experimentName?.let { name ->
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Selected experiment", fontSize = 12.sp, color = SecondaryTextColor)
                    Text(name, fontSize = 16.sp, fontWeight = FontWeight.Medium, color = PrimaryTextColor)
                }
                TextButton(onClick = onChangeExperiment) { Text("Change", color = PrimaryGreen) }
            }
        }

        Column(
            modifier = Modifier.padding(top = 16.dp, bottom = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                "Add your circuit.",
                fontSize = 34.sp,
                fontWeight = FontWeight.Medium,
                letterSpacing = (-1.3).sp,
                color = PrimaryTextColor
            )
            Text(
                "Choose a photo or video, or take a new photo. Add one attachment at a time.",
                fontSize = 15.sp,
                lineHeight = 22.sp,
                color = SecondaryTextColor
            )
        }

        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Button(
                onClick = onUploadClick,
                modifier = Modifier.fillMaxWidth().heightIn(min = 54.dp),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(containerColor = PrimaryGreen, contentColor = OnPrimaryColor)
            ) {
                Icon(Icons.Outlined.AddPhotoAlternate, contentDescription = null)
                Spacer(Modifier.width(12.dp))
                Text("Upload image", fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
            }
            OutlinedButton(
                onClick = onTakePhotoClick,
                modifier = Modifier.fillMaxWidth().heightIn(min = 54.dp),
                shape = RoundedCornerShape(14.dp),
                border = BorderStroke(1.dp, BorderColor),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = PrimaryGreen)
            ) {
                Icon(Icons.Outlined.PhotoCamera, contentDescription = null)
                Spacer(Modifier.width(12.dp))
                Text("Take photo", fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
            }
            OutlinedButton(
                onClick = onUploadVideoClick,
                modifier = Modifier.fillMaxWidth().heightIn(min = 54.dp),
                shape = RoundedCornerShape(14.dp),
                border = BorderStroke(1.dp, BorderColor)
            ) {
                Icon(Icons.Outlined.VideoLibrary, contentDescription = null)
                Spacer(Modifier.width(12.dp))
                Text("Upload video", fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
            }
        }

        Surface(
            modifier = Modifier.fillMaxWidth().heightIn(min = 240.dp),
            shape = RoundedCornerShape(12.dp),
            color = SurfaceColor,
            border = BorderStroke(1.dp, BorderColor)
        ) {
            if (selectedVideoUri != null) {
                VideoPreview(uri = selectedVideoUri, modifier = Modifier.fillMaxWidth())
            } else if (selectedImageUri != null) {
                AsyncImage(
                    model = selectedImageUri,
                    contentDescription = "Selected image preview",
                    modifier = Modifier.fillMaxWidth().height(240.dp),
                    contentScale = ContentScale.Fit
                )
            } else Column(
                modifier = Modifier.padding(24.dp),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Icon(
                    Icons.Outlined.Image,
                    contentDescription = null,
                    modifier = Modifier.size(44.dp),
                    tint = PrimaryGreen
                )
                Spacer(Modifier.height(16.dp))
                Text("Your photo or video preview", fontSize = 14.sp, fontWeight = FontWeight.Medium, color = PrimaryTextColor)
                Spacer(Modifier.height(8.dp))
                Text("No attachment selected yet", fontSize = 13.sp, color = SecondaryTextColor)
            }
        }

        if (selectedImageUri != null) {
            TextButton(onClick = onRemoveImageClick, modifier = Modifier.align(Alignment.End)) {
                Text("Remove image", color = PrimaryGreen)
            }
        }

        if (selectedVideoUri != null) {
            TextButton(onClick = onRemoveVideoClick, modifier = Modifier.align(Alignment.End)) {
                Text("Remove video")
            }
            Surface(color = LightGreen, shape = RoundedCornerShape(12.dp)) {
                Text("Video selected. You can preview it here. Video analysis is not available yet; choose a photo to continue with circuit review.",
                    modifier = Modifier.padding(14.dp), color = PrimaryTextColor, fontSize = 13.sp, lineHeight = 19.sp)
            }
        }

        Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
            Text(
                "Description",
                fontSize = 14.sp,
                fontWeight = FontWeight.Medium,
                color = PrimaryTextColor
            )
            OutlinedTextField(
                value = description,
                onValueChange = onDescriptionChange,
                modifier = Modifier.fillMaxWidth(),
                placeholder = { Text("Describe your circuit or what you want to check", fontSize = 14.sp) },
                isError = description.codePointCount(0, description.length) > 2000,
                supportingText = {
                    Text("Required · ${description.codePointCount(0, description.length)}/2000 characters" +
                        if (selectedVideoUri == null) " · Photos: JPEG/PNG, up to 5 MiB and 20 megapixels" else "")
                },
                minLines = 3,
                maxLines = 5,
                shape = RoundedCornerShape(12.dp),
                textStyle = MaterialTheme.typography.bodyMedium.copy(color = PrimaryTextColor),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = PrimaryGreen,
                    unfocusedBorderColor = BorderColor,
                    focusedContainerColor = SurfaceColor,
                    unfocusedContainerColor = SurfaceColor,
                    cursorColor = PrimaryGreen,
                    focusedPlaceholderColor = SecondaryTextColor,
                    unfocusedPlaceholderColor = SecondaryTextColor
                )
            )
        }

        errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error) }

        Button(
            onClick = onContinueClick,
            enabled = canContinue && selectedVideoUri == null && selectedImageUri != null && description.isNotBlank() && description.codePointCount(0, description.length) <= 2000,
            modifier = Modifier.fillMaxWidth().heightIn(min = 54.dp),
            shape = RoundedCornerShape(14.dp),
            colors = ButtonDefaults.buttonColors(containerColor = PrimaryGreen)
        ) {
            Text(if (selectedVideoUri != null) "Video analysis coming soon" else "Continue", fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
        }
    }
}

@Preview(showBackground = true, showSystemUi = true)
@Composable
private fun HomeScreenPreview() {
    GitGoodTheme {
        HomeScreen(onUploadClick = {}, onTakePhotoClick = {}, onContinueClick = {})
    }
}
