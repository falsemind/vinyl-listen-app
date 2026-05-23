package com.example.vinyllistenapp.data.api

import android.content.Context
import android.net.Uri
import com.example.vinyllistenapp.BuildConfig
import com.example.vinyllistenapp.domain.AnalyticsDashboard
import com.example.vinyllistenapp.domain.AnalyticsTopRecordSummary
import com.example.vinyllistenapp.domain.HomeSummary
import com.example.vinyllistenapp.domain.ListeningSession
import com.example.vinyllistenapp.domain.MatchCandidate
import com.example.vinyllistenapp.domain.MonthlyPlayCount
import com.example.vinyllistenapp.domain.MoodDistributionItem
import com.example.vinyllistenapp.domain.RatingDistributionItem
import com.example.vinyllistenapp.domain.RecordSummary
import com.example.vinyllistenapp.domain.ReleaseSearchResult
import com.example.vinyllistenapp.domain.ReleaseSideOption
import com.example.vinyllistenapp.domain.StyleDistributionItem
import com.example.vinyllistenapp.domain.TopRecordSummary
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.io.OutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import java.util.Locale
import kotlin.math.roundToInt
import kotlin.random.Random

class VinylApiClient(
    private val baseUrl: String = BuildConfig.VINYL_API_BASE_URL,
    private val retryPolicy: ApiRetryPolicy = ApiRetryPolicy(),
    private val retryJitterMillis: () -> Long = { Random.nextLong(0, retryPolicy.jitterMaxMillis + 1) },
    private val retryDelay: suspend (Long) -> Unit = { delay(it) },
) {
    suspend fun identifyImage(
        context: Context,
        imageUri: Uri,
        onStatus: (IdentifyJobState) -> Unit = {},
    ): List<MatchCandidate> =
        apiCall {
            var job = startIdentifyJob(context, imageUri)
            onStatus(job)
            while (!job.status.isTerminal) {
                delay(750)
                job = getIdentifyJobStatus(job.jobId)
                onStatus(job)
            }
            when (job.status) {
                IdentifyJobStatus.Completed -> job.candidates.orEmpty()
                IdentifyJobStatus.Failed ->
                    throw ApiException(
                        message = job.error?.message ?: "Identify failed. Retry or use Manual Search.",
                        failedStep = job.error?.failedStep,
                    )
                IdentifyJobStatus.Expired ->
                    throw ApiException(
                        message = "Identify result expired. Try another image or search manually.",
                        kind = ApiErrorKind.NotFound,
                        failedStep = "unknown",
                    )
                else -> emptyList()
            }
        }

    suspend fun startIdentifyJob(
        context: Context,
        imageUri: Uri,
    ): IdentifyJobState =
        apiCall {
            val response = postImageMultipart(context, imageUri, "identify/jobs")
            response.toIdentifyJobState()
        }

    suspend fun getIdentifyJobStatus(jobId: String): IdentifyJobState =
        apiCall {
            getJson("identify/jobs/${Uri.encode(jobId)}").toIdentifyJobState()
        }

    suspend fun cancelIdentifyJob(jobId: String): IdentifyJobState =
        apiCall {
            postRetryableJson("identify/jobs/${Uri.encode(jobId)}/cancel", JSONObject()).toIdentifyJobState()
        }

    suspend fun importRelease(discogsReleaseId: Long): String =
        apiCall {
            val body =
                JSONObject()
                    .put("discogs_release_id", discogsReleaseId)
                    .put("force_refresh", false)
            val response = postJson("releases/import", body)
            response.getString("release_id")
        }

    suspend fun searchReleases(
        artist: String?,
        title: String?,
        catalog: String?,
        barcode: String?,
        year: Int?,
        limit: Int = 10,
        offset: Int = 0,
    ): List<ReleaseSearchResult> =
        apiCall {
            val query =
                buildList {
                    addQueryParam("artist", artist)
                    addQueryParam("title", title)
                    addQueryParam("catalog", catalog)
                    addQueryParam("barcode", barcode)
                    addQueryParam("year", year?.toString())
                    addQueryParam("limit", limit.toString())
                    addQueryParam("offset", offset.toString())
                }.joinToString("&")
            val response = getJson("releases/search?$query")
            response.optJSONArray("results").orEmpty().mapObjects { item ->
                ReleaseSearchResult(
                    discogsReleaseId = item.optLong("discogs_release_id"),
                    artist = item.optString("artist", "Unknown artist"),
                    title = item.optString("title", "Unknown title"),
                    year = item.optNullableInt("year"),
                    label = item.optNullableString("label"),
                    catalogNumber = item.optNullableString("catalog_number"),
                    thumbnailUrl = item.optNullableString("thumbnail_url"),
                    format = item.optNullableString("format"),
                )
            }
        }

    suspend fun getRelease(releaseId: String): RecordSummary =
        apiCall {
            val response = getJson("releases/${Uri.encode(releaseId)}")
            response.toRecordSummary()
        }

    suspend fun getReleaseSessions(releaseId: String): List<ListeningSession> =
        apiCall {
            val response = getJson("releases/${Uri.encode(releaseId)}/sessions")
            response.optJSONArray("sessions").orEmpty().mapObjects { item ->
                ListeningSession(
                    releaseId = releaseId,
                    artist = "",
                    title = "",
                    playedAt = item.optNullableString("played_at") ?: item.optNullableString("date") ?: "Unknown date",
                    mood = item.optNullableString("mood") ?: "Unspecified",
                    rating = item.optNullableInt("rating") ?: 0,
                    side = item.optNullableString("side"),
                    hasNotes = item.optBoolean("has_notes", false),
                    notes = item.optNullableString("notes"),
                )
            }
        }

    suspend fun getHomeSummary(
        recentLimit: Int = 5,
        topLimit: Int = 3,
    ): HomeSummary =
        apiCall {
            val response = getJson("sessions/summary?recent_limit=$recentLimit&top_limit=$topLimit")
            HomeSummary(
                recentSessions =
                    response.optJSONArray("recent_sessions").orEmpty().mapObjects { item ->
                        ListeningSession(
                            releaseId = item.getString("release_id"),
                            artist = item.optString("artist", "Unknown artist"),
                            title = item.optString("title", "Unknown title"),
                            playedAt = item.optNullableString("played_at") ?: item.optNullableString("date") ?: "Unknown date",
                            mood = item.optNullableString("mood") ?: "Unspecified",
                            rating = item.optNullableInt("rating") ?: 0,
                            thumbnailUrl = item.optNullableString("thumbnail_url"),
                            side = item.optNullableString("side"),
                            hasNotes = item.optBoolean("has_notes", false),
                            notes = item.optNullableString("notes"),
                        )
                    },
                totalSessions = response.optInt("total_sessions", 0),
                recordsThisMonth = response.optInt("records_this_month", 0),
                topRecords =
                    response.optJSONArray("top_records").orEmpty().mapObjects { item ->
                        TopRecordSummary(
                            record =
                                RecordSummary(
                                    releaseId = item.getString("release_id"),
                                    discogsReleaseId = 0,
                                    artist = item.optString("artist", "Unknown artist"),
                                    title = item.optString("title", "Unknown title"),
                                    label = "",
                                    year = null,
                                    format = "Vinyl",
                                    rating = 0,
                                    lastPlayed = "",
                                    coverImageUrl = item.optNullableString("thumbnail_url"),
                                ),
                            plays = item.optInt("plays", 0),
                            averageRating = item.optNullableDouble("average_rating")?.let { String.format(Locale.US, "%.1f", it) } ?: "-",
                        )
                    },
            )
        }

    suspend fun getAnalyticsDashboard(topRecordsLimit: Int = 10): AnalyticsDashboard =
        apiCall {
            AnalyticsDashboard(
                monthlyPlays =
                    getJson("analytics/plays/monthly")
                        .optJSONArray("data")
                        .orEmpty()
                        .mapObjects { item ->
                            MonthlyPlayCount(
                                month = item.optString("month", "Unknown"),
                                plays = item.optInt("plays", 0),
                            )
                        },
                topRecords =
                    getJson("analytics/top-records?limit=$topRecordsLimit")
                        .optJSONArray("records")
                        .orEmpty()
                        .mapObjects { item ->
                            AnalyticsTopRecordSummary(
                                record =
                                    RecordSummary(
                                        releaseId = item.getString("release_id"),
                                        discogsReleaseId = item.optLong("discogs_release_id"),
                                        artist = item.optString("artist", "Unknown artist"),
                                        title = item.optString("title", "Unknown title"),
                                        label = "",
                                        year = null,
                                        format = "Vinyl",
                                        rating = 0,
                                        lastPlayed = "",
                                        coverImageUrl = item.optNullableString("thumbnail_url"),
                                    ),
                                plays = item.optInt("plays", 0),
                                averageRating =
                                    item
                                        .optNullableDouble("average_rating")
                                        ?.let { String.format(Locale.US, "%.1f", it) }
                                        ?: "-",
                            )
                        },
                ratingDistribution =
                    getJson("analytics/rating-distribution")
                        .optJSONObject("ratings")
                        .orEmpty()
                        .intEntries()
                        .mapNotNull { (rating, count) ->
                            rating.toIntOrNull()?.let { RatingDistributionItem(rating = it, count = count) }
                        }.sortedByDescending { it.rating },
                moodDistribution =
                    getJson("analytics/mood-distribution")
                        .optJSONObject("moods")
                        .orEmpty()
                        .intEntries()
                        .map { (mood, count) -> MoodDistributionItem(mood = mood, count = count) }
                        .sortedByDescending { it.count },
                styleDistribution =
                    getJson("analytics/style-distribution")
                        .optJSONObject("styles")
                        .orEmpty()
                        .intEntries()
                        .map { (style, count) -> StyleDistributionItem(style = style, count = count) }
                        .sortedByDescending { it.count },
            )
        }

    suspend fun createSession(
        releaseId: String,
        side: String?,
        rating: Int?,
        mood: String?,
        notes: String?,
    ): String =
        apiCall {
            val body =
                JSONObject()
                    .put("release_id", releaseId)
                    .put("played_at", Instant.now().toString())
                    .putNullable("side", side)
                    .putNullable("rating", rating)
                    .putNullable("mood", mood)
                    .putNullable("notes", notes?.takeIf { it.isNotBlank() })
            postJson("sessions/", body).getString("session_id")
        }

    suspend fun getCustomMoods(): List<String> =
        apiCall {
            getJson("sessions/moods")
                .optJSONArray("moods")
                .orEmpty()
                .mapObjects { item -> item.optString("name") }
                .filter { it.isNotBlank() }
        }

    suspend fun createCustomMood(name: String): String =
        apiCall {
            val body = JSONObject().put("name", name)
            postJson("sessions/moods", body)
                .optJSONObject("mood")
                ?.optString("name")
                ?.takeIf { it.isNotBlank() }
                ?: name
        }

    suspend fun deleteCustomMood(name: String) {
        apiCall {
            deleteJson("sessions/moods/${Uri.encode(name)}")
        }
    }

    suspend fun chatWithAi(
        message: String,
        conversationId: String? = null,
    ): AiChatResponse =
        apiCall {
            val body = JSONObject().put("message", message)
            conversationId?.let { body.put("conversation_id", it) }
            val response = postJson("ai/chat", body)
            val assistantMessage = response.getJSONObject("message")
            AiChatResponse(
                conversationId = response.getString("conversation_id"),
                content = assistantMessage.getString("content"),
                usedTools = response.optJSONArray("used_tools").orEmpty().mapStrings(),
            )
        }

    private suspend fun <T> apiCall(block: suspend () -> T): T =
        withContext(Dispatchers.IO) {
            try {
                block()
            } catch (error: ApiException) {
                throw error
            } catch (error: IOException) {
                throw ApiException(
                    message = "Service unavailable.",
                    kind = ApiErrorKind.Offline,
                    cause = error,
                )
            }
        }

    private suspend fun getJson(path: String): JSONObject =
        withRetry(ApiHttpMethod.Get) {
            val connection = openConnection(path)
            connection.requestMethod = "GET"
            readJsonResponse(connection)
        }

    private fun postImageMultipart(
        context: Context,
        imageUri: Uri,
        path: String,
    ): JSONObject {
        val resolver = context.contentResolver
        val mimeType = resolver.getType(imageUri) ?: "image/jpeg"
        val filename = imageUri.lastPathSegment?.substringAfterLast('/')?.ifBlank { null } ?: "record.jpg"
        val imageBytes =
            resolver.openInputStream(imageUri)?.use { it.readBytes() }
                ?: throw ApiException("Could not read selected image.", failedStep = "upload")
        val boundary = "VinylListenBoundary${System.currentTimeMillis()}"
        val connection = openConnection(path)

        connection.requestMethod = "POST"
        connection.doOutput = true
        connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
        connection.outputStream.use { output ->
            output.writeUtf8("--$boundary\r\n")
            output.writeUtf8("Content-Disposition: form-data; name=\"image\"; filename=\"$filename\"\r\n")
            output.writeUtf8("Content-Type: $mimeType\r\n\r\n")
            output.write(imageBytes)
            output.writeUtf8("\r\n--$boundary--\r\n")
        }

        return readJsonResponse(connection)
    }

    private fun postJson(
        path: String,
        body: JSONObject,
    ): JSONObject {
        val connection = openConnection(path)
        connection.requestMethod = "POST"
        connection.doOutput = true
        connection.setRequestProperty("Content-Type", "application/json")
        connection.outputStream.use { it.writeUtf8(body.toString()) }
        return readJsonResponse(connection)
    }

    private suspend fun postRetryableJson(
        path: String,
        body: JSONObject,
    ): JSONObject =
        withRetry(ApiHttpMethod.RetryablePost) {
            postJson(path, body)
        }

    private fun deleteJson(path: String): JSONObject {
        val connection = openConnection(path)
        connection.requestMethod = "DELETE"
        return readJsonResponse(connection)
    }

    private fun openConnection(path: String): HttpURLConnection =
        URL("${baseUrl.trimEnd('/')}/${path.trimStart('/')}").openConnection().let { connection ->
            (connection as HttpURLConnection).apply {
                connectTimeout = 15_000
                readTimeout = 60_000
                setRequestProperty("Accept", "application/json")
            }
        }

    private fun readJsonResponse(connection: HttpURLConnection): JSONObject {
        val status = connection.responseCode
        val retryAfterMillis = parseRetryAfterMillis(connection.getHeaderField("Retry-After"))
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
            val errorBody = runCatching { JSONObject(body) }.getOrNull()
            val errorObject = errorBody?.optJSONObject("error")
            val code = errorObject?.optNullableString("code")
            val rawMessage =
                errorObject?.optNullableString("message")
                    ?: errorBody?.optNullableString("detail")
                    ?: body.takeIf { it.isNotBlank() }
            val kind = status.toApiErrorKind()
            throw ApiException(
                message = apiErrorMessage(status, code, rawMessage, retryAfterMillis),
                kind = kind,
                statusCode = status,
                retryAfterMillis = retryAfterMillis,
            )
        }
        return JSONObject(body.ifBlank { "{}" })
    }

    private suspend fun <T> withRetry(
        method: ApiHttpMethod,
        block: () -> T,
    ): T {
        var attempt = 1
        while (true) {
            try {
                return block()
            } catch (error: ApiException) {
                if (!retryPolicy.shouldRetry(method, attempt, statusCode = error.statusCode)) throw error
                retryDelay(retryPolicy.delayMillis(attempt, error.retryAfterMillis, retryJitterMillis()))
            } catch (error: IOException) {
                if (!retryPolicy.shouldRetry(method, attempt, isNetworkFailure = true)) throw error
                retryDelay(retryPolicy.delayMillis(attempt, retryAfterMillis = null, retryJitterMillis()))
            }
            attempt += 1
        }
    }
}

