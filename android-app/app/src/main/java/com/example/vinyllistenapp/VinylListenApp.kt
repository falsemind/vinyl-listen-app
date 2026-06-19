package com.example.vinyllistenapp

import androidx.compose.runtime.Composable
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
import com.example.vinyllistenapp.data.auth.AuthStartupRepository
import com.example.vinyllistenapp.data.auth.AuthStartupResult
import com.example.vinyllistenapp.data.auth.SharedPreferencesAuthSessionStore
import com.example.vinyllistenapp.navigation.VinylNavHost
import com.example.vinyllistenapp.ui.screens.AuthEntryScreen
import com.example.vinyllistenapp.ui.screens.AuthSplashScreen
import com.example.vinyllistenapp.ui.screens.PasswordReentryRequiredScreen
import kotlinx.coroutines.launch

@Composable
fun VinylListenApp(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val navController = rememberNavController()
    val appContext = remember(context) { context.applicationContext }
    val apiClient = remember { VinylApiClient() }
    val sessionStore = remember(appContext) { SharedPreferencesAuthSessionStore(appContext) }
    val authRepository =
        remember(apiClient, sessionStore) {
            AuthStartupRepository(
                sessionStore = sessionStore,
                refreshSession = apiClient::refreshAuthSession,
                onAccessTokenChanged = apiClient::setAccessToken,
            )
        }
    val coroutineScope = rememberCoroutineScope()
    var authState by remember { mutableStateOf<AuthGateUiState>(AuthGateUiState.Checking) }
    var retryCount by rememberSaveable { mutableIntStateOf(0) }

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
                modifier = modifier,
            )
        AuthGateUiState.NeedsAuth ->
            AuthEntryScreen(
                onCreateAccount = {},
                onSignIn = {},
                modifier = modifier,
            )
        AuthGateUiState.NeedsPasswordReentry ->
            PasswordReentryRequiredScreen(
                onUseDifferentAccount = {
                    authRepository.clearSession()
                    authState = AuthGateUiState.NeedsAuth
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
