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
            assertEquals("alex@example.com", store.accountEmail)
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
    fun requestCurrentAccountPasswordResetDoesNotRequireEmailInput() =
        runBlocking {
            val repository =
                repository(
                    requestCurrentPasswordReset = {
                        AuthPasswordResetRequestResult(accepted = true, email = "alex@example.com")
                    },
                )

            val result = repository.requestCurrentAccountPasswordReset()

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

    @Test
    fun logoutClearsLocalSessionAndPublishedAccessToken() =
        runBlocking {
            val store = FakeAuthSessionStore()
            var publishedAccessToken: String? = "access"
            val repository =
                repository(
                    store = store,
                    logout = { true },
                    onAccessTokenChanged = { publishedAccessToken = it },
                )
            store.saveTokenPair(tokenPair(), accountEmail = "alex@example.com")

            val revoked = repository.logout()

            assertEquals(true, revoked)
            assertEquals(null, store.refreshToken)
            assertEquals(null, store.accountEmail)
            assertEquals(null, publishedAccessToken)
        }

    @Test
    fun failedLogoutStillClearsLocalSession() =
        runBlocking {
            val store = FakeAuthSessionStore()
            val repository =
                repository(
                    store = store,
                    logout = { error("logout failed") },
                )
            store.saveTokenPair(tokenPair(), accountEmail = "alex@example.com")

            runCatching { repository.logout() }

            assertEquals(null, store.refreshToken)
            assertEquals(null, store.accountEmail)
        }

    @Test
    fun logoutAllClearsLocalSession() =
        runBlocking {
            val store = FakeAuthSessionStore()
            val repository =
                repository(
                    store = store,
                    logoutAll = { AuthLogoutAllResult(revokedSessions = 2) },
                )
            store.saveTokenPair(tokenPair(), accountEmail = "alex@example.com")

            val result = repository.logoutAll()

            assertEquals(2, result.revokedSessions)
            assertEquals(null, store.refreshToken)
            assertEquals(null, store.accountEmail)
        }

    @Test
    fun deleteAccountClearsLocalSession() =
        runBlocking {
            val store = FakeAuthSessionStore()
            val repository =
                repository(
                    store = store,
                    deleteAccount = { password ->
                        assertEquals("password", password)
                        AuthDeleteAccountResult(
                            deleted = true,
                            deletionReceiptId = "receipt-1",
                            deletedAt = "2026-06-19T12:00:00Z",
                        )
                    },
                )
            store.saveTokenPair(tokenPair(), accountEmail = "alex@example.com")

            val result = repository.deleteAccount("password")

            assertEquals(true, result.deleted)
            assertEquals(null, store.refreshToken)
            assertEquals(null, store.accountEmail)
        }

    @Test
    fun changePasswordClearsLocalSessionWhenSigningOutEverywhere() =
        runBlocking {
            val store = FakeAuthSessionStore()
            val repository =
                repository(
                    store = store,
                    changePassword = { currentPassword, newPassword, signOutEverywhere ->
                        assertEquals("old-password", currentPassword)
                        assertEquals("new-password", newPassword)
                        assertEquals(true, signOutEverywhere)
                        AuthPasswordChangeResult(changed = true, revokedSessions = 1)
                    },
                )
            store.saveTokenPair(tokenPair(), accountEmail = "alex@example.com")

            val result =
                repository.changePassword(
                    currentPassword = "old-password",
                    newPassword = "new-password",
                    signOutEverywhere = true,
                )

            assertEquals(true, result.changed)
            assertEquals(null, store.refreshToken)
            assertEquals(null, store.accountEmail)
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
        requestCurrentPasswordReset: suspend () -> AuthPasswordResetRequestResult = {
            AuthPasswordResetRequestResult(accepted = true, email = "alex@example.com")
        },
        confirmPasswordReset: suspend (String, String, String) -> AuthAccountSummary = { email, _, _ ->
            accountSummary(email)
        },
        confirmCurrentPasswordReset: suspend (String, String) -> AuthAccountSummary = { _, _ ->
            accountSummary("alex@example.com")
        },
        changePassword: suspend (String, String, Boolean) -> AuthPasswordChangeResult = { _, _, _ ->
            AuthPasswordChangeResult(changed = true, revokedSessions = 0)
        },
        logout: suspend () -> Boolean = { true },
        logoutAll: suspend () -> AuthLogoutAllResult = { AuthLogoutAllResult(revokedSessions = 1) },
        deleteAccount: suspend (String) -> AuthDeleteAccountResult = {
            AuthDeleteAccountResult(
                deleted = true,
                deletionReceiptId = "receipt-1",
                deletedAt = "2026-06-19T12:00:00Z",
            )
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
            currentPasswordResetRequest = requestCurrentPasswordReset,
            passwordResetConfirmRequest = confirmPasswordReset,
            currentPasswordResetConfirmRequest = confirmCurrentPasswordReset,
            passwordChangeRequest = changePassword,
            logoutRequest = logout,
            logoutAllRequest = logoutAll,
            deleteAccountRequest = deleteAccount,
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
        var accountEmail: String? = null

        override fun loadRefreshToken(): String? = refreshToken

        override fun loadAccountEmail(): String? = accountEmail

        override fun saveTokenPair(
            tokenPair: AuthTokenPair,
            accountEmail: String?,
        ) {
            refreshToken = tokenPair.refreshToken
            sessionId = tokenPair.sessionId
            accountEmail?.let { this.accountEmail = it }
        }

        override fun clear() {
            refreshToken = null
            sessionId = null
            accountEmail = null
        }
    }
}