enum class ApiErrorKind {
    Offline,
    RateLimited,
    Validation,
    NotFound,
    Server,
    Unknown,
}

class ApiException(
    message: String,
    val kind: ApiErrorKind = ApiErrorKind.Unknown,
    val failedStep: String? = null,
    val statusCode: Int? = null,
    val retryAfterMillis: Long? = null,
    cause: Throwable? = null,
) : Exception(message, cause)

data class AiChatResponse(
    val conversationId: String,
    val content: String,
    val usedTools: List<String>,
)

fun Throwable.toUserMessage(fallback: String): String = (this as? ApiException)?.message ?: fallback

private fun OutputStream.writeUtf8(value: String) {
    write(value.toByteArray(Charsets.UTF_8))
}

private fun MutableList<String>.addQueryParam(
    name: String,
    value: String?,
) {
    val normalizedValue = value?.trim()?.takeIf { it.isNotBlank() } ?: return
    add("${Uri.encode(name)}=${Uri.encode(normalizedValue)}")
}

private fun JSONObject.toRecordSummary(): RecordSummary =
    RecordSummary(
        releaseId = getString("id"),
        discogsReleaseId = optLong("discogs_release_id"),
        artist = optString("artist", "Unknown artist"),
        title = optString("title", "Unknown title"),
        label = optNullableString("label") ?: "Unknown label",
        year = optNullableInt("year"),
        format = "Vinyl",
        rating = 0,
        lastPlayed = "Not logged yet",
        catalogNumber = optNullableString("catalog_number"),
        barcode = optNullableString("barcode"),
        genres = optJSONArray("genres").orEmpty().mapStrings(),
        styles = optJSONArray("styles").orEmpty().mapStrings(),
        coverImageUrl = optNullableString("cover_image_url"),
        availableSides = optJSONArray("available_sides").orEmpty().mapStrings(),
        availableSideOptions = optJSONArray("available_side_options").orEmpty().toReleaseSideOptions(),
    )

