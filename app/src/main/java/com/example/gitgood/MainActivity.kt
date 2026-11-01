package com.example.gitgood

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.SystemBarStyle
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.SideEffect
import com.example.gitgood.viewModel.SettingsViewModel
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
import com.example.gitgood.ui.theme.screen.auth.forgotpassword.ForgotPasswordScreen
import com.example.gitgood.ui.theme.GitGoodTheme
import com.example.gitgood.ui.theme.screen.CircuitlySplashScreen
import com.example.gitgood.ui.theme.screen.auth.loading.CircuitlyWelcomeScreenLayout
import com.example.gitgood.viewModel.ConversationViewModel
import com.example.gitgood.ui.theme.screen.conversation.ConversationScreen
import com.example.gitgood.ui.theme.screen.conversation.SessionActions
import androidx.compose.runtime.DisposableEffect
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.example.gitgood.viewModel.ExperimentViewModel
import com.example.gitgood.ui.theme.screen.experiment.ExperimentScreen
import com.example.gitgood.viewModel.HomeViewModel
import com.example.gitgood.viewModel.LoginViewModel
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    private val conversationViewModel: ConversationViewModel by viewModels()
    private val experimentViewModel: ExperimentViewModel by viewModels()
    private val homeViewModel: HomeViewModel by viewModels()
    private val loginViewModel: LoginViewModel by viewModels()
    private val settingsViewModel: SettingsViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val savedDarkTheme by settingsViewModel.darkTheme.collectAsStateWithLifecycle()
            val darkTheme = savedDarkTheme ?: isSystemInDarkTheme()
            SideEffect {
                enableEdgeToEdge(
                    statusBarStyle = SystemBarStyle.auto(android.graphics.Color.TRANSPARENT, android.graphics.Color.TRANSPARENT) { darkTheme },
                    navigationBarStyle = SystemBarStyle.auto(0xE6FFFFFF.toInt(), 0x801B1B1B.toInt()) { darkTheme }
                )
            }
            GitGoodTheme(darkTheme = darkTheme) {
                val user by loginViewModel.currentUser.collectAsStateWithLifecycle()
                val loginState by loginViewModel.loginUiState.collectAsStateWithLifecycle()
                val catalog by experimentViewModel.experiments.collectAsStateWithLifecycle()
                val selectedId by experimentViewModel.selectedId.collectAsStateWithLifecycle()
                val catalogError by experimentViewModel.error.collectAsStateWithLifecycle()
                val selectedExperiment = catalog.find { it.id == selectedId }
                val context = LocalContext.current
                val backStack = rememberNavBackStack(ScreenRoute.Auth.Splash)

                LaunchedEffect(user?.uid) {
                    conversationViewModel.resetForAccount(user?.uid)
                    if (user == null) {
                        homeViewModel.reset()
                        experimentViewModel.clear()
                        if (backStack.lastOrNull() == ScreenRoute.Auth.Splash ||
                            backStack.any { it == ScreenRoute.Home || it == ScreenRoute.Experiments || it == ScreenRoute.Conversation }) {
                            backStack.clear()
                            backStack.add(ScreenRoute.Auth.Landing)
                        }
                    } else if (backStack.any { it is ScreenRoute.Auth }) {
                        backStack.clear()
                        backStack.add(ScreenRoute.Experiments)
                    }
                    if (user != null) experimentViewModel.refresh()
                }

                Scaffold { padding ->
                    NavDisplay(
                        backStack = backStack,
                        modifier = Modifier.fillMaxSize().padding(padding),
                        onBack = {
                            if (backStack.lastOrNull() == ScreenRoute.Conversation) {
                                conversationViewModel.exit()
                            } else if (backStack.size > 1) {
                                if (backStack.lastOrNull() == ScreenRoute.Auth.ForgotPassword) loginViewModel.leaveForgotPassword()
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
                                    onForgotPasswordClick = {
                                        loginViewModel.openForgotPassword()
                                        backStack.add(ScreenRoute.Auth.ForgotPassword)
                                    },
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
                            entry<ScreenRoute.Auth.ForgotPassword> {
                                val resetState by loginViewModel.forgotPasswordUiState.collectAsStateWithLifecycle()
                                ForgotPasswordScreen(
                                    state = resetState,
                                    onEmailChange = loginViewModel::onResetEmailChange,
                                    onSendResetLink = loginViewModel::sendPasswordReset,
                                    onBackToLogin = {
                                        loginViewModel.leaveForgotPassword()
                                        if (backStack.size > 1) backStack.removeAt(backStack.lastIndex)
                                    }
                                )
                            }
                            entry<ScreenRoute.Auth.Register> {
                                RegisterDestination(loginViewModel, onLogin = {
                                    loginViewModel.clearMessage()
                                    backStack.removeAt(backStack.lastIndex)
                                    backStack.add(ScreenRoute.Auth.Login)
                                })
                            }
                            entry<ScreenRoute.Experiments> {
                                val loading by experimentViewModel.loading.collectAsStateWithLifecycle()
                                val error by experimentViewModel.error.collectAsStateWithLifecycle()
                                val requiresSignIn by experimentViewModel.requiresSignIn.collectAsStateWithLifecycle()
                                ExperimentScreen(
                                    experiments = catalog,
                                    loading = loading, error = error, onRetry = experimentViewModel::refresh,
                                    onSignInAgain = if (requiresSignIn) ({ loginViewModel.signOut(context); Unit }) else null,
                                    selectedId = selectedId,
                                    onSelect = { id ->
                                        if (id != experimentViewModel.selectedId.value) homeViewModel.reset()
                                        experimentViewModel.select(id)
                                    },
                                    onContinue = {
                                        if (experimentViewModel.selectedExperiment?.canStart == true && backStack.lastOrNull() != ScreenRoute.Home) {
                                            backStack.add(ScreenRoute.Home)
                                        }
                                    }
                                )
                            }
                            entry<ScreenRoute.Home> {
                                HomeDestination(loginViewModel, homeViewModel,
                                    experimentName = selectedExperiment?.name ?: if (catalogError == null) "Loading experiment…" else "Experiment unavailable",
                                    catalogError = catalogError,
                                    experimentAvailable = selectedExperiment?.canStart == true,
                                    darkTheme = darkTheme,
                                    onDarkThemeChange = settingsViewModel::setDarkTheme,
                                    onContinue = {
                                        val experiment = experimentViewModel.selectedExperiment
                                        val home = homeViewModel.uiState.value
                                        if (backStack.lastOrNull() == ScreenRoute.Home && experiment?.canStart == true && home.selectedVideoUri != null &&
                                            home.description.isNotBlank() && home.description.codePointCount(0, home.description.length) <= 2000) {
                                            conversationViewModel.startVideo(experiment, home.selectedVideoUri, home.description)
                                            backStack.add(ScreenRoute.Conversation)
                                        }
                                    },
                                    onChangeExperiment = {
                                        if (backStack.size > 1) backStack.removeAt(backStack.lastIndex)
                                    },
                                )
                            }
                            entry<ScreenRoute.Conversation> {
                                val state by conversationViewModel.uiState.collectAsStateWithLifecycle()
                                val session by conversationViewModel.session.collectAsStateWithLifecycle()
                                val contract by conversationViewModel.reviewContract.collectAsStateWithLifecycle()
                                val lifecycle = LocalLifecycleOwner.current.lifecycle
                                DisposableEffect(lifecycle) {
                                    val observer = LifecycleEventObserver { _, event ->
                                        if (event == Lifecycle.Event.ON_START) conversationViewModel.setForeground(true)
                                        if (event == Lifecycle.Event.ON_STOP) conversationViewModel.setForeground(false)
                                    }
                                    lifecycle.addObserver(observer)
                                    conversationViewModel.setForeground(lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED))
                                    onDispose { lifecycle.removeObserver(observer); conversationViewModel.setForeground(false) }
                                }
                                LaunchedEffect(state.exited) {
                                    if (state.exited && backStack.lastOrNull() == ScreenRoute.Conversation) {
                                        backStack.removeAt(backStack.lastIndex)
                                    }
                                }
                                ConversationScreen(state, conversationViewModel::draft,
                                    conversationViewModel::sendMessage, conversationViewModel::exit,
                                    onRetry = { conversationViewModel.retry() },
                                    actions = { session?.let { SessionActions(it, !state.isSending && state.canSend, contract, conversationViewModel::submit, state.reviewFrameUri, state.frameCaption,
                                        state.wireReview, conversationViewModel::reviewWire, { conversationViewModel.retry() }, conversationViewModel::exit) } },
                                    actionsKey = session?.takeIf { it.actions.isNotEmpty() }?.let {
                                        "${it.session_id}:${it.candidate_revision}:${it.actions.hashCode()}"
                                    })
                            }
                        }
                    )
                }
            }
        }
    }
}
