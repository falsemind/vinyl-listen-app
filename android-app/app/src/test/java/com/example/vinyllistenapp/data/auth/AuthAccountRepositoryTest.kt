package com.example.vinyllistenapp.data.auth

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Test

class AuthAccountRepositoryTest {
    @Test
    fun signInStoresTokenPairAndPublishesAccessToken() =
        runBlocking {
            val store = FakeAuthSessionStore()
            var publishedAccessToken: String? = null
            var capturedDeviceLabel: String? = null
            val repository =
                repository(
                    store = store,
                    onAccessTokenChanged = { publishedAccessToken = it },
                    login = { email, password, deviceLabel ->
                        assertEquals("alex@example.com", email)
                        assertEquals("password", password)
                        capturedDeviceLabel = deviceLabel
                        tokenPair(accessToken = "access-new", refreshToken = "refresh-new")
                    },
                )

            repository.signIn(" alex@example.com ", "password")

            assertEquals("Pixel 9", capturedDeviceLabel)
            assertEquals("access-new", publishedAccessToken)
            assertEquals("refresh-new", store.refreshToken)
            assertEquals("session-new", store.sessionId)
        }

    @Test
    fun registerTrimsEmailBeforeSubmitting() =
        runBlocking {
            val repository =
                repository(
                    registerAccount = { email, password ->
                        assertEquals("alex@example.com", email)
                        assertEquals("password", password)
                        registrationResult(email)
                    },
                )

            val result = repository.register(" alex@example.com ", "password")

            assertEquals("alex@example.com", result.email)
        }

    @Test
    fun requestPasswordResetTrimsEmailBeforeSubmitting() =
        runBlocking {
            val repository =
                repository(
                    requestPasswordReset = { email ->
                        assertEquals("alex@example.com", email)
                        AuthPasswordResetRequestResult(accepted = true, email = email)
                    },
                )

            val result = repository.requestPasswordReset(" alex@example.com ")

            assertEquals(true, result.accepted)
            assertEquals("alex@example.com", result.email)
        }

    @Test
    fun confirmPasswordResetTrimsEmailAndCodeBeforeSubmitting() =
        runBlocking {
            val repository =
                repository(
                    confirmPasswordReset = { email, code, newPassword ->
                        assertEquals("alex@example.com", email)
                        assertEquals("123456", code)
                        assertEquals("new-password", newPassword)
                        accountSummary(email)
                    },
                )

            val result =
                repository.confirmPasswordReset(
                    email = " alex@example.com ",
                    code = " 123456 ",
                    newPassword = "new-password",
                )

            assertEquals("alex@example.com", result.email)
        }

    private fun repository(
        store: AuthSessionStore = FakeAuthSessionStore(),
        registerAccount: suspend (String, String) -> AuthRegistrationResult = { email, _ -> registrationResult(email) },
        verifyEmail: suspend (String, String) -> AuthAccountSummary = { email, _ -> accountSummary(email) },
        resendVerification: suspend (String) -> AuthVerificationResendResult = { email -> resendResult(email) },
        login: suspend (String, String, String?) -> AuthTokenPair = { _, _, _ -> tokenPair() },
        requestPasswordReset: suspend (String) -> AuthPasswordResetRequestResult = { email ->
            AuthPasswordResetRequestResult(accepted = true, email = email)
        },
        confirmPasswordReset: suspend (String, String, String) -> AuthAccountSummary = { email, _, _ ->
            accountSummary(email)
        },
        onAccessTokenChanged: (String?) -> Unit = {},
    ): AuthAccountRepository =
        AuthAccountRepository(
            sessionStore = store,
            registerAccountRequest = registerAccount,
            verifyEmailRequest = verifyEmail,
            resendVerificationRequest = resendVerification,
            loginRequest = login,
            passwordResetRequest = requestPasswordReset,
            passwordResetConfirmRequest = confirmPasswordReset,
            onAccessTokenChanged = onAccessTokenChanged,
            deviceLabelProvider = { "Pixel 9" },
        )

    private fun tokenPair(
        accessToken: String = "access",
        refreshToken: String = "refresh",
    ): AuthTokenPair =
        AuthTokenPair(
            accessToken = accessToken,
            accessExpiresAt = "2026-06-19T12:00:00Z",
            refreshToken = refreshToken,
            refreshExpiresAt = "2026-06-26T12:00:00Z",
            tokenType = "Bearer",
            sessionId = "session-new",
        )

    private fun registrationResult(email: String): AuthRegistrationResult =
        AuthRegistrationResult(
            userId = "user-1",
            email = email,
            verificationExpiresAt = "2026-06-19T12:00:00Z",
        )

    private fun accountSummary(email: String): AuthAccountSummary =
        AuthAccountSummary(
            userId = "user-1",
            email = email,
            emailVerifiedAt = "2026-06-19T12:00:00Z",
        )

    private fun resendResult(email: String): AuthVerificationResendResult =
        AuthVerificationResendResult(
            userId = "user-1",
            email = email,
            verificationExpiresAt = "2026-06-19T12:05:00Z",
            resendCount = 1,
        )

    private class FakeAuthSessionStore : AuthSessionStore {
        var refreshToken: String? = null
        var sessionId: String? = null

        override fun loadRefreshToken(): String? = refreshToken

        override fun saveTokenPair(tokenPair: AuthTokenPair) {
            refreshToken = tokenPair.refreshToken
            sessionId = tokenPair.sessionId
        }

        override fun clear() {
            refreshToken = null
            sessionId = null
        }
    }
}