private fun JSONObject.putNullable(
    name: String,
    value: Any?,
): JSONObject =
    apply {
        if (value == null) {
            put(name, JSONObject.NULL)
        } else {
            put(name, value)
        }
    }

data class IdentifyJobState(
    val jobId: String,
    val status: IdentifyJobStatus,
    val message: String,
    val candidates: List<MatchCandidate>? = null,
    val error: IdentifyJobError? = null,
    val cancelRequested: Boolean = false,
)

enum class IdentifyJobStatus(
    val wireValue: String,
) {
    Queued("queued"),
    UploadReceived("upload_received"),
    PreprocessingImage("preprocessing_image"),
    ExtractingText("extracting_text"),
    ParsingIdentifiers("parsing_identifiers"),
    SearchingLocal("searching_local"),
    SearchingDiscogs("searching_discogs"),
    RankingCandidates("ranking_candidates"),
    Completed("completed"),
    Failed("failed"),
    Expired("expired"),
    Canceled("canceled"),
    Unknown("unknown"),
    ;

    val isTerminal: Boolean
        get() = this == Completed || this == Failed || this == Expired || this == Canceled

    companion object {
        fun fromWireValue(value: String): IdentifyJobStatus = entries.firstOrNull { it.wireValue == value } ?: Unknown
    }
}

