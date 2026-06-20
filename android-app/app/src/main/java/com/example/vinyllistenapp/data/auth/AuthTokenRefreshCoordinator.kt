package com.example.vinyllistenapp.data.auth

import com.example.vinyllistenapp.data.api.ApiErrorKind
import com.example.vinyllistenapp.data.api.ApiException
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

class AuthTokenRefreshCoordinator(
    private val sessionStore: AuthSessionStore,
    private val refreshSession: suspend (String) -> AuthTokenPair,
    private val onAccessTokenChanged: (String?) -> Unit,
    private val onSessionCleared: () -> Unit = {},
    private val onPasswordReentryRequired: () -> Unit = {},
) {
    private val refreshMutex = Mutex()

    suspend fun refreshAccessToken(): AuthSessionRefreshResult =
        refreshMutex.withLock {
            val refreshToken = sessionStore.loadRefreshToken()
            if (refreshToken.isNullOrBlank()) {
                onAccessTokenChanged(null)
                onSessionCleared()
                return@withLock AuthSessionRefreshResult.NeedsAuth
            }

            try {
                val tokenPair = refreshSession(refreshToken)
                sessionStore.saveTokenPair(tokenPair)
                onAccessTokenChanged(tokenPair.accessToken)
                AuthSessionRefreshResult.Ready
            } catch (error: ApiException) {
                when {
                    error.code == INACTIVITY_REAUTH_REQUIRED -> {
                        onAccessTokenChanged(null)
                        onPasswordReentryRequired()
                        AuthSessionRefreshResult.NeedsPasswordReentry
                    }
                    error.isUnrecoverableRefreshFailure() -> {
                        sessionStore.clear()
                        onAccessTokenChanged(null)
                        onSessionCleared()
                        AuthSessionRefreshResult.NeedsAuth
                    }
                    else -> throw error
                }
            }
        }

    fun clearSession() {
        sessionStore.clear()
        onAccessTokenChanged(null)
        onSessionCleared()
    }

    private fun ApiException.isUnrecoverableRefreshFailure(): Boolean =
        statusCode == 401 &&
            code in
            setOf(
                INVALID_REFRESH_TOKEN,
                REFRESH_TOKEN_EXPIRED,
                REFRESH_TOKEN_REUSE_DETECTED,
                REFRESH_TOKEN_REVOKED,
                null,
            )

    companion object {
        const val INACTIVITY_REAUTH_REQUIRED = "inactivity_reauth_required"
        const val INVALID_REFRESH_TOKEN = "invalid_refresh_token"
        const val REFRESH_TOKEN_EXPIRED = "refresh_token_expired"
        const val REFRESH_TOKEN_REUSE_DETECTED = "refresh_token_reuse_detected"
        const val REFRESH_TOKEN_REVOKED = "refresh_token_revoked"

        fun ApiException.isRetryableRefreshFailure(): Boolean =
            kind == ApiErrorKind.Offline ||
                kind == ApiErrorKind.RateLimited ||
                kind == ApiErrorKind.Server ||
                statusCode == 408 ||
                statusCode == 429 ||
                (statusCode != null && statusCode in 500..599)
    }
}
