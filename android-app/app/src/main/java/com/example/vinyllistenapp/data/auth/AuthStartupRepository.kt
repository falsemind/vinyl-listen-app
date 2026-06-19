package com.example.vinyllistenapp.data.auth

import com.example.vinyllistenapp.data.api.ApiErrorKind
import com.example.vinyllistenapp.data.api.ApiException

class AuthStartupRepository(
    private val sessionStore: AuthSessionStore,
    private val refreshSession: suspend (String) -> AuthTokenPair,
    private val onAccessTokenChanged: (String?) -> Unit,
) {
    suspend fun resolveStartupState(): AuthStartupResult {
        val refreshToken = sessionStore.loadRefreshToken()
        if (refreshToken.isNullOrBlank()) {
            onAccessTokenChanged(null)
            return AuthStartupResult.NeedsAuth
        }

        return try {
            val tokenPair = refreshSession(refreshToken)
            sessionStore.saveTokenPair(tokenPair)
            onAccessTokenChanged(tokenPair.accessToken)
            AuthStartupResult.Ready
        } catch (error: ApiException) {
            when {
                error.code == INACTIVITY_REAUTH_REQUIRED -> AuthStartupResult.NeedsPasswordReentry
                error.isUnrecoverableRefreshFailure() -> {
                    sessionStore.clear()
                    onAccessTokenChanged(null)
                    AuthStartupResult.NeedsAuth
                }
                error.isRetryableStartupFailure() -> AuthStartupResult.RetryableError(error.message ?: STARTUP_ERROR_MESSAGE)
                else -> AuthStartupResult.RetryableError(STARTUP_ERROR_MESSAGE)
            }
        }
    }

    fun clearSession() {
        sessionStore.clear()
        onAccessTokenChanged(null)
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

    private fun ApiException.isRetryableStartupFailure(): Boolean =
        kind == ApiErrorKind.Offline ||
            kind == ApiErrorKind.RateLimited ||
            kind == ApiErrorKind.Server ||
            statusCode == 408 ||
            statusCode == 429 ||
            (statusCode != null && statusCode in 500..599)

    private companion object {
        const val INACTIVITY_REAUTH_REQUIRED = "inactivity_reauth_required"
        const val INVALID_REFRESH_TOKEN = "invalid_refresh_token"
        const val REFRESH_TOKEN_EXPIRED = "refresh_token_expired"
        const val REFRESH_TOKEN_REUSE_DETECTED = "refresh_token_reuse_detected"
        const val REFRESH_TOKEN_REVOKED = "refresh_token_revoked"
        const val STARTUP_ERROR_MESSAGE = "Could not verify your session. Retry in a moment."
    }
}
