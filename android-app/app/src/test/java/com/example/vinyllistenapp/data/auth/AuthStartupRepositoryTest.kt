package com.example.vinyllistenapp.data.auth

import com.example.vinyllistenapp.data.api.ApiErrorKind
import com.example.vinyllistenapp.data.api.ApiException
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AuthStartupRepositoryTest {
    @Test
    fun noStoredRefreshTokenNeedsAuthAndClearsAccessToken() =
        runBlocking {
            val store = FakeAuthSessionStore()
            var accessToken: String? = "old-access"
            val repository =
                AuthStartupRepository(
                    sessionStore = store,
                    refreshSession = { error("refresh should not run") },
                    onAccessTokenChanged = { accessToken = it },
                )

            val result = repository.resolveStartupState()

            assertEquals(AuthStartupResult.NeedsAuth, result)
            assertNull(accessToken)
        }

    @Test
    fun validRefreshTokenStoresRotatedTokenPairAndMarksReady() =
        runBlocking {
            val store = FakeAuthSessionStore(refreshToken = "old-refresh")
            var accessToken: String? = null
            val repository =
                AuthStartupRepository(
                    sessionStore = store,
                    refreshSession = { refreshToken ->
                        assertEquals("old-refresh", refreshToken)
                        tokenPair(accessToken = "new-access", refreshToken = "new-refresh")
                    },
                    onAccessTokenChanged = { accessToken = it },
                )

            val result = repository.resolveStartupState()

            assertEquals(AuthStartupResult.Ready, result)
            assertEquals("new-access", accessToken)
            assertEquals("new-refresh", store.refreshToken)
            assertEquals("new-session", store.sessionId)
        }

    @Test
    fun inactivityRequiredRoutesToPasswordReentryWithoutClearingToken() =
        runBlocking {
            val store = FakeAuthSessionStore(refreshToken = "stale-refresh")
            val repository =
                AuthStartupRepository(
                    sessionStore = store,
                    refreshSession = {
                        throw ApiException(
                            message = "Password re-entry is required after inactivity.",
                            kind = ApiErrorKind.Unknown,
                            code = "inactivity_reauth_required",
                            statusCode = 401,
                        )
                    },
                    onAccessTokenChanged = {},
                )

            val result = repository.resolveStartupState()

            assertEquals(AuthStartupResult.NeedsPasswordReentry, result)
            assertEquals("stale-refresh", store.refreshToken)
            assertEquals(false, store.cleared)
        }

    @Test
    fun invalidRefreshTokenClearsSessionAndNeedsAuth() =
        runBlocking {
            val store = FakeAuthSessionStore(refreshToken = "bad-refresh")
            var accessToken: String? = "old-access"
            val repository =
                AuthStartupRepository(
                    sessionStore = store,
                    refreshSession = {
                        throw ApiException(
                            message = "Refresh token is invalid.",
                            kind = ApiErrorKind.Unknown,
                            code = "invalid_refresh_token",
                            statusCode = 401,
                        )
                    },
                    onAccessTokenChanged = { accessToken = it },
                )

            val result = repository.resolveStartupState()

            assertEquals(AuthStartupResult.NeedsAuth, result)
            assertNull(store.refreshToken)
            assertNull(accessToken)
            assertTrue(store.cleared)
        }

    @Test
    fun transientRefreshFailureIsRetryableAndKeepsSession() =
        runBlocking {
            val store = FakeAuthSessionStore(refreshToken = "retry-refresh")
            val repository =
                AuthStartupRepository(
                    sessionStore = store,
                    refreshSession = {
                        throw ApiException(
                            message = "Service unavailable.",
                            kind = ApiErrorKind.Offline,
                        )
                    },
                    onAccessTokenChanged = {},
                )

            val result = repository.resolveStartupState()

            assertTrue(result is AuthStartupResult.RetryableError)
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
            sessionId = "new-session",
        )

    private class FakeAuthSessionStore(
        var refreshToken: String? = null,
    ) : AuthSessionStore {
        var sessionId: String? = null
        var cleared: Boolean = false

        override fun loadRefreshToken(): String? = refreshToken

        override fun loadAccountEmail(): String? = null

        override fun saveTokenPair(
            tokenPair: AuthTokenPair,
            accountEmail: String?,
        ) {
            refreshToken = tokenPair.refreshToken
            sessionId = tokenPair.sessionId
            cleared = false
        }

        override fun clear() {
            refreshToken = null
            sessionId = null
            cleared = true
        }
    }
}
