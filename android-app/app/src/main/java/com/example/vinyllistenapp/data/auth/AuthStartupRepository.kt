package com.example.vinyllistenapp.data.auth

import com.example.vinyllistenapp.data.api.ApiException
import com.example.vinyllistenapp.data.auth.AuthTokenRefreshCoordinator.Companion.isRetryableRefreshFailure

class AuthStartupRepository(
    private val sessionStore: AuthSessionStore,
    refreshSession: suspend (String) -> AuthTokenPair,
    private val onAccessTokenChanged: (String?) -> Unit,
) {
    private val refreshCoordinator =
        AuthTokenRefreshCoordinator(
            sessionStore = sessionStore,
            refreshSession = refreshSession,
            onAccessTokenChanged = onAccessTokenChanged,
        )

    suspend fun resolveStartupState(): AuthStartupResult =
        try {
            when (refreshCoordinator.refreshAccessToken()) {
                AuthSessionRefreshResult.Ready -> AuthStartupResult.Ready
                AuthSessionRefreshResult.NeedsAuth -> AuthStartupResult.NeedsAuth
                AuthSessionRefreshResult.NeedsPasswordReentry -> AuthStartupResult.NeedsPasswordReentry
            }
        } catch (error: ApiException) {
            when {
                error.isRetryableRefreshFailure() -> AuthStartupResult.RetryableError(error.message ?: STARTUP_ERROR_MESSAGE)
                else -> AuthStartupResult.RetryableError(STARTUP_ERROR_MESSAGE)
            }
        }

    fun clearSession() {
        sessionStore.clear()
        onAccessTokenChanged(null)
    }

    private companion object {
        const val STARTUP_ERROR_MESSAGE = "Could not verify your session. Retry in a moment."
    }
}
