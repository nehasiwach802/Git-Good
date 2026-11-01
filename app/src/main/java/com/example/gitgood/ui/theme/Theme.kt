package com.example.gitgood.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

internal val CircuitlyDarkColors = darkColorScheme(
    primary = Color(0xFF69DDB8), onPrimary = Color(0xFF00382B),
    primaryContainer = Color(0xFF16483C), onPrimaryContainer = Color(0xFFC5F9E8),
    secondary = Color(0xFFA9C9DA), onSecondary = Color(0xFF143441),
    secondaryContainer = Color(0xFF233D4B), onSecondaryContainer = Color(0xFFD5EAF4),
    tertiary = Color(0xFFD5C1F5), onTertiary = Color(0xFF392751),
    background = Color(0xFF0C151D), onBackground = Color(0xFFE5EDF3),
    surface = Color(0xFF16232E), onSurface = Color(0xFFE5EDF3),
    surfaceVariant = Color(0xFF23343F), onSurfaceVariant = Color(0xFFB3C5D0),
    surfaceContainerLowest = Color(0xFF091118), surfaceContainerLow = Color(0xFF111E28),
    surfaceContainer = Color(0xFF16232E), surfaceContainerHigh = Color(0xFF1E2D39),
    surfaceContainerHighest = Color(0xFF283946),
    outline = Color(0xFF8299A7), outlineVariant = Color(0xFF364D5A),
    error = Color(0xFFFFB4AB), onError = Color(0xFF690005),
    errorContainer = Color(0xFF572020), onErrorContainer = Color(0xFFFFDAD5),
    inverseSurface = Color(0xFFE5EDF3), inverseOnSurface = Color(0xFF16232E),
    inversePrimary = Color(0xFF006B53), surfaceTint = Color(0xFF69DDB8)
)

internal val CircuitlyLightColors = lightColorScheme(
    primary = Color(0xFF006B53), onPrimary = Color.White,
    primaryContainer = Color(0xFFCDEFE2), onPrimaryContainer = Color(0xFF00382B),
    secondary = Color(0xFF3F6073), onSecondary = Color.White,
    secondaryContainer = Color(0xFFD3E6F1), onSecondaryContainer = Color(0xFF173543),
    tertiary = Color(0xFF6A5288), onTertiary = Color.White,
    background = Color(0xFFEAF0F4), onBackground = Color(0xFF172B38),
    surface = Color(0xFFF8FAFC), onSurface = Color(0xFF172B38),
    surfaceVariant = Color(0xFFDEE8EE), onSurfaceVariant = Color(0xFF445C6B),
    surfaceContainerLowest = Color.White, surfaceContainerLow = Color(0xFFF1F6F9),
    surfaceContainer = Color(0xFFE4EDF3), surfaceContainerHigh = Color(0xFFDCE7EE),
    surfaceContainerHighest = Color(0xFFD2DFE8),
    outline = Color(0xFF6B8291), outlineVariant = Color(0xFFBDCED9),
    error = Color(0xFFB3261E), onError = Color.White,
    errorContainer = Color(0xFFFFDAD5), onErrorContainer = Color(0xFF410002),
    inverseSurface = Color(0xFF21333F), inverseOnSurface = Color(0xFFEDF3F7),
    inversePrimary = Color(0xFF69DDB8), surfaceTint = Color(0xFF006B53)
)

@Composable
fun GitGoodTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit
) {
    val colors = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        darkTheme -> CircuitlyDarkColors
        else -> CircuitlyLightColors
    }
    MaterialTheme(colorScheme = colors, typography = Typography, content = content)
}
