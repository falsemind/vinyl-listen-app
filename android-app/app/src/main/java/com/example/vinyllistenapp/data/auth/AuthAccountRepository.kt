package com.example.vinyllistenapp.data.auth

class AuthAccountRepository(
    private val sessionStore: AuthSessionStore,
    private val registerAccountRequest: suspend (String, String) -> AuthRegistrationResult,
    private val verifyEmailRequest: suspend (String, String) -> AuthAccountSummary,
    private val resendVerificationRequest: suspend (String) -> AuthVerificationResendResult,
    private val loginRequest: suspend (String, String, String?) -> AuthTokenPair,
    private val passwordResetRequest: suspend (String) -> AuthPasswordResetRequestResult,
    private val currentPasswordResetRequest: suspend () -> AuthPasswordResetRequestResult,
    private val passwordResetConfirmRequest: suspend (String, String, String) -> AuthAccountSummary,
    private val currentPasswordResetConfirmRequest: suspend (String, String) -> AuthAccountSummary,
    private val passwordChangeRequest: suspend (String, String, Boolean) -> AuthPasswordChangeResult,
    private val logoutRequest: suspend () -> Boolean,
    private val logoutAllRequest: suspend () -> AuthLogoutAllResult,
    private val deleteAccountRequest: suspend (String) -> AuthDeleteAccountResult,
    private val onAccessTokenChanged: (String?) -> Unit,
    private val deviceLabelProvider: () -> String?,
) {
    suspend fun register(
        email: String,
        password: String,
    ): AuthRegistrationResult = registerAccountRequest(email.trim(), password)

    suspend fun verifyEmail(
        email: String,
        code: String,
    ): AuthAccountSummary = verifyEmailRequest(email.trim(), code.trim())

    suspend fun resendVerification(email: String): AuthVerificationResendResult = resendVerificationRequest(email.trim())

    suspend fun signIn(
        email: String,
        password: String,
    ): AuthTokenPair {
        val normalizedEmail = email.trim()
        val tokenPair = loginRequest(normalizedEmail, password, deviceLabelProvider())
        sessionStore.saveTokenPair(tokenPair, accountEmail = normalizedEmail)
        onAccessTokenChanged(tokenPair.accessToken)
        return tokenPair
    }

    suspend fun requestPasswordReset(email: String): AuthPasswordResetRequestResult = passwordResetRequest(email.trim())

    suspend fun requestCurrentAccountPasswordReset(): AuthPasswordResetRequestResult = currentPasswordResetRequest()

    suspend fun confirmPasswordReset(
        email: String,
        code: String,
        newPassword: String,
    ): AuthAccountSummary = passwordResetConfirmRequest(email.trim(), code.trim(), newPassword)

    suspend fun confirmCurrentAccountPasswordReset(
        code: String,
        newPassword: String,
    ): AuthAccountSummary = currentPasswordResetConfirmRequest(code.trim(), newPassword)

    fun currentAccountEmail(): String? = sessionStore.loadAccountEmail()

    suspend fun changePassword(
        currentPassword: String,
        newPassword: String,
        signOutEverywhere: Boolean,
    ): AuthPasswordChangeResult {
        val result = passwordChangeRequest(currentPassword, newPassword, signOutEverywhere)
        if (signOutEverywhere) {
            clearLocalSession()
        }
        return result
    }

    suspend fun logout(): Boolean {
        try {
            return logoutRequest()
        } finally {
            clearLocalSession()
        }
    }

    suspend fun logoutAll(): AuthLogoutAllResult {
        val result = logoutAllRequest()
        clearLocalSession()
        return result
    }

    suspend fun deleteAccount(password: String): AuthDeleteAccountResult {
        val result = deleteAccountRequest(password)
        clearLocalSession()
        return result
    }

    fun clearLocalSession() {
        sessionStore.clear()
        onAccessTokenChanged(null)
    }
}
