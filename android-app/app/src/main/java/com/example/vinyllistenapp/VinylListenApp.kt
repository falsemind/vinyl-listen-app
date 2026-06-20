package com.example.vinyllistenapp

import android.os.Build
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.navigation.compose.rememberNavController
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.data.auth.AuthAccountRepository
import com.example.vinyllistenapp.data.auth.AuthStartupRepository
import com.example.vinyllistenapp.data.auth.AuthStartupResult
import com.example.vinyllistenapp.data.auth.AuthTokenRefreshCoordinator
import com.example.vinyllistenapp.data.auth.EncryptedAuthSessionStore
import com.example.vinyllistenapp.navigation.VinylNavHost
import com.example.vinyllistenapp.navigation.VinylRoutes
import com.example.vinyllistenapp.ui.screens.AuthFlowScreen
import com.example.vinyllistenapp.ui.screens.AuthSplashScreen
import com.example.vinyllistenapp.ui.screens.PasswordReentryRequiredScreen
import kotlinx.coroutines.launch

@Composable
fun VinylListenApp(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val navController = rememberNavController()
    val appContext = remember(context) { context.applicationContext }
    val apiClient = remember { VinylApiClient() }
    val sessionStore = remember(appContext) { EncryptedAuthSessionStore(appContext) }
    val coroutineScope = rememberCoroutineScope()
    var authState by remember { mutableStateOf<AuthGateUiState>(AuthGateUiState.Checking) }
    var retryCount by rememberSaveable { mutableIntStateOf(0) }
    var isPasswordReentrySubmitting by remember { mutableStateOf(false) }
    var passwordReentryError by remember { mutableStateOf<String?>(null) }

    fun resetMainNavigationToHome() {
        runCatching {
            navController.navigate(VinylRoutes.HOME) {
                popUpTo(navController.graph.startDestinationId) {
                    inclusive = false
                }
                launchSingleTop = true
            }
        }
    }

    fun requireAuthFromSignedOutState() {
        resetMainNavigationToHome()
        passwordReentryError = null
        authState = AuthGateUiState.NeedsAuth
    }

    val tokenRefreshCoordinator =
        remember(apiClient, sessionStore, coroutineScope) {
            AuthTokenRefreshCoordinator(
                sessionStore = sessionStore,
                refreshSession = apiClient::refreshAuthSession,
                onAccessTokenChanged = apiClient::setAccessToken,
                onSessionCleared = {
                    coroutineScope.launch {
                        requireAuthFromSignedOutState()
                    }
                },
                onPasswordReentryRequired = {
                    coroutineScope.launch {
                        passwordReentryError = null
                        authState = AuthGateUiState.NeedsPasswordReentry
                    }
                },
            )
        }
    val authRepository =
        remember(apiClient, sessionStore) {
            AuthStartupRepository(
                sessionStore = sessionStore,
                refreshSession = apiClient::refreshAuthSession,
                onAccessTokenChanged = apiClient::setAccessToken,
            )
        }
    val authAccountRepository =
        remember(apiClient, sessionStore) {
            AuthAccountRepository(
                sessionStore = sessionStore,
                registerAccountRequest = apiClient::registerAccount,
                verifyEmailRequest = apiClient::verifyEmail,
                resendVerificationRequest = apiClient::resendEmailVerification,
                loginRequest = apiClient::login,
                passwordResetRequest = apiClient::requestPasswordReset,
                currentPasswordResetRequest = apiClient::requestCurrentAccountPasswordReset,
                passwordResetConfirmRequest = apiClient::confirmPasswordReset,
                currentPasswordResetConfirmRequest = apiClient::confirmCurrentAccountPasswordReset,
                passwordChangeRequest = apiClient::changePassword,
                logoutRequest = apiClient::logout,
                logoutAllRequest = apiClient::logoutAll,
                deleteAccountRequest = apiClient::deleteAccount,
                onAccessTokenChanged = apiClient::setAccessToken,
                deviceLabelProvider = ::androidDeviceLabel,
            )
        }

    DisposableEffect(apiClient, tokenRefreshCoordinator) {
        apiClient.setAuthSessionRefresher(tokenRefreshCoordinator::refreshAccessToken)
        onDispose { apiClient.setAuthSessionRefresher(null) }
    }

    suspend fun verifyStartupAuth() {
        authState = AuthGateUiState.Checking
        authState = authRepository.resolveStartupState().toUiState()
    }

    LaunchedEffect(authRepository) {
        verifyStartupAuth()
    }

    when (val state = authState) {
        AuthGateUiState.Checking ->
            AuthSplashScreen(
                errorMessage = null,
                retryCount = retryCount,
                onRetry = {},
                modifier = modifier,
            )
        AuthGateUiState.Ready ->
            VinylNavHost(
                navController = navController,
                apiClient = apiClient,
                authAccountRepository = authAccountRepository,
                onAuthSessionEnded = ::requireAuthFromSignedOutState,
                onAccountDeleted = ::requireAuthFromSignedOutState,
                modifier = modifier,
            )
        AuthGateUiState.NeedsAuth ->
            AuthFlowScreen(
                authRepository = authAccountRepository,
                onAuthenticated = {
                    resetMainNavigationToHome()
                    authState = AuthGateUiState.Ready
                },
                modifier = modifier,
            )
        AuthGateUiState.NeedsPasswordReentry ->
            PasswordReentryRequiredScreen(
                accountEmail = sessionStore.loadAccountEmail(),
                isSubmitting = isPasswordReentrySubmitting,
                errorMessage = passwordReentryError,
                onSubmit = { email, password ->
                    if (isPasswordReentrySubmitting) return@PasswordReentryRequiredScreen
                    isPasswordReentrySubmitting = true
                    passwordReentryError = null
                    coroutineScope.launch {
                        runCatching { authAccountRepository.signIn(email, password) }
                            .onSuccess {
                                authState = AuthGateUiState.Ready
                            }.onFailure { error ->
                                passwordReentryError =
                                    error.message?.takeIf { it.isNotBlank() }
                                        ?: "Could not verify your password."
                            }
                        isPasswordReentrySubmitting = false
                    }
                },
                onUseDifferentAccount = {
                    tokenRefreshCoordinator.clearSession()
                    requireAuthFromSignedOutState()
                },
                modifier = modifier,
            )
        is AuthGateUiState.RetryableError ->
            AuthSplashScreen(
                errorMessage = state.message,
                retryCount = retryCount,
                onRetry = {
                    retryCount += 1
                    coroutineScope.launch { verifyStartupAuth() }
                },
                modifier = modifier,
            )
    }
}

private sealed interface AuthGateUiState {
    data object Checking : AuthGateUiState

    data object Ready : AuthGateUiState

    data object NeedsAuth : AuthGateUiState

    data object NeedsPasswordReentry : AuthGateUiState

    data class RetryableError(
        val message: String,
    ) : AuthGateUiState
}

private fun AuthStartupResult.toUiState(): AuthGateUiState =
    when (this) {
        AuthStartupResult.Ready -> AuthGateUiState.Ready
        AuthStartupResult.NeedsAuth -> AuthGateUiState.NeedsAuth
        AuthStartupResult.NeedsPasswordReentry -> AuthGateUiState.NeedsPasswordReentry
        is AuthStartupResult.RetryableError -> AuthGateUiState.RetryableError(message)
    }

private fun androidDeviceLabel(): String =
    listOf(Build.MANUFACTURER, Build.MODEL)
        .filter { it.isNotBlank() }
        .joinToString(" ")
        .ifBlank { "Android" }
