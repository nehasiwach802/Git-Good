package com.example.gitgood.ui.theme

import androidx.compose.ui.graphics.Color
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow

class ThemeContrastTest {
    @Test fun darkThemeTextHasReadableContrast() = checkTheme(CircuitlyDarkColors)
    @Test fun lightThemeTextHasReadableContrast() = checkTheme(CircuitlyLightColors)

    private fun checkTheme(colors: androidx.compose.material3.ColorScheme) {
        listOf(
            "body" to (colors.onSurface to colors.surface),
            "background" to (colors.onBackground to colors.background),
            "secondary" to (colors.onSurfaceVariant to colors.surface),
            "accent" to (colors.primary to colors.background),
            "button" to (colors.onPrimary to colors.primary),
            "user message" to (colors.onSurface to colors.primaryContainer)
        ).forEach { (label, pair) ->
            val contrast = (max(luminance(pair.first), luminance(pair.second)) + .05) /
                (min(luminance(pair.first), luminance(pair.second)) + .05)
            assertTrue("$label contrast $contrast must be at least 4.5:1", contrast >= 4.5)
        }
    }
    private fun luminance(color: Color): Double {
        fun channel(value: Float): Double = if (value <= .04045) value / 12.92 else ((value + .055) / 1.055).pow(2.4)
        return .2126 * channel(color.red) + .7152 * channel(color.green) + .0722 * channel(color.blue)
    }
}
