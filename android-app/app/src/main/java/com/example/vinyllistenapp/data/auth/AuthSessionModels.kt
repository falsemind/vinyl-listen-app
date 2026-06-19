package com.example.vinyllistenapp.data.auth

data class AuthTokenPair(
    val accessToken: String,
    val accessExpiresAt: String,
    val refreshToken: String,
    val refreshExpiresAt: String,
    val tokenType: String,
    val sessionId: String,
)

sealed interface AuthStartupResult {
    data object Ready : AuthStartupResult

    data object NeedsAuth : AuthStartupResult

    data object NeedsPasswordReentry : AuthStartupResult

    data class RetryableError(
        val message: String,
    ) : AuthStartupResult
}
