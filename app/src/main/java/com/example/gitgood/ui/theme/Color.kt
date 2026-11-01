package com.example.gitgood.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// All screen colors follow the same scheme, including legacy auth screens.
val BackgroundColor: Color @Composable get() = MaterialTheme.colorScheme.background
val SurfaceColor: Color @Composable get() = MaterialTheme.colorScheme.surface
val PrimaryTextColor: Color @Composable get() = MaterialTheme.colorScheme.onSurface
val SecondaryTextColor: Color @Composable get() = MaterialTheme.colorScheme.onSurfaceVariant
val PrimaryGreen: Color @Composable get() = MaterialTheme.colorScheme.primary
val OnPrimaryColor: Color @Composable get() = MaterialTheme.colorScheme.onPrimary
val LightGreen: Color @Composable get() = MaterialTheme.colorScheme.primaryContainer
val BorderColor: Color @Composable get() = MaterialTheme.colorScheme.outlineVariant