data class IdentifyJobError(
    val code: String,
    val message: String,
    val failedStep: String,
)

internal fun JSONObject.toIdentifyJobState(): IdentifyJobState {
    val result = optJSONObject("result")
    val error = optJSONObject("error")
    return IdentifyJobState(
        jobId = getString("job_id"),
        status = IdentifyJobStatus.fromWireValue(optString("status", "unknown")),
        message = optString("message", ""),
        candidates = result?.optJSONArray("candidates")?.toMatchCandidates(),
        error =
            error?.let {
                IdentifyJobError(
                    code = it.optString("code", "identify_failed"),
                    message = it.optString("message", "Identify failed. Retry or use Manual Search."),
                    failedStep = it.optString("failed_step", "unknown"),
                )
            },
        cancelRequested = optBoolean("cancel_requested", false),
    )
}

private fun JSONArray.toMatchCandidates(): List<MatchCandidate> =
    mapObjects { candidate ->
        MatchCandidate(
            releaseId = candidate.optNullableString("release_id"),
            discogsReleaseId = candidate.optLong("discogs_release_id"),
            artist = candidate.optString("artist", "Unknown artist"),
            title = candidate.optString("title", "Unknown title"),
            label = candidate.optNullableString("label") ?: "Unknown label",
            confidence = candidate.optConfidence(),
            year = candidate.optNullableInt("year"),
            catalogNumber = candidate.optNullableString("catalog_number"),
            barcode = candidate.optNullableString("barcode"),
            coverImageUrl = candidate.optNullableString("cover_image_url"),
            format = candidate.optNullableString("format"),
            matchSource = candidate.optNullableString("match_source"),
            matchedOn = candidate.optJSONArray("matched_on").orEmpty().mapStrings(),
        )
    }

