package com.example.vinyllistenapp.data.api

import kotlin.math.min

enum class ApiHttpMethod {
    Get,
    Post,
}

data class ApiRetryPolicy(
    val maxAttempts: Int = 3,
    val baseDelayMillis: Long = 1_000,
    val maxDelayMillis: Long = 8_000,
    val jitterMaxMillis: Long = 250,
) {
    init {
        require(maxAttempts >= 1) { "maxAttempts must be at least 1" }
        require(baseDelayMillis >= 0) { "baseDelayMillis must be non-negative" }
        require(maxDelayMillis >= baseDelayMillis) { "maxDelayMillis must be at least baseDelayMillis" }
        require(jitterMaxMillis >= 0) { "jitterMaxMillis must be non-negative" }
        require(jitterMaxMillis < Long.MAX_VALUE) { "jitterMaxMillis must be below Long.MAX_VALUE" }
    }

    fun shouldRetry(
        method: ApiHttpMethod,
        attempt: Int,
        statusCode: Int? = null,
        isNetworkFailure: Boolean = false,
    ): Boolean {
        if (method != ApiHttpMethod.Get || attempt >= maxAttempts) return false
        return isNetworkFailure || statusCode == 429 || statusCode in 500..599
    }

    fun delayMillis(
        attempt: Int,
        retryAfterMillis: Long?,
        jitterMillis: Long,
    ): Long {
        if (retryAfterMillis != null) return retryAfterMillis

        val exponentialDelay =
            baseDelayMillis.saturatingMultiply(1L shl (attempt - 1).coerceAtLeast(0).coerceAtMost(62))
        return min(exponentialDelay.saturatingAdd(jitterMillis.coerceAtLeast(0)), maxDelayMillis)
    }
}

fun parseRetryAfterMillis(value: String?): Long? {
    val seconds = value?.trim()?.toLongOrNull() ?: return null
    if (seconds < 0) return null
    return seconds.saturatingMultiply(1_000)
}

private fun Long.saturatingMultiply(multiplier: Long): Long =
    if (this == 0L || multiplier == 0L) {
        0L
    } else if (this > Long.MAX_VALUE / multiplier) {
        Long.MAX_VALUE
    } else {
        this * multiplier
    }

private fun Long.saturatingAdd(value: Long): Long =
    if (this > Long.MAX_VALUE - value) {
        Long.MAX_VALUE
    } else {
        this + value
    }
