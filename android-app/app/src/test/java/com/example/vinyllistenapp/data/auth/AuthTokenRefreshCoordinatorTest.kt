package com.example.vinyllistenapp.data.auth

import com.example.vinyllistenapp.data.api.ApiErrorKind
import com.example.vinyllistenapp.data.api.ApiException
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AuthTokenRefreshCoordinatorTest {
    @Test
    fun refreshAccessTokenStoresRotatedRefreshTokenAndPublishesAccessToken() =
        runBlocking {
            val store = FakeAuthSessionStore(refreshToken = "old-refresh", accountEmail = "alex@example.com")
            var publishedAccessToken: String? = null
            val coordinator =
                AuthTokenRefreshCoordinator(
                    sessionStore = store,
                    refreshSession = { refreshToken ->
                        assertEquals("old-refresh", refreshToken)
                        tokenPair(accessToken = "new-access", refreshToken = "new-refresh")
                    },
                    onAccessTokenChanged = { publishedAccessToken = it },
                )

            val result = coordinator.refreshAccessToken()

            assertEquals(AuthSessionRefreshResult.Ready, result)
            assertEquals("new-access", publishedAccessToken)
            assertEquals("new-refresh", store.refreshToken)
            assertEquals("session-new", store.sessionId)
            assertEquals("alex@example.com", store.accountEmail)
        }

    @Test
    fun inactivityRequiredKeepsRefreshTokenAndRoutesToPasswordReentry() =
        runBlocking {
            val store = FakeAuthSessionStore(refreshToken = "stale-refresh")
            var passwordReentryRequested = false
            var publishedAccessToken: String? = "old-access"
            val coordinator =
                AuthTokenRefreshCoordinator(
                    sessionStore = store,
                    refreshSession = {
                        throw ApiException(
                            message = "Password re-entry is required.",
                            code = "inactivity_reauth_required",
                            statusCode = 401,
                        )
                    },
                    onAccessTokenChanged = { publishedAccessToken = it },
                    onPasswordReentryRequired = { passwordReentryRequested = true },
                )

            val result = coordinator.refreshAccessToken()

            assertEquals(AuthSessionRefreshResult.NeedsPasswordReentry, result)
            assertEquals("stale-refresh", store.refreshToken)
            assertNull(publishedAccessToken)
            assertTrue(passwordReentryRequested)
            assertEquals(false, store.cleared)
        }

    @Test
    fun invalidRefreshTokenClearsSessionAndRoutesToAuth() =
        runBlocking {
            val store = FakeAuthSessionStore(refreshToken = "bad-refresh", accountEmail = "alex@example.com")
            var sessionCleared = false
            val coordinator =
                AuthTokenRefreshCoordinator(
                    sessionStore = store,
                    refreshSession = {
                        throw ApiException(
                            message = "Refresh token is invalid.",
                            code = "invalid_refresh_token",
                            statusCode = 401,
                        )
                    },
                    onAccessTokenChanged = {},
                    onSessionCleared = { sessionCleared = true },
                )

            val result = coordinator.refreshAccessToken()

            assertEquals(AuthSessionRefreshResult.NeedsAuth, result)
            assertNull(store.refreshToken)
            assertNull(store.accountEmail)
            assertTrue(store.cleared)
            assertTrue(sessionCleared)
        }

    @Test
    fun transientRefreshFailureIsRethrownAndKeepsSession() =
        runBlocking {
            val store = FakeAuthSessionStore(refreshToken = "retry-refresh")
            val coordinator =
                AuthTokenRefreshCoordinator(
                    sessionStore = store,
                    refreshSession = {
                        throw ApiException(
                            message = "Service unavailable.",
                            kind = ApiErrorKind.Offline,
                        )
                    },
                    onAccessTokenChanged = {},
                )

            val error = runCatching { coordinator.refreshAccessToken() }.exceptionOrNull()

            assertTrue(error is ApiException)
            assertEquals("retry-refresh", store.refreshToken)
            assertEquals(false, store.cleared)
        }

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

    private class FakeAuthSessionStore(
        var refreshToken: String? = null,
        var accountEmail: String? = null,
    ) : AuthSessionStore {
        var sessionId: String? = null
        var cleared: Boolean = false

        override fun loadRefreshToken(): String? = refreshToken

        override fun loadAccountEmail(): String? = accountEmail

        override fun saveTokenPair(
            tokenPair: AuthTokenPair,
            accountEmail: String?,
        ) {
            refreshToken = tokenPair.refreshToken
            sessionId = tokenPair.sessionId
            accountEmail?.let { this.accountEmail = it }
            cleared = false
        }

        override fun clear() {
            refreshToken = null
            accountEmail = null
            sessionId = null
            cleared = true
        }
    }
}
