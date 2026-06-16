package com.example.vinyllistenapp.data.api

import android.content.Context
import android.net.Uri
import com.example.vinyllistenapp.BuildConfig
import com.example.vinyllistenapp.domain.ReleaseSearchResult
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID
import kotlin.math.max

private const val DISCOGS_BASE_URL = "https://api.discogs.com"
private const val DISCOGS_UNAUTHENTICATED_LIMIT_PER_MINUTE = 25
private const val DISCOGS_INSTALL_ID_PREF = "discogs_install_id"
private const val DISCOGS_CLIENT_PREFS = "discogs_client"

class DiscogsApiClient(
    context: Context,
    private val baseUrl: String = DISCOGS_BASE_URL,
    private val rateLimiter: DiscogsRateLimiter = DiscogsRateLimiter(DISCOGS_UNAUTHENTICATED_LIMIT_PER_MINUTE),
) {
    private val appContext = context.applicationContext
    private val userAgent: String by lazy { buildDiscogsUserAgent(appContext) }

    suspend fun searchReleases(
        artist: String?,
        title: String?,
        catalog: String?,
        barcode: String?,
        year: Int?,
        limit: Int = 10,
        offset: Int = 0,
    ): ReleaseSearchResultsPage =
        withContext(Dispatchers.IO) {
            rateLimiter.waitForTurn()
            val page = (offset / limit) + 1
            val response =
                getJson(
                    path = "database/search",
                    params =
                        buildList {
                            addQueryParam("type", "release")
                            addQueryParam("artist", artist)
                            addQueryParam("release_title", title)
                            addQueryParam("catno", catalog)
                            addQueryParam("barcode", barcode)
                            addQueryParam("year", year?.toString())
                            addQueryParam("per_page", limit.toString())
                            addQueryParam("page", page.toString())
                        },
                )
            response.toDiscogsReleaseSearchResultsPage(limit = limit)
        }

    suspend fun fetchRelease(discogsReleaseId: Long): JSONObject =
        withContext(Dispatchers.IO) {
            require(discogsReleaseId > 0) { "Discogs release ID must be positive." }
            rateLimiter.waitForTurn()
            getJson(
                path = "releases/$discogsReleaseId",
                params = emptyList(),
            )
        }

    private fun getJson(
        path: String,
        params: List<String>,
    ): JSONObject {
        val query = params.takeIf { it.isNotEmpty() }?.joinToString("&").orEmpty()
        val url = "${baseUrl.trimEnd('/')}/${path.trimStart('/')}${query.takeIf { it.isNotBlank() }?.let { "?$it" }.orEmpty()}"
        val connection =
            (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = 15_000
                readTimeout = 30_000
                setRequestProperty("Accept", "application/json")
                setRequestProperty("User-Agent", userAgent)
            }
        return readJsonResponse(connection)
    }

    private fun readJsonResponse(connection: HttpURLConnection): JSONObject {
        val status = connection.responseCode
        rateLimiter.observeHeaders(
            limit = connection.getHeaderField("X-Discogs-Ratelimit")?.toIntOrNull(),
            remaining = connection.getHeaderField("X-Discogs-Ratelimit-Remaining")?.toIntOrNull(),
        )
        val body =
            if (status in 200..299) {
                connection.inputStream.bufferedReader().use { it.readText() }
            } else {
                connection.errorStream
                    ?.bufferedReader()
                    ?.use { it.readText() }
                    .orEmpty()
            }
        if (status !in 200..299) {
            val message =
                runCatching { JSONObject(body).optString("message") }
                    .getOrNull()
                    ?.takeIf { it.isNotBlank() }
                    ?: "Discogs search failed."
            throw IOException(message)
        }
        return JSONObject(body.ifBlank { "{}" })
    }
}