private fun JSONObject.optNullableString(name: String): String? = if (isNull(name)) null else optString(name).takeIf { it.isNotBlank() }

private fun JSONObject.optNullableInt(name: String): Int? = if (isNull(name)) null else optInt(name)

private fun JSONObject.optNullableDouble(name: String): Double? = if (isNull(name)) null else optDouble(name)

private fun Int.toApiErrorKind(): ApiErrorKind =
    when (this) {
        429 -> ApiErrorKind.RateLimited
        404 -> ApiErrorKind.NotFound
        422 -> ApiErrorKind.Validation
        in 500..599 -> ApiErrorKind.Server
        else -> ApiErrorKind.Unknown
    }

private fun apiErrorMessage(
    status: Int,
    code: String?,
    rawMessage: String?,
): String =
    when {
        code == "identify_capacity_exceeded" || status == 429 -> rateLimitMessage(retryAfterMillis = null)
        code == "invalid_side" -> "That side is not available for this release."
        code == "invalid_rating" -> "Rating must be between 1 and 5."
        code == "invalid_played_at" -> "Session time was invalid. Try saving again."
        code == "release_not_found" -> "This release is not available locally yet."
        status == 404 -> "Could not find that record."
        status in 500..599 -> "Backend error. Retry in a moment."
        !rawMessage.isNullOrBlank() -> rawMessage
        else -> "Request failed. Retry in a moment."
    }

