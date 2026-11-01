package com.example.gitgood.data.preferences

import android.content.Context
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

/** Device-level preference: follow the system until the user makes a choice. */
@Singleton
class ThemePreferences @Inject constructor(@ApplicationContext context: Context) {
    private val preferences = context.getSharedPreferences("circuitly_settings", Context.MODE_PRIVATE)
    private val _darkTheme = MutableStateFlow<Boolean?>(
        if (preferences.contains("dark_theme")) preferences.getBoolean("dark_theme", false) else null
    )
    val darkTheme = _darkTheme.asStateFlow()

    fun setDarkTheme(enabled: Boolean) {
        preferences.edit().putBoolean("dark_theme", enabled).apply()
        _darkTheme.value = enabled
    }
}
