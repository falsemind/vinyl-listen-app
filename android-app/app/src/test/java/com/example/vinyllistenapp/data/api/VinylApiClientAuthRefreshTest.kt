package com.example.vinyllistenapp.data.api

import com.example.vinyllistenapp.data.auth.AuthSessionRefreshResult
import com.sun.net.httpserver.HttpServer
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
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
