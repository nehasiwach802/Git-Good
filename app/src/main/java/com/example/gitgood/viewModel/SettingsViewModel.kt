package com.example.gitgood.viewModel

import androidx.lifecycle.ViewModel
import com.example.gitgood.data.preferences.ThemePreferences
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel @Inject constructor(private val preferences: ThemePreferences) : ViewModel() {
    val darkTheme = preferences.darkTheme
    fun setDarkTheme(enabled: Boolean) = preferences.setDarkTheme(enabled)
}
