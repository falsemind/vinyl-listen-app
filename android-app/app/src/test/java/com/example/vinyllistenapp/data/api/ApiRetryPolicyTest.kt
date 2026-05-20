package com.example.vinyllistenapp.data.api

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

class ApiRetryPolicyTest {
    private val policy =
        ApiRetryPolicy(
            maxAttempts = 3,
            baseDelayMillis = 1_000,
            maxDelayMillis = 8_000,
            jitterMaxMillis = 250,
        )

    @Test
    fun parsesRetryAfterSeconds() {
        assertEquals(5_000L, parseRetryAfterMillis("5"))
        assertEquals(0L, parseRetryAfterMillis("0"))
    }

    @Test
    fun ignoresInvalidRetryAfterValues() {
        assertEquals(null, parseRetryAfterMillis("-1"))
        assertEquals(null, parseRetryAfterMillis("soon"))
        assertEquals(null, parseRetryAfterMillis(null))
    }

    @Test
    fun retryAfterOverridesLocalBackoff() {
        assertEquals(4_000L, policy.delayMillis(attempt = 2, retryAfterMillis = 4_000, jitterMillis = 125))
    }

    @Test
    fun localBackoffUsesExponentialDelayWithJitterAndMaxClamp() {
        assertEquals(1_125L, policy.delayMillis(attempt = 1, retryAfterMillis = null, jitterMillis = 125))
        assertEquals(2_250L, policy.delayMillis(attempt = 2, retryAfterMillis = null, jitterMillis = 250))
        assertEquals(8_000L, policy.delayMillis(attempt = 4, retryAfterMillis = null, jitterMillis = 250))
    }

    @Test
    fun localBackoffClampsWithoutOverflow() {
        val largePolicy =
            ApiRetryPolicy(
                baseDelayMillis = Long.MAX_VALUE - 1,
                maxDelayMillis = Long.MAX_VALUE,
                jitterMaxMillis = 250,
            )

        assertEquals(Long.MAX_VALUE, largePolicy.delayMillis(attempt = 2, retryAfterMillis = null, jitterMillis = 250))
    }

    @Test
    fun jitterMaximumMustLeaveRoomForInclusiveRandomBound() {
        try {
            ApiRetryPolicy(jitterMaxMillis = Long.MAX_VALUE)
            fail("Expected invalid jitter maximum to throw")
        } catch (error: IllegalArgumentException) {
            assertEquals("jitterMaxMillis must be below Long.MAX_VALUE", error.message)
        }
    }

    @Test
    fun getCallsRetryRateLimitServerAndNetworkFailuresBeforeMaxAttempts() {
        assertTrue(policy.shouldRetry(ApiHttpMethod.Get, attempt = 1, statusCode = 429))
        assertTrue(policy.shouldRetry(ApiHttpMethod.Get, attempt = 2, statusCode = 503))
        assertTrue(policy.shouldRetry(ApiHttpMethod.Get, attempt = 1, isNetworkFailure = true))
        assertFalse(policy.shouldRetry(ApiHttpMethod.Get, attempt = 3, statusCode = 429))
    }

    @Test
    fun retryablePostCallsRetryRateLimitServerAndNetworkFailuresBeforeMaxAttempts() {
        assertTrue(policy.shouldRetry(ApiHttpMethod.RetryablePost, attempt = 1, statusCode = 429))
        assertTrue(policy.shouldRetry(ApiHttpMethod.RetryablePost, attempt = 2, statusCode = 503))
        assertTrue(policy.shouldRetry(ApiHttpMethod.RetryablePost, attempt = 1, isNetworkFailure = true))
        assertFalse(policy.shouldRetry(ApiHttpMethod.RetryablePost, attempt = 3, statusCode = 429))
    }

    @Test
    fun postCallsDoNotAutoRetry() {
        assertFalse(policy.shouldRetry(ApiHttpMethod.Post, attempt = 1, statusCode = 429))
        assertFalse(policy.shouldRetry(ApiHttpMethod.Post, attempt = 1, statusCode = 503))
        assertFalse(policy.shouldRetry(ApiHttpMethod.Post, attempt = 1, isNetworkFailure = true))
    }

    @Test
    fun rateLimitMessageUsesRetryAfterWhenAvailable() {
        assertEquals("Backend is busy. Retry in 3 seconds.", rateLimitMessage(2_500))
        assertEquals("Backend is busy. Retry in a moment.", rateLimitMessage(null))
    }
}
