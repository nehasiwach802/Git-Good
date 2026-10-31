package com.example.gitgood

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.navigation3.rememberViewModelStoreNavEntryDecorator
import androidx.navigation3.runtime.entryProvider
import androidx.navigation3.runtime.rememberNavBackStack
import androidx.navigation3.runtime.rememberSaveableStateHolderNavEntryDecorator
import androidx.navigation3.ui.NavDisplay
import com.example.gitgood.navigation.HomeDestination
import com.example.gitgood.navigation.RegisterDestination
import com.example.gitgood.navigation.ScreenRoute
import com.example.gitgood.ui.screen.auth.login.LoginScreenLayout
import com.example.gitgood.ui.theme.GitGoodTheme
import com.example.gitgood.ui.theme.screen.CircuitlySplashScreen
import com.example.gitgood.ui.theme.screen.auth.loading.CircuitlyWelcomeScreenLayout
import com.example.gitgood.viewModel.LoginViewModel
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    private val loginViewModel: LoginViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            GitGoodTheme {
                val user by loginViewModel.currentUser.collectAsStateWithLifecycle()
                val loginState by loginViewModel.loginUiState.collectAsStateWithLifecycle()
                val context = LocalContext.current
                val backStack = rememberNavBackStack(ScreenRoute.Auth.Splash)

                LaunchedEffect(user?.uid) {
                    if (user != null) {
                        backStack.clear()
                        backStack.add(ScreenRoute.Home)
                    } else if (backStack.lastOrNull() == ScreenRoute.Auth.Splash ||
                        backStack.any { it == ScreenRoute.Home }) {
                        backStack.clear()
                        backStack.add(ScreenRoute.Auth.Landing)
                    }
                }

                Scaffold { padding ->
                    NavDisplay(
                        backStack = backStack,
                        modifier = Modifier.fillMaxSize().padding(padding),
                        onBack = {
                            if (backStack.size > 1) {
                                loginViewModel.clearMessage()
                                backStack.removeAt(backStack.lastIndex)
                            }
                        },
                        entryDecorators = listOf(
                            rememberSaveableStateHolderNavEntryDecorator(),
                            rememberViewModelStoreNavEntryDecorator()
                        ),
                        entryProvider = entryProvider {
                            entry<ScreenRoute.Auth.Splash> { CircuitlySplashScreen() }
                            entry<ScreenRoute.Auth.Landing> {
                                CircuitlyWelcomeScreenLayout(
                                    onGetStartedClick = { backStack.add(ScreenRoute.Auth.Register) },
                                    onLoginClick = { backStack.add(ScreenRoute.Auth.Login) }
                                )
                            }
                            entry<ScreenRoute.Auth.Login> {
                                LoginScreenLayout(
                                    uiState = loginState,
                                    onEmailChange = loginViewModel::onEmailChange,
                                    onPasswordChange = loginViewModel::onPasswordChange,
                                    onPasswordVisibilityToggle = loginViewModel::togglePasswordVisibility,
                                    onLoginClick = loginViewModel::onLoginClick,
                                    onForgotPasswordClick = loginViewModel::onForgotPasswordClick,
                                    onSignUpClick = {
                                        loginViewModel.clearMessage()
                                        backStack.removeAt(backStack.lastIndex)
                                        backStack.add(ScreenRoute.Auth.Register)
                                    },
                                    onBackClick = {
                                        if (backStack.size > 1) backStack.removeAt(backStack.lastIndex)
                                    },
                                    onGoogleClick = { loginViewModel.onGoogleClick(context) }
                                )
                            }
                            entry<ScreenRoute.Auth.Register> {
                                RegisterDestination(loginViewModel, onLogin = {
                                    loginViewModel.clearMessage()
                                    backStack.removeAt(backStack.lastIndex)
                                    backStack.add(ScreenRoute.Auth.Login)
                                })
                            }
                            entry<ScreenRoute.Home> { HomeDestination(loginViewModel) }
                        }
                    )
                }
            }
        }
    }
}
