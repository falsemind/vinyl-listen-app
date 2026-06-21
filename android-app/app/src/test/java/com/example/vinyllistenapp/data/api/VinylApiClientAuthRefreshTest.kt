package com.example.vinyllistenapp.data.api

import com.example.vinyllistenapp.data.auth.AuthSessionRefreshResult
import com.example.vinyllistenapp.domain.ManualReleaseFormData
import com.sun.net.httpserver.HttpServer
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.fail
import org.junit.Test
import java.net.InetSocketAddress

class VinylApiClientAuthRefreshTest {
    @Test
    fun protectedRequestRefreshesAccessTokenOnceAndRetries() =
        runBlocking {
            val seenAuthorizationHeaders = mutableListOf<String?>()
            val server = HttpServer.create(InetSocketAddress("127.0.0.1", 0), 0)
            server.createContext("/api/v1/collection/folders") { exchange ->
                seenAuthorizationHeaders += exchange.requestHeaders.getFirst("Authorization")
                if (seenAuthorizationHeaders.size == 1) {
                    exchange.respond(
                        status = 401,
                        body = """{"error":{"code":"expired_access_token","message":"Access token expired."}}""",
                    )
                } else {
                    exchange.respond(
                        status = 200,
                        body = """{"discogs_configured":false,"folders":[],"has_extra_folders":false}""",
                    )
                }
            }
            server.start()
            try {
                val client = VinylApiClient(baseUrl = "http://127.0.0.1:${server.address.port}/api/v1")
                var refreshCount = 0
                client.setAccessToken("old-access")
                client.setAuthSessionRefresher {
                    refreshCount += 1
                    client.setAccessToken("new-access")
                    AuthSessionRefreshResult.Ready
                }

                val folders = client.getCollectionFolders()

                assertEquals(false, folders.discogsConfigured)
                assertEquals(1, refreshCount)
                assertEquals(listOf("Bearer old-access", "Bearer new-access"), seenAuthorizationHeaders)
            } finally {
                server.stop(0)
            }
        }

    @Test
    fun featureUsageLimitErrorPreservesEntitlementMetadata() =
        runBlocking {
            val server = HttpServer.create(InetSocketAddress("127.0.0.1", 0), 0)
            server.createContext("/api/v1/collection/folders") { exchange ->
                exchange.respond(
                    status = 402,
                    body =
                        """
                        {
                          "error": {
                            "code": "feature_usage_limit_exceeded",
                            "message": "Usage limit reached for this feature.",
                            "capability": "ocr_identify",
                            "plan": "FREE",
                            "limit": 25,
                            "used": 25,
                            "reset_at": "2026-07-19T12:00:00+00:00"
                          }
                        }
                        """.trimIndent(),
                )
            }
            server.start()
            try {
                val client = VinylApiClient(baseUrl = "http://127.0.0.1:${server.address.port}/api/v1")

                try {
                    client.getCollectionFolders()
                    fail("Expected feature-gated API error.")
                } catch (error: ApiException) {
                    assertEquals(ApiErrorKind.FeatureGated, error.kind)
                    assertEquals("feature_usage_limit_exceeded", error.code)
                    assertEquals(402, error.statusCode)
                    assertEquals(
                        "Identify allowance reached. Manual Search is still available. " +
                            "Try again after 2026-07-19T12:00:00+00:00.",
                        error.message,
                    )
                    val usageLimit = error.featureUsageLimit ?: throw AssertionError("Expected usage limit metadata.")
                    assertEquals("ocr_identify", usageLimit.capability)
                    assertEquals("FREE", usageLimit.plan)
                    assertEquals(25, usageLimit.limit)
                    assertEquals(25, usageLimit.used)
                    assertEquals("2026-07-19T12:00:00+00:00", usageLimit.resetAt)
                }
            } finally {
                server.stop(0)
            }
        }

    @Test
    fun validationErrorPreservesFieldErrors() =
        runBlocking {
            val server = HttpServer.create(InetSocketAddress("127.0.0.1", 0), 0)
            server.createContext("/api/v1/manual-releases") { exchange ->
                exchange.respond(
                    status = 422,
                    body =
                        """
                        {
                          "error": {
                            "code": "manual_release_validation_failed",
                            "message": "Manual release validation failed.",
                            "field_errors": {
                              "title": "This field is required.",
                              "tracklist.0.title": "Track title is required."
                            }
                          }
                        }
                        """.trimIndent(),
                )
            }
            server.start()
            try {
                val client = VinylApiClient(baseUrl = "http://127.0.0.1:${server.address.port}/api/v1")

                try {
                    client.saveManualRelease(formData = ManualReleaseFormData())
                    fail("Expected validation API error.")
                } catch (error: ApiException) {
                    assertEquals(ApiErrorKind.Validation, error.kind)
                    assertEquals("manual_release_validation_failed", error.code)
                    assertEquals("This field is required.", error.fieldErrors["title"])
                    assertEquals("Track title is required.", error.fieldErrors["tracklist.0.title"])
                }
            } finally {
                server.stop(0)
            }
        }

    private fun com.sun.net.httpserver.HttpExchange.respond(
        status: Int,
        body: String,
    ) {
        responseHeaders.add("Content-Type", "application/json")
        val bytes = body.toByteArray(Charsets.UTF_8)
        sendResponseHeaders(status, bytes.size.toLong())
        responseBody.use { it.write(bytes) }
    }
}