class DiscogsRateLimiter(
    requestsPerMinute: Int,
    private val nowMillis: () -> Long = { System.currentTimeMillis() },
    private val delayMillis: suspend (Long) -> Unit = { delay(it) },
) {
    private var effectiveLimit = requestsPerMinute
    private var windowStartedAtMillis = 0L
    private var usedInWindow = 0
    private var remainingFromHeaders: Int? = null

    suspend fun waitForTurn() {
        val now = nowMillis()
        if (now - windowStartedAtMillis >= 60_000L) {
            windowStartedAtMillis = now
            usedInWindow = 0
            remainingFromHeaders = null
        }
        val headerRemaining = remainingFromHeaders
        if (usedInWindow >= effectiveLimit || headerRemaining == 0) {
            val waitMillis = max(0L, windowStartedAtMillis + 60_000L - now)
            if (waitMillis > 0L) {
                delayMillis(waitMillis)
            }
            windowStartedAtMillis = nowMillis()
            usedInWindow = 0
            remainingFromHeaders = null
        }
        usedInWindow += 1
    }

    fun observeHeaders(
        limit: Int?,
        remaining: Int?,
    ) {
        if (limit != null && limit > 0) {
            effectiveLimit = minOf(effectiveLimit, limit)
        }
        remainingFromHeaders = remaining
    }
}

private fun buildDiscogsUserAgent(context: Context): String {
    val installId =
        context
            .getSharedPreferences(DISCOGS_CLIENT_PREFS, Context.MODE_PRIVATE)
            .getString(DISCOGS_INSTALL_ID_PREF, null)
            ?: UUID.randomUUID().toString().also { id ->
                context
                    .getSharedPreferences(DISCOGS_CLIENT_PREFS, Context.MODE_PRIVATE)
                    .edit()
                    .putString(DISCOGS_INSTALL_ID_PREF, id)
                    .apply()
            }
    return "VinylListenApp/${BuildConfig.VERSION_NAME} Android Device/$installId"
}

private fun JSONObject.toDiscogsReleaseSearchResultsPage(limit: Int): ReleaseSearchResultsPage {
    val results = optJSONArray("results").orEmpty().mapObjects { item -> item.toDiscogsReleaseSearchResult() }
    val pagination = optJSONObject("pagination")
    val totalPages = pagination?.optInt("pages", 1) ?: 1
    val currentPage = pagination?.optInt("page", 1) ?: 1
    return ReleaseSearchResultsPage(
        results = results,
        hasMore = currentPage < totalPages || results.size == limit,
    )
}

private fun JSONObject.toDiscogsReleaseSearchResult(): ReleaseSearchResult {
    val displayTitle = optString("title", "Unknown artist - Unknown title")
    val parts = displayTitle.split(" - ", limit = 2)
    return ReleaseSearchResult(
        discogsReleaseId = optLong("id"),
        artist = parts.getOrNull(0)?.takeIf { it.isNotBlank() } ?: "Unknown artist",
        title = parts.getOrNull(1)?.takeIf { it.isNotBlank() } ?: displayTitle,
        year = optNullableInt("year"),
        label = optJSONArray("label").orEmpty().mapStrings().firstOrNull(),
        catalogNumber = optNullableString("catno"),
        thumbnailUrl = optNullableString("thumb"),
        format =
            optJSONArray("format")
                .orEmpty()
                .mapStrings()
                .joinToString(", ")
                .takeIf { it.isNotBlank() },
    )
}

private fun MutableList<String>.addQueryParam(
    name: String,
    value: String?,
) {
    val normalizedValue = value?.trim()?.takeIf { it.isNotBlank() } ?: return
    add("${Uri.encode(name)}=${Uri.encode(normalizedValue)}")
}

private fun JSONArray?.orEmpty(): JSONArray = this ?: JSONArray()

private fun JSONArray.mapObjects(transform: (JSONObject) -> ReleaseSearchResult): List<ReleaseSearchResult> =
    (0 until length()).mapNotNull { index -> optJSONObject(index)?.let(transform) }

private fun JSONArray.mapStrings(): List<String> = (0 until length()).mapNotNull { index -> optString(index).takeIf { it.isNotBlank() } }

private fun JSONObject.optNullableString(name: String): String? =
    if (has(name) && !isNull(name)) optString(name).takeIf { it.isNotBlank() } else null

private fun JSONObject.optNullableInt(name: String): Int? = if (has(name) && !isNull(name)) optInt(name) else null
