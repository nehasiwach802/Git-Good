package com.example.gitgood.navigation

import androidx.navigation3.runtime.NavKey
import kotlinx.serialization.Serializable

@Serializable
sealed interface ScreenRoute : NavKey {
    @Serializable
    sealed interface Auth : ScreenRoute {
        @Serializable data object Splash : Auth
        @Serializable data object Landing : Auth
        @Serializable data object Login : Auth
        @Serializable data object Register : Auth
    }
    @Serializable data object Home : ScreenRoute
}