private fun apiErrorMessage(
    status: Int,
    code: String?,
    rawMessage: String?,
    retryAfterMillis: Long?,
): String =
    when {
        code == "identify_capacity_exceeded" || status == 429 -> rateLimitMessage(retryAfterMillis)
        else -> apiErrorMessage(status, code, rawMessage)
    }

internal fun rateLimitMessage(retryAfterMillis: Long?): String {
    val seconds = retryAfterMillis?.takeIf { it > 0 }?.let { (it + 999) / 1_000 }
    return seconds?.let { "Backend is busy. Retry in $it seconds." }
        ?: "Backend is busy. Retry in a moment."
}

private fun JSONObject.optConfidence(): Int {
    val rawConfidence = optDouble("confidence", 0.0)
    val percent = if (rawConfidence <= 1.0) rawConfidence * 100.0 else rawConfidence
    return percent.roundToInt().coerceIn(0, 100)
}

private fun JSONArray?.orEmpty(): JSONArray = this ?: JSONArray()

private fun JSONObject?.orEmpty(): JSONObject = this ?: JSONObject()

private fun JSONArray.mapStrings(): List<String> = List(length()) { index -> optString(index) }.filter { it.isNotBlank() }

private fun JSONArray.toReleaseSideOptions(): List<ReleaseSideOption> =
    mapObjects { item ->
        ReleaseSideOption(
            value = item.optString("value"),
            label = item.optString("label"),
        )
    }.filter { it.value.isNotBlank() && it.label.isNotBlank() }

private fun <T> JSONArray.mapObjects(transform: (JSONObject) -> T): List<T> = List(length()) { index -> transform(getJSONObject(index)) }

private fun JSONObject.intEntries(): List<Pair<String, Int>> =
    buildList {
        val keys = keys()
        while (keys.hasNext()) {
            val key = keys.next()
            add(key to optInt(key, 0))
        }
    }
