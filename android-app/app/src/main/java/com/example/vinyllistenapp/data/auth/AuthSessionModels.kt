package com.example.vinyllistenapp.data.auth

data class AuthTokenPair(
    val accessToken: String,
    val accessExpiresAt: String,
    val refreshToken: String,
    val refreshExpiresAt: String,
    val tokenType: String,
    val sessionId: String,
)

data class AuthRegistrationResult(
    val userId: String,
    val email: String,
    val verificationExpiresAt: String,
)

data class AuthAccountSummary(
    val userId: String,
    val email: String,
    val emailVerifiedAt: String?,
)

data class AuthVerificationResendResult(
    val userId: String,
    val email: String,
    val verificationExpiresAt: String,
    val resendCount: Int,
)

data class AuthPasswordResetRequestResult(
    val accepted: Boolean,
    val email: String,
)

sealed interface AuthStartupResult {
    data object Ready : AuthStartupResult

    data object NeedsAuth : AuthStartupResult

    data object NeedsPasswordReentry : AuthStartupResult

    data class RetryableError(
        val message: String,
    ) : AuthStartupResult
}

sealed interface AuthSessionRefreshResult {
    data object Ready : AuthSessionRefreshResult

    data object NeedsAuth : AuthSessionRefreshResult

    data object NeedsPasswordReentry : AuthSessionRefreshResult
}
