package com.example.vinyllistenapp.data.api

import android.content.Context
import android.net.Uri
import com.example.vinyllistenapp.BuildConfig
import com.example.vinyllistenapp.data.auth.AuthAccountSummary
import com.example.vinyllistenapp.data.auth.AuthDeleteAccountResult
import com.example.vinyllistenapp.data.auth.AuthLogoutAllResult
import com.example.vinyllistenapp.data.auth.AuthPasswordChangeResult
import com.example.vinyllistenapp.data.auth.AuthPasswordResetRequestResult
import com.example.vinyllistenapp.data.auth.AuthRegistrationResult
import com.example.vinyllistenapp.data.auth.AuthSessionRefreshResult
import com.example.vinyllistenapp.data.auth.AuthTokenPair
import com.example.vinyllistenapp.data.auth.AuthVerificationResendResult
import com.example.vinyllistenapp.domain.AnalyticsDashboard
import com.example.vinyllistenapp.domain.AnalyticsPagination
import com.example.vinyllistenapp.domain.AnalyticsRecordCountItem
import com.example.vinyllistenapp.domain.AnalyticsRecordCountsPage
import com.example.vinyllistenapp.domain.AnalyticsSessionsPage
import com.example.vinyllistenapp.domain.AnalyticsTopRecordSummary
import com.example.vinyllistenapp.domain.CollectionFolder
import com.example.vinyllistenapp.domain.CollectionFoldersPage
import com.example.vinyllistenapp.domain.CollectionRecord
import com.example.vinyllistenapp.domain.CollectionRecordsPage
import com.example.vinyllistenapp.domain.CollectionSourceOfTruth
import com.example.vinyllistenapp.domain.DiscogsIntegrationStatus
import com.example.vinyllistenapp.domain.HomeSummary
import com.example.vinyllistenapp.domain.ListeningSession
import com.example.vinyllistenapp.domain.ManualReleaseCompletionState
import com.example.vinyllistenapp.domain.ManualReleaseCoverUploadResult
import com.example.vinyllistenapp.domain.ManualReleaseDraft
import com.example.vinyllistenapp.domain.ManualReleaseDraftList
import com.example.vinyllistenapp.domain.ManualReleaseDraftSummary
import com.example.vinyllistenapp.domain.ManualReleaseFormData
import com.example.vinyllistenapp.domain.ManualReleaseFormat
import com.example.vinyllistenapp.domain.ManualReleaseLimits
import com.example.vinyllistenapp.domain.ManualReleaseSaveResult
import com.example.vinyllistenapp.domain.ManualReleaseTrackCreditInput
import com.example.vinyllistenapp.domain.ManualReleaseTrackCreditRole
import com.example.vinyllistenapp.domain.ManualReleaseTrackInput
import com.example.vinyllistenapp.domain.ManualReleaseVinylSize
import com.example.vinyllistenapp.domain.ManualReleaseVinylSpeed
import com.example.vinyllistenapp.domain.MatchCandidate
import com.example.vinyllistenapp.domain.MonthlyPlayCount
import com.example.vinyllistenapp.domain.MoodDistributionItem
import com.example.vinyllistenapp.domain.RatingDistributionItem
import com.example.vinyllistenapp.domain.RecordFlowInsights
import com.example.vinyllistenapp.domain.RecordFlowMoodTransition
import com.example.vinyllistenapp.domain.RecordFlowReleaseSummary
import com.example.vinyllistenapp.domain.RecordSummary
import com.example.vinyllistenapp.domain.ReleaseArtist
import com.example.vinyllistenapp.domain.ReleaseSearchResult
import com.example.vinyllistenapp.domain.ReleaseSideOption
import com.example.vinyllistenapp.domain.ReleaseTrack
import com.example.vinyllistenapp.domain.ReleaseTrackArtist
import com.example.vinyllistenapp.domain.ReleaseTrackCredit
import com.example.vinyllistenapp.domain.SessionTrack
import com.example.vinyllistenapp.domain.StyleDistributionItem
import com.example.vinyllistenapp.domain.TimedSessionGroup
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
    @Volatile
    private var accessToken: String? = null
    private var refreshAccessToken: (suspend () -> AuthSessionRefreshResult)? = null

    fun setAccessToken(token: String?) {
        accessToken = token?.takeIf { it.isNotBlank() }
    }

    fun setAuthSessionRefresher(refresher: (suspend () -> AuthSessionRefreshResult)?) {
        refreshAccessToken = refresher
    }

    suspend fun refreshAuthSession(refreshToken: String): AuthTokenPair =
        apiCall(allowAuthRefresh = false) {
            val body = JSONObject().put("refresh_token", refreshToken)
            postJson("auth/refresh", body).toAuthTokenPair()
        }

    suspend fun registerAccount(
        email: String,
        password: String,
    ): AuthRegistrationResult =
        apiCall(allowAuthRefresh = false) {
            val body =
                JSONObject()
                    .put("email", email)
                    .put("password", password)
            postJson("auth/register", body).toAuthRegistrationResult()
        }

    suspend fun verifyEmail(
        email: String,
        code: String,
    ): AuthAccountSummary =
        apiCall(allowAuthRefresh = false) {
            val body =
                JSONObject()
                    .put("email", email)
                    .put("code", code)
            postJson("auth/verify-email", body).toAuthAccountSummary()
        }

    suspend fun resendEmailVerification(email: String): AuthVerificationResendResult =
        apiCall(allowAuthRefresh = false) {
            val body = JSONObject().put("email", email)
            postJson("auth/resend-verification", body).toAuthVerificationResendResult()
        }

    suspend fun login(
        email: String,
        password: String,
        deviceLabel: String?,
    ): AuthTokenPair =
        apiCall(allowAuthRefresh = false) {
            val body =
                JSONObject()
                    .put("email", email)
                    .put("password", password)
                    .put("device_label", deviceLabel)
            postJson("auth/login", body).toAuthTokenPair()
        }

    suspend fun requestPasswordReset(email: String): AuthPasswordResetRequestResult =
        apiCall(allowAuthRefresh = false) {
            val body = JSONObject().put("email", email)
            postJson("auth/password-reset/request", body).toAuthPasswordResetRequestResult()
        }

    suspend fun requestCurrentAccountPasswordReset(): AuthPasswordResetRequestResult =
        apiCall {
            postJson("auth/password-reset/request-current", JSONObject()).toAuthPasswordResetRequestResult()
        }

    suspend fun confirmPasswordReset(
        email: String,
        code: String,
        newPassword: String,
    ): AuthAccountSummary =
        apiCall(allowAuthRefresh = false) {
            val body =
                JSONObject()
                    .put("email", email)
                    .put("code", code)
                    .put("new_password", newPassword)
            postJson("auth/password-reset/confirm", body).toAuthAccountSummary()
        }

    suspend fun confirmCurrentAccountPasswordReset(
        code: String,
        newPassword: String,
    ): AuthAccountSummary =
        apiCall {
            val body =
                JSONObject()
                    .put("code", code)
                    .put("new_password", newPassword)
            postJson("auth/password-reset/confirm-current", body).toAuthAccountSummary()
        }

    suspend fun changePassword(
        currentPassword: String,
        newPassword: String,
        signOutEverywhere: Boolean,
    ): AuthPasswordChangeResult =
        apiCall {
            val body =
                JSONObject()
                    .put("current_password", currentPassword)
                    .put("new_password", newPassword)
                    .put("sign_out_everywhere", signOutEverywhere)
            postJson("auth/password/change", body).toAuthPasswordChangeResult()
        }

    suspend fun logout(): Boolean =
        apiCall {
            postJson("auth/logout", JSONObject()).optBoolean("revoked", false)
        }

    suspend fun logoutAll(): AuthLogoutAllResult =
        apiCall {
            postJson("auth/logout-all", JSONObject()).toAuthLogoutAllResult()
        }

    suspend fun deleteAccount(password: String): AuthDeleteAccountResult =
        apiCall {
            val body = JSONObject().put("password", password)
            deleteJson("auth/account", body).toAuthDeleteAccountResult()
        }

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
                        code = job.error?.code,
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

    suspend fun syncCollection(onStatus: (CollectionSyncJobState) -> Unit = {}): CollectionSyncJobState =
        apiCall {
            waitForCollectionSyncJob(startCollectionSyncJob(), onStatus)
        }

    suspend fun waitForCollectionSyncJob(
        jobId: String,
        onStatus: (CollectionSyncJobState) -> Unit = {},
    ): CollectionSyncJobState =
        apiCall {
            waitForCollectionSyncJob(fetchCollectionSyncJobStatus(jobId), onStatus)
        }

    suspend fun startCollectionSyncJob(): CollectionSyncJobState =
        apiCall {
            postRetryableJson("collection/sync", JSONObject()).toCollectionSyncJobState()
        }

    suspend fun getCollectionSyncJobStatus(jobId: String): CollectionSyncJobState =
        apiCall {
            fetchCollectionSyncJobStatus(jobId)
        }

    suspend fun getActiveCollectionSyncJob(): CollectionSyncJobState? =
        apiCall {
            getNullableJson("collection/sync/active")?.toCollectionSyncJobState()
        }

    suspend fun getCollectionReleases(
        limit: Int = 25,
        offset: Int = 0,
        artist: String? = null,
        label: String? = null,
        favorite: Boolean = false,
        folderId: Long? = null,
    ): CollectionRecordsPage =
        apiCall {
            val query =
                buildList {
                    addQueryParam("limit", limit.toString())
                    addQueryParam("offset", offset.toString())
                    addQueryParam("artist", artist)
                    addQueryParam("label", label)
                    if (favorite) addQueryParam("favorite", "true")
                    folderId?.let { addQueryParam("folder_id", it.toString()) }
                }.joinToString("&")
            getJson("collection/releases?$query").toCollectionRecordsPage()
        }

    suspend fun getCollectionFolders(): CollectionFoldersPage =
        apiCall {
            getJson("collection/folders").toCollectionFoldersPage()
        }

    suspend fun getCollectionSettings(): CollectionSourceOfTruth =
        apiCall {
            getJson("collection/settings").toCollectionSourceOfTruth()
        }

    suspend fun updateCollectionSettings(sourceOfTruth: CollectionSourceOfTruth): CollectionSourceOfTruth =
        apiCall {
            val body = JSONObject().put("source_of_truth", sourceOfTruth.toWireValue())
            putJson("collection/settings", body).toCollectionSourceOfTruth()
        }

    suspend fun getDiscogsIntegrationStatus(): DiscogsIntegrationStatus =
        apiCall {
            getJson("integrations/discogs").toDiscogsIntegrationStatus()
        }

    suspend fun saveDiscogsAccessToken(accessToken: String): DiscogsIntegrationStatus =
        apiCall {
            val body = JSONObject().put("access_token", accessToken)
            putJson("integrations/discogs/token", body).toDiscogsIntegrationStatus()
        }

    suspend fun deleteDiscogsAccessToken(): DiscogsIntegrationStatus =
        apiCall {
            deleteJson("integrations/discogs/token").toDiscogsIntegrationStatus()
        }

    suspend fun listManualReleaseDrafts(): ManualReleaseDraftList =
        apiCall {
            getJson("manual-releases/drafts").toManualReleaseDraftList()
        }

    suspend fun createManualReleaseDraft(
        formData: ManualReleaseFormData,
        completionState: ManualReleaseCompletionState? = null,
    ): ManualReleaseDraft =
        apiCall {
            postJson("manual-releases/drafts", manualReleaseDraftBody(formData, completionState)).toManualReleaseDraft()
        }

    suspend fun updateManualReleaseDraft(
        draftId: String,
        formData: ManualReleaseFormData,
        completionState: ManualReleaseCompletionState? = null,
    ): ManualReleaseDraft =
        apiCall {
            putJson(
                "manual-releases/drafts/${Uri.encode(draftId)}",
                manualReleaseDraftBody(formData, completionState),
            ).toManualReleaseDraft()
        }

    suspend fun deleteManualReleaseDraft(draftId: String) {
        apiCall {
            deleteJson("manual-releases/drafts/${Uri.encode(draftId)}")
        }
    }

    suspend fun saveManualRelease(
        formData: ManualReleaseFormData? = null,
        draftId: String? = null,
    ): ManualReleaseSaveResult =
        apiCall {
            val body = JSONObject()
            formData?.let { body.put("form_data", it.toJson()) }
            draftId?.let { body.put("draft_id", it) }
            postJson("manual-releases", body).toManualReleaseSaveResult()
        }

    suspend fun uploadManualReleaseDraftCover(
        context: Context,
        draftId: String,
        imageUri: Uri,
    ): ManualReleaseCoverUploadResult =
        apiCall {
            val contentType = validateManualReleaseCoverContentType(context.contentResolver.getType(imageUri))
            postImageMultipart(
                context = context,
                imageUri = imageUri,
                path = "manual-releases/drafts/${Uri.encode(draftId)}/cover",
                fieldName = "file",
                contentType = contentType,
            ).toManualReleaseCoverUploadResult()
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

    suspend fun importReleaseToCollection(discogsReleaseId: Long): String =
        apiCall {
            val body =
                JSONObject()
                    .put("discogs_release_id", discogsReleaseId)
                    .put("force_refresh", false)
            val response = postJson("releases/import-to-collection", body)
            response.getString("release_id")
        }

    suspend fun importClientDiscogsRelease(discogsRelease: JSONObject): String =
        apiCall {
            val body = JSONObject().put("discogs_release", discogsRelease)
            val response = postJson("releases/import/client-discogs", body)
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
    ): ReleaseSearchResultsPage =
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
            response.toReleaseSearchResultsPage(limit = limit)
        }

    suspend fun searchCollectionReleases(
        artist: String?,
        title: String?,
        catalog: String?,
        barcode: String?,
        year: Int?,
        limit: Int = 10,
        offset: Int = 0,
    ): ReleaseSearchResultsPage =
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
            val response = getJson("collection/search?$query")
            response.toReleaseSearchResultsPage(limit = limit)
        }

    suspend fun getRelease(releaseId: String): RecordSummary =
        apiCall {
            val response = getJson("releases/${Uri.encode(releaseId)}")
            response.toRecordSummary()
        }

    suspend fun refreshRelease(releaseId: String): RecordSummary =
        apiCall {
            val response = postJson("releases/${Uri.encode(releaseId)}/refresh", JSONObject())
            response.toRecordSummary()
        }

    suspend fun setReleaseFavorite(
        releaseId: String,
        isFavorite: Boolean,
    ): RecordSummary =
        apiCall {
            val body = JSONObject().put("is_favorite", isFavorite)
            val response = patchJson("releases/${Uri.encode(releaseId)}/favorite", body)
            response.toRecordSummary()
        }

    suspend fun deactivateReleaseCollectionMembership(releaseId: String): RecordSummary =
        apiCall {
            postJson("releases/${Uri.encode(releaseId)}/collection/deactivate", JSONObject()).toRecordSummary()
        }

    suspend fun reactivateReleaseCollectionMembership(releaseId: String): RecordSummary =
        apiCall {
            postJson("releases/${Uri.encode(releaseId)}/collection/reactivate", JSONObject()).toRecordSummary()
        }

    suspend fun getReleaseSessions(releaseId: String): List<ListeningSession> =
        apiCall {
            val response = getJson("releases/${Uri.encode(releaseId)}/sessions")
            response.optJSONArray("sessions").orEmpty().mapObjects { item ->
                item.toListeningSession(
                    fallbackReleaseId = releaseId,
                    fallbackArtist = "",
                    fallbackTitle = "",
                )
            }
        }

    suspend fun getReleaseFlowInsights(
        releaseId: String,
        limit: Int = 5,
        period: String = "3m",
    ): RecordFlowInsights =
        apiCall {
            val query =
                buildList {
                    addQueryParam("limit", limit.toString())
                    addQueryParam("period", period)
                }.toQueryString()
            val response = getJson("releases/${Uri.encode(releaseId)}/flow-insights$query")
            response.toRecordFlowInsights()
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
                        item.toListeningSession()
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
                                topTrack = item.optNullableString("top_track"),
                                topMood = item.optNullableString("top_mood"),
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

    suspend fun getAnalyticsSessionsForMonth(
        month: String,
        limit: Int = 10,
        offset: Int = 0,
    ): AnalyticsSessionsPage =
        apiCall {
            val query =
                mutableListOf<String>()
                    .apply {
                        addQueryParam("month", month)
                        addQueryParam("limit", limit.toString())
                        addQueryParam("offset", offset.toString())
                    }.toQueryString()
            getJson("analytics/sessions$query").toAnalyticsSessionsPage()
        }

    suspend fun getAnalyticsRecordsByRating(
        rating: Int,
        limit: Int = 10,
        offset: Int = 0,
    ): AnalyticsRecordCountsPage =
        apiCall {
            val query =
                mutableListOf<String>()
                    .apply {
                        addQueryParam("rating", rating.toString())
                        addQueryParam("limit", limit.toString())
                        addQueryParam("offset", offset.toString())
                    }.toQueryString()
            getJson("analytics/records/by-rating$query").toAnalyticsRecordCountsPage()
        }

    suspend fun getAnalyticsRecordsByMood(
        mood: String,
        limit: Int = 10,
        offset: Int = 0,
    ): AnalyticsRecordCountsPage =
        apiCall {
            val query =
                mutableListOf<String>()
                    .apply {
                        addQueryParam("mood", mood)
                        addQueryParam("limit", limit.toString())
                        addQueryParam("offset", offset.toString())
                    }.toQueryString()
            getJson("analytics/records/by-mood$query").toAnalyticsRecordCountsPage()
        }

    suspend fun getAnalyticsRecordsByStyle(
        style: String,
        limit: Int = 10,
        offset: Int = 0,
    ): AnalyticsRecordCountsPage =
        apiCall {
            val query =
                mutableListOf<String>()
                    .apply {
                        addQueryParam("style", style)
                        addQueryParam("limit", limit.toString())
                        addQueryParam("offset", offset.toString())
                    }.toQueryString()
            getJson("analytics/records/by-style$query").toAnalyticsRecordCountsPage()
        }

    suspend fun createSession(
        releaseId: String,
        sessionGroupId: String? = null,
        side: String?,
        trackPositions: List<String> = emptyList(),
        rating: Int?,
        mood: String?,
        notes: String?,
    ): String =
        apiCall {
            val body =
                JSONObject()
                    .put("release_id", releaseId)
                    .put("played_at", Instant.now().toString())
                    .putNullable("session_group_id", sessionGroupId)
                    .putNullable("side", side)
                    .put("track_positions", trackPositions.toJSONArray())
                    .putNullable("rating", rating)
                    .putNullable("mood", mood)
                    .putNullable("notes", notes?.takeIf { it.isNotBlank() })
            postJson("sessions/", body).getString("session_id")
        }

    suspend fun startSessionGroup(
        title: String? = null,
        styleFocus: String = "mixed",
        moodDirection: String = "steady_mood",
        sessionType: String = "casual_listening",
        notes: String? = null,
    ): TimedSessionGroup =
        apiCall {
            val body =
                JSONObject()
                    .putNullable("title", title?.takeIf { it.isNotBlank() })
                    .put("style_focus", styleFocus)
                    .put("mood_direction", moodDirection)
                    .put("session_type", sessionType)
                    .putNullable("notes", notes?.takeIf { it.isNotBlank() })
            postJson("sessions/groups", body).toTimedSessionGroup()
        }

    suspend fun getActiveSessionGroup(): TimedSessionGroup? =
        apiCall {
            getJson("sessions/groups/active")
                .optJSONObject("session_group")
                ?.toTimedSessionGroup()
        }

    suspend fun finishSessionGroup(sessionGroupId: String): TimedSessionGroup =
        apiCall {
            patchJson("sessions/groups/${Uri.encode(sessionGroupId)}/finish", JSONObject()).toTimedSessionGroup()
        }

    suspend fun updateSessionGroup(
        sessionGroupId: String,
        styleFocus: String,
        moodDirection: String,
        sessionType: String,
        notes: String?,
    ): TimedSessionGroup =
        apiCall {
            val body =
                JSONObject()
                    .put("style_focus", styleFocus)
                    .put("mood_direction", moodDirection)
                    .put("session_type", sessionType)
                    .putNullable("notes", notes?.takeIf { it.isNotBlank() })
            patchJson("sessions/groups/${Uri.encode(sessionGroupId)}", body).toTimedSessionGroup()
        }

    suspend fun getSession(sessionId: String): ListeningSession =
        apiCall {
            getJson("sessions/${Uri.encode(sessionId)}").toListeningSession()
        }

    suspend fun updateSession(
        sessionId: String,
        side: String?,
        trackPositions: List<String> = emptyList(),
        rating: Int?,
        mood: String?,
        notes: String?,
    ): ListeningSession =
        apiCall {
            val body =
                JSONObject()
                    .putNullable("side", side)
                    .put("track_positions", trackPositions.toJSONArray())
                    .putNullable("rating", rating)
                    .putNullable("mood", mood)
                    .putNullable("notes", notes?.takeIf { it.isNotBlank() })
            patchJson("sessions/${Uri.encode(sessionId)}", body).toListeningSession()
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

    suspend fun getAiChatHistory(conversationId: String? = null): AiChatHistoryResponse =
        apiCall {
            val query = mutableListOf<String>()
            query.addQueryParam("conversation_id", conversationId)
            val response = getJson("ai/chat/history${query.toQueryString()}")
            AiChatHistoryResponse(
                conversationId = response.getString("conversation_id"),
                messages =
                    response.optJSONArray("messages").orEmpty().mapObjects { item ->
                        AiChatMessage(
                            role = item.optString("role", "assistant"),
                            content = item.getString("content"),
                            usedTools = item.optJSONArray("used_tools").orEmpty().mapStrings(),
                        )
                    },
            )
        }

    suspend fun clearAiChatHistory(conversationId: String? = null): AiChatClearResponse =
        apiCall {
            val query = mutableListOf<String>()
            query.addQueryParam("conversation_id", conversationId)
            val response = deleteJson("ai/chat/history${query.toQueryString()}")
            AiChatClearResponse(
                conversationId = response.getString("conversation_id"),
                deletedMessages = response.optInt("deleted_messages", 0),
            )
        }

    suspend fun exportAiChatHistory(conversationId: String? = null): AiChatExportResponse =
        apiCall {
            val query = mutableListOf<String>()
            query.addQueryParam("conversation_id", conversationId)
            val response = getJson("ai/chat/export${query.toQueryString()}")
            AiChatExportResponse(
                conversationId = response.getString("conversation_id"),
                exportedAt = response.getString("exported_at"),
                messages =
                    response.optJSONArray("messages").orEmpty().mapObjects { item ->
                        AiChatMessage(
                            role = item.optString("role", "assistant"),
                            content = item.getString("content"),
                            usedTools = item.optJSONArray("used_tools").orEmpty().mapStrings(),
                        )
                    },
            )
        }

    private suspend fun <T> apiCall(
        allowAuthRefresh: Boolean = true,
        block: suspend () -> T,
    ): T =
        withContext(Dispatchers.IO) {
            val requestAccessToken = accessToken
            try {
                block()
            } catch (error: ApiException) {
                if (allowAuthRefresh && error.shouldAttemptAccessRefresh()) {
                    val refreshResult =
                        if (accessToken != null && accessToken != requestAccessToken) {
                            AuthSessionRefreshResult.Ready
                        } else {
                            refreshAccessToken?.invoke()
                        }

                    when (refreshResult) {
                        AuthSessionRefreshResult.Ready -> return@withContext block()
                        AuthSessionRefreshResult.NeedsPasswordReentry ->
                            throw ApiException(
                                message = "Password re-entry is required.",
                                kind = ApiErrorKind.Unknown,
                                code = INACTIVITY_REAUTH_REQUIRED,
                                statusCode = 401,
                            )
                        AuthSessionRefreshResult.NeedsAuth ->
                            throw ApiException(
                                message = "Sign in again to continue.",
                                kind = ApiErrorKind.Unknown,
                                code = AUTH_REQUIRED,
                                statusCode = 401,
                            )
                        null -> throw error
                    }
                }
                throw error
            } catch (error: IOException) {
                throw ApiException(
                    message = "Service unavailable.",
                    kind = ApiErrorKind.Offline,
                    cause = error,
                )
            }
        }

    private fun ApiException.shouldAttemptAccessRefresh(): Boolean =
        statusCode == 401 &&
            code in
            setOf(
                AUTH_REQUIRED,
                EXPIRED_ACCESS_TOKEN,
                INVALID_ACCESS_TOKEN,
                null,
            )

    private suspend fun getJson(path: String): JSONObject =
        withRetry(ApiHttpMethod.Get) {
            val connection = openConnection(path)
            connection.requestMethod = "GET"
            readJsonResponse(connection)
        }

    private suspend fun getNullableJson(path: String): JSONObject? =
        withRetry(ApiHttpMethod.Get) {
            val connection = openConnection(path)
            connection.requestMethod = "GET"
            readNullableJsonResponse(connection)
        }

    private suspend fun fetchCollectionSyncJobStatus(jobId: String): CollectionSyncJobState =
        getJson("collection/sync/${Uri.encode(jobId)}").toCollectionSyncJobState()

    private suspend fun waitForCollectionSyncJob(
        initialJob: CollectionSyncJobState,
        onStatus: (CollectionSyncJobState) -> Unit,
    ): CollectionSyncJobState {
        var job = initialJob
        onStatus(job)
        while (!job.status.isTerminal) {
            delay(750)
            job = fetchCollectionSyncJobStatus(job.jobId)
            onStatus(job)
        }
        when (job.status) {
            CollectionSyncJobStatus.Succeeded -> return job
            CollectionSyncJobStatus.Failed ->
                throw ApiException(
                    message = job.error?.message ?: "Collection sync failed.",
                    failedStep = job.error?.failedStep,
                )
            CollectionSyncJobStatus.Expired ->
                throw ApiException(
                    message = job.error?.message ?: "Collection sync expired. Start a new sync.",
                    failedStep = job.error?.failedStep,
                )
            else ->
                throw ApiException(
                    message = "Collection sync ended unexpectedly.",
                    failedStep = job.step?.wireValue,
                )
        }
    }

    private fun postImageMultipart(
        context: Context,
        imageUri: Uri,
        path: String,
        fieldName: String = "image",
        contentType: String? = null,
    ): JSONObject {
        val resolver = context.contentResolver
        val mimeType = contentType ?: resolver.getType(imageUri) ?: "image/jpeg"
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
            output.writeUtf8("Content-Disposition: form-data; name=\"$fieldName\"; filename=\"$filename\"\r\n")
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

    private fun patchJson(
        path: String,
        body: JSONObject,
    ): JSONObject {
        val connection = openConnection(path)
        connection.requestMethod = "PATCH"
        connection.doOutput = true
        connection.setRequestProperty("Content-Type", "application/json")
        connection.outputStream.use { it.writeUtf8(body.toString()) }
        return readJsonResponse(connection)
    }

    private fun putJson(
        path: String,
        body: JSONObject,
    ): JSONObject {
        val connection = openConnection(path)
        connection.requestMethod = "PUT"
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

    private fun deleteJson(
        path: String,
        body: JSONObject,
    ): JSONObject {
        val connection = openConnection(path)
        connection.requestMethod = "DELETE"
        connection.doOutput = true
        connection.setRequestProperty("Content-Type", "application/json")
        connection.outputStream.use { it.writeUtf8(body.toString()) }
        return readJsonResponse(connection)
    }

    private fun openConnection(path: String): HttpURLConnection =
        URL("${baseUrl.trimEnd('/')}/${path.trimStart('/')}").openConnection().let { connection ->
            (connection as HttpURLConnection).apply {
                connectTimeout = 15_000
                readTimeout = 60_000
                setRequestProperty("Accept", "application/json")
                accessToken?.let { setRequestProperty("Authorization", "Bearer $it") }
            }
        }

    private fun readJsonResponse(connection: HttpURLConnection): JSONObject = readNullableJsonResponse(connection) ?: JSONObject()

    private fun readNullableJsonResponse(connection: HttpURLConnection): JSONObject? {
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
            val fieldErrors = errorObject?.optJSONObject("field_errors").toFieldErrors()
            val featureUsageLimit = errorObject?.toFeatureUsageLimit()
            val rawMessage =
                errorObject?.optNullableString("message")
                    ?: errorBody?.optNullableString("detail")
                    ?: body.takeIf { it.isNotBlank() }
            val kind = status.toApiErrorKind()
            throw ApiException(
                message =
                    featureUsageLimit?.toUserMessage()
                        ?: apiErrorMessage(status, code, rawMessage, retryAfterMillis),
                kind = if (featureUsageLimit != null) ApiErrorKind.FeatureGated else kind,
                code = code,
                statusCode = status,
                retryAfterMillis = retryAfterMillis,
                featureUsageLimit = featureUsageLimit,
                fieldErrors = fieldErrors,
            )
        }
        if (status == 204) {
            return null
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
    FeatureGated,
    Validation,
    NotFound,
    Server,
    Unknown,
}

class ApiException(
    message: String,
    val kind: ApiErrorKind = ApiErrorKind.Unknown,
    val code: String? = null,
    val failedStep: String? = null,
    val statusCode: Int? = null,
    val retryAfterMillis: Long? = null,
    val featureUsageLimit: FeatureUsageLimit? = null,
    val fieldErrors: Map<String, String> = emptyMap(),
    cause: Throwable? = null,
) : Exception(message, cause)

data class FeatureUsageLimit(
    val capability: String,
    val plan: String?,
    val limit: Int?,
    val used: Int?,
    val resetAt: String?,
)

data class AiChatResponse(
    val conversationId: String,
    val content: String,
    val usedTools: List<String>,
)

data class AiChatHistoryResponse(
    val conversationId: String,
    val messages: List<AiChatMessage>,
)

data class AiChatClearResponse(
    val conversationId: String,
    val deletedMessages: Int,
)

data class AiChatExportResponse(
    val conversationId: String,
    val exportedAt: String,
    val messages: List<AiChatMessage>,
)

data class AiChatMessage(
    val role: String,
    val content: String,
    val usedTools: List<String>,
)

data class ReleaseSearchResultsPage(
    val results: List<ReleaseSearchResult>,
    val hasMore: Boolean,
)

fun Throwable.toUserMessage(fallback: String): String = (this as? ApiException)?.message ?: fallback

internal fun validateManualReleaseCoverContentType(contentType: String?): String {
    val normalizedContentType =
        contentType
            ?.trim()
            ?.lowercase()
            ?.takeIf { it.isNotBlank() }
            ?: throw ApiException(
                message = "Cover image type could not be detected.",
                kind = ApiErrorKind.Validation,
                code = "manual_release_cover_invalid",
            )
    if (normalizedContentType !in ManualReleaseLimits.SUPPORTED_COVER_CONTENT_TYPES) {
        throw ApiException(
            message = "Cover image must be JPEG, PNG, or WebP.",
            kind = ApiErrorKind.Validation,
            code = "manual_release_cover_invalid",
        )
    }
    return normalizedContentType
}

private const val AUTH_REQUIRED = "auth_required"
private const val EXPIRED_ACCESS_TOKEN = "expired_access_token"
private const val INVALID_ACCESS_TOKEN = "invalid_access_token"
private const val INACTIVITY_REAUTH_REQUIRED = "inactivity_reauth_required"
private const val FEATURE_USAGE_LIMIT_EXCEEDED = "feature_usage_limit_exceeded"
private const val OCR_IDENTIFY_CAPABILITY = "ocr_identify"

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

private fun List<String>.toQueryString(): String = if (isEmpty()) "" else "?${joinToString("&")}"

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
        inCollection = optBoolean("in_collection", true),
        collectionAddedAt = optNullableString("collection_added_at"),
        collectionRemovedAt = optNullableString("collection_removed_at"),
        isFavorite = optBoolean("is_favorite", false),
        hasFullDiscogsInfo = optBoolean("has_full_discogs_info", false),
        tracklist = optJSONArray("tracklist").orEmpty().toReleaseTracks(),
        discogsArtists = optJSONArray("discogs_artists").orEmpty().toReleaseArtists(),
    )

private fun JSONObject.toRecordFlowInsights(): RecordFlowInsights =
    RecordFlowInsights(
        releaseId = optString("release_id"),
        before = optJSONArray("before").orEmpty().toRecordFlowReleaseSummaries(),
        after = optJSONArray("after").orEmpty().toRecordFlowReleaseSummaries(),
        moodTransitions = optJSONArray("mood_transitions").orEmpty().toRecordFlowMoodTransitions(),
        sampleSize = optInt("sample_size", 0),
        confidence = optString("confidence", "low"),
    )

internal fun JSONObject.toCollectionRecordsPage(): CollectionRecordsPage {
    val records =
        optJSONArray("items")
            .orEmpty()
            .mapObjects { item -> item.toCollectionRecord() }
    return CollectionRecordsPage(
        records = records,
        limit = optInt("limit", 25),
        offset = optInt("offset", 0),
        total = optInt("total", records.size),
        hasMore = optBoolean("has_more", false),
        hasFavorites = optBoolean("has_favorites", false),
    )
}

internal fun JSONObject.toCollectionFoldersPage(): CollectionFoldersPage {
    val folders =
        optJSONArray("folders")
            .orEmpty()
            .mapObjects { folder -> folder.toCollectionFolder() }
    return CollectionFoldersPage(
        discogsConfigured = optBoolean("discogs_configured", false),
        folders = folders,
        hasExtraFolders = optBoolean("has_extra_folders", folders.any { !it.isDefault }),
    )
}

internal fun JSONObject.toCollectionSourceOfTruth(): CollectionSourceOfTruth =
    CollectionSourceOfTruth.fromWireValue(optString("source_of_truth", "APP"))

internal fun JSONObject.toDiscogsIntegrationStatus(): DiscogsIntegrationStatus =
    DiscogsIntegrationStatus(
        accessTokenSaved = optBoolean("access_token_saved", false),
        externalUserId = optNullableString("external_user_id"),
        externalUsername = optNullableString("external_username"),
        sourceOfTruth = CollectionSourceOfTruth.fromWireValue(optString("source_of_truth", "APP")),
        backendIdentifyEnabled = optBoolean("backend_identify_enabled", false),
    )

internal fun JSONObject.toManualReleaseDraftList(): ManualReleaseDraftList {
    val items = optJSONArray("items").orEmpty().mapObjects { item -> item.toManualReleaseDraftSummary() }
    return ManualReleaseDraftList(
        items = items,
        limit = optInt("limit", ManualReleaseLimits.MAX_DRAFTS),
        remainingSlots = optInt("remaining_slots", 0),
    )
}

internal fun JSONObject.toManualReleaseDraft(): ManualReleaseDraft {
    val summary = toManualReleaseDraftSummary()
    return ManualReleaseDraft(
        id = summary.id,
        artist = summary.artist,
        title = summary.title,
        label = summary.label,
        catalogNumber = summary.catalogNumber,
        format = summary.format,
        coverThumbnailUrl = summary.coverThumbnailUrl,
        completionState = summary.completionState,
        updatedAt = summary.updatedAt,
        formData = optJSONObject("form_data").orEmpty().toManualReleaseFormData(),
        coverImageUrl = optNullableString("cover_image_url"),
        coverContentType = optNullableString("cover_content_type"),
        coverSizeBytes = optNullableInt("cover_size_bytes"),
        createdAt = optString("created_at", summary.updatedAt),
    )
}

internal fun JSONObject.toManualReleaseSaveResult(): ManualReleaseSaveResult =
    ManualReleaseSaveResult(
        id = getString("id"),
        title = optString("title", ""),
        artist = optString("artist", ""),
        inCollection = optBoolean("in_collection", true),
    )

internal fun JSONObject.toManualReleaseCoverUploadResult(): ManualReleaseCoverUploadResult =
    ManualReleaseCoverUploadResult(
        contentType = getString("content_type"),
        sizeBytes = optInt("size_bytes", 0),
    )

private fun JSONObject.toManualReleaseDraftSummary(): ManualReleaseDraftSummary =
    ManualReleaseDraftSummary(
        id = getString("id"),
        artist = optNullableString("artist"),
        title = optNullableString("title"),
        label = optNullableString("label"),
        catalogNumber = optNullableString("catalog_number"),
        format = optNullableString("format"),
        coverThumbnailUrl = optNullableString("cover_thumbnail_url"),
        completionState = optJSONObject("completion_state")?.toManualReleaseCompletionState(),
        updatedAt = optString("updated_at", ""),
    )

private fun JSONObject.toManualReleaseCompletionState(): ManualReleaseCompletionState =
    ManualReleaseCompletionState(
        requiredComplete = optBoolean("required_complete", false),
    )

private fun JSONObject.toManualReleaseFormData(): ManualReleaseFormData =
    ManualReleaseFormData(
        artists = optJSONArray("artists").orEmpty().mapStrings(),
        title = optNullableString("title"),
        label = optNullableString("label"),
        catalogNumber = optNullableString("catalog_number"),
        barcode = optNullableString("barcode"),
        format = ManualReleaseFormat.fromWireValue(optNullableString("format")),
        vinylSize = ManualReleaseVinylSize.fromWireValue(optNullableString("vinyl_size")),
        vinylSpeed = ManualReleaseVinylSpeed.fromWireValue(optNullableString("vinyl_speed")),
        vinylDiscCount = optNullableInt("vinyl_disc_count"),
        genres = optJSONArray("genres").orEmpty().mapStrings(),
        styles = optJSONArray("styles").orEmpty().mapStrings(),
        tracklist = optJSONArray("tracklist").orEmpty().mapObjects { track -> track.toManualReleaseTrackInput() },
    )

private fun JSONObject.toManualReleaseTrackInput(): ManualReleaseTrackInput =
    ManualReleaseTrackInput(
        title = optNullableString("title"),
        position = optNullableString("position"),
        duration = optNullableString("duration"),
        credits = optJSONArray("credits").orEmpty().mapObjects { credit -> credit.toManualReleaseTrackCreditInput() },
    )

private fun JSONObject.toManualReleaseTrackCreditInput(): ManualReleaseTrackCreditInput =
    ManualReleaseTrackCreditInput(
        role = ManualReleaseTrackCreditRole.fromWireValue(optNullableString("role")) ?: ManualReleaseTrackCreditRole.Other,
        name = optNullableString("name"),
    )

private fun JSONObject.toReleaseSearchResult(): ReleaseSearchResult =
    ReleaseSearchResult(
        releaseId = optNullableString("release_id"),
        discogsReleaseId = optLong("discogs_release_id"),
        artist = optString("artist", "Unknown artist"),
        title = optString("title", "Unknown title"),
        year = optNullableInt("year"),
        label = optNullableString("label"),
        catalogNumber = optNullableString("catalog_number"),
        thumbnailUrl = optNullableString("thumbnail_url"),
        format = optNullableString("format"),
    )

private fun JSONObject.toReleaseSearchResultsPage(limit: Int): ReleaseSearchResultsPage {
    val results = releaseSearchResults()
    val defaultHasMore = results.size == limit
    val hasMore =
        if (has("has_more") && !isNull("has_more")) {
            optBoolean("has_more", defaultHasMore)
        } else {
            defaultHasMore
        }
    return ReleaseSearchResultsPage(results = results, hasMore = hasMore)
}

private fun JSONObject.releaseSearchResults(): List<ReleaseSearchResult> =
    optJSONArray("results").orEmpty().mapObjects { item ->
        item.toReleaseSearchResult()
    }

private fun JSONObject.toCollectionRecord(): CollectionRecord =
    CollectionRecord(
        releaseId = getString("id"),
        discogsReleaseId = optLong("discogs_release_id"),
        artist = optString("artist", "Unknown artist"),
        title = optString("title", "Unknown title"),
        year = optNullableInt("year"),
        format = optNullableString("format") ?: "Vinyl",
        label = optNullableString("label"),
        catalogNumber = optNullableString("catalog_number"),
        styles = optJSONArray("styles").orEmpty().mapStrings(),
        thumbnailUrl = optNullableString("thumb_url"),
        collectionAddedAt = optNullableString("collection_added_at"),
        inCollection = optBoolean("in_collection", false),
        isFavorite = optBoolean("is_favorite", false),
    )

private fun JSONObject.toCollectionFolder(): CollectionFolder =
    CollectionFolder(
        id = optLong("id"),
        name = optString("name", "Folder ${optLong("id")}"),
        count = optNullableInt("count"),
        isDefault = optBoolean("is_default", false),
    )

private fun CollectionSourceOfTruth.toWireValue(): String =
    when (this) {
        CollectionSourceOfTruth.App -> "APP"
        CollectionSourceOfTruth.Discogs -> "DISCOGS"
    }

internal fun JSONObject.toAnalyticsSessionsPage(): AnalyticsSessionsPage =
    AnalyticsSessionsPage(
        sessions =
            optJSONArray("sessions")
                .orEmpty()
                .mapObjects { item ->
                    item.toListeningSession()
                },
        pagination = optJSONObject("pagination").toAnalyticsPagination(),
    )

internal fun JSONObject.toListeningSession(
    fallbackReleaseId: String = "",
    fallbackArtist: String = "Unknown artist",
    fallbackTitle: String = "Unknown title",
): ListeningSession {
    val notes = optNullableString("notes")
    return ListeningSession(
        releaseId = optNullableString("release_id") ?: fallbackReleaseId,
        artist = optNullableString("artist") ?: fallbackArtist,
        title = optNullableString("title") ?: fallbackTitle,
        year = optNullableInt("year"),
        label = optNullableString("label"),
        catalogNumber = optNullableString("catalog_number"),
        playedAt = optNullableString("played_at") ?: optNullableString("date") ?: "Unknown date",
        mood = optNullableString("mood") ?: "Unspecified",
        rating = optNullableInt("rating") ?: 0,
        thumbnailUrl = optNullableString("thumbnail_url"),
        side = optNullableString("side") ?: optNullableString("vinyl_side"),
        hasNotes = optBoolean("has_notes", false) || !notes.isNullOrBlank(),
        notes = notes,
        sessionId = optNullableString("session_id") ?: optNullableString("id"),
        sessionGroupId = optNullableString("session_group_id"),
        sessionGroup = optJSONObject("session_group")?.toTimedSessionGroup(),
        createdAt = optNullableString("created_at"),
        canEdit = optBoolean("can_edit", false),
        editableUntil = optNullableString("editable_until"),
        tracks = optJSONArray("tracks").orEmpty().toSessionTracks(),
    )
}

private fun JSONObject.toTimedSessionGroup(): TimedSessionGroup {
    val startedAt = optNullableString("started_at") ?: optNullableString("created_at") ?: ""
    val endedAt = optNullableString("ended_at")
    return TimedSessionGroup(
        id = getString("id"),
        title = optNullableString("title"),
        status = optString("status", "active"),
        styleFocus = optString("style_focus", "mixed"),
        moodDirection = optString("mood_direction", "steady_mood"),
        sessionType = optString("session_type", "casual_listening"),
        notes = optNullableString("notes"),
        startedAt = startedAt,
        endedAt = endedAt,
        createdAt = optNullableString("created_at") ?: startedAt,
        updatedAt = optNullableString("updated_at") ?: endedAt ?: startedAt,
        canEdit = optBoolean("can_edit", false),
        editableUntil = optNullableString("editable_until"),
    )
}

internal fun JSONObject.toAnalyticsRecordCountsPage(): AnalyticsRecordCountsPage =
    AnalyticsRecordCountsPage(
        records =
            optJSONArray("records")
                .orEmpty()
                .mapObjects { item ->
                    AnalyticsRecordCountItem(
                        record = item.toAnalyticsRecordSummary(),
                        count = item.optInt("count", 0),
                    )
                },
        pagination = optJSONObject("pagination").toAnalyticsPagination(),
    )

private fun JSONObject?.toAnalyticsPagination(): AnalyticsPagination {
    val pagination = orEmpty()
    return AnalyticsPagination(
        limit = pagination.optInt("limit", 10),
        offset = pagination.optInt("offset", 0),
        total = pagination.optInt("total", 0),
        hasMore = pagination.optBoolean("has_more", false),
    )
}

private fun JSONObject.toAnalyticsRecordSummary(): RecordSummary =
    RecordSummary(
        releaseId = getString("release_id"),
        discogsReleaseId = optLong("discogs_release_id"),
        artist = optString("artist", "Unknown artist"),
        title = optString("title", "Unknown title"),
        label = "",
        year = null,
        format = "Vinyl",
        rating = 0,
        lastPlayed = "",
        coverImageUrl = optNullableString("thumbnail_url"),
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

private fun manualReleaseDraftBody(
    formData: ManualReleaseFormData,
    completionState: ManualReleaseCompletionState?,
): JSONObject =
    JSONObject()
        .put("form_data", formData.toJson())
        .putNullable("completion_state", completionState?.toJson())

private fun ManualReleaseCompletionState.toJson(): JSONObject =
    JSONObject()
        .put("required_complete", requiredComplete)

private fun ManualReleaseFormData.toJson(): JSONObject =
    JSONObject()
        .put("artists", artists.toJsonArray())
        .putNullable("title", title)
        .putNullable("label", label)
        .putNullable("catalog_number", catalogNumber)
        .putNullable("barcode", barcode)
        .putNullable("format", format?.wireValue)
        .putNullable("vinyl_size", vinylSize?.wireValue)
        .putNullable("vinyl_speed", vinylSpeed?.wireValue)
        .putNullable("vinyl_disc_count", vinylDiscCount)
        .put("genres", genres.toJsonArray())
        .put("styles", styles.toJsonArray())
        .put("tracklist", JSONArray().also { items -> tracklist.forEach { items.put(it.toJson()) } })

private fun ManualReleaseTrackInput.toJson(): JSONObject =
    JSONObject()
        .putNullable("title", title)
        .putNullable("position", position)
        .putNullable("duration", duration)
        .put("credits", JSONArray().also { items -> credits.forEach { items.put(it.toJson()) } })

private fun ManualReleaseTrackCreditInput.toJson(): JSONObject =
    JSONObject()
        .put("role", role.wireValue)
        .putNullable("name", name)

private fun List<String>.toJsonArray(): JSONArray = JSONArray().also { items -> forEach { items.put(it) } }

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

data class CollectionSyncJobState(
    val jobId: String,
    val status: CollectionSyncJobStatus,
    val step: CollectionSyncJobStep?,
    val message: String,
    val totalItems: Int = 0,
    val processedItems: Int = 0,
    val addedCount: Int = 0,
    val updatedCount: Int = 0,
    val removedCount: Int = 0,
    val error: CollectionSyncJobError? = null,
)

enum class CollectionSyncJobStatus(
    val wireValue: String,
) {
    Queued("queued"),
    Running("running"),
    Succeeded("succeeded"),
    Failed("failed"),
    Expired("expired"),
    Unknown("unknown"),
    ;

    val isTerminal: Boolean
        get() = this == Succeeded || this == Failed || this == Expired

    companion object {
        fun fromWireValue(value: String): CollectionSyncJobStatus = entries.firstOrNull { it.wireValue == value } ?: Unknown
    }
}

enum class CollectionSyncJobStep(
    val wireValue: String,
) {
    Fetching("fetching"),
    Importing("importing"),
    Loading("loading"),
    Finalizing("finalizing"),
    Unknown("unknown"),
    ;

    companion object {
        fun fromWireValue(value: String?): CollectionSyncJobStep? =
            value?.takeIf { it.isNotBlank() }?.let { wireValue ->
                entries.firstOrNull { it.wireValue == wireValue } ?: Unknown
            }
    }
}

data class CollectionSyncJobError(
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

internal fun JSONObject.toCollectionSyncJobState(): CollectionSyncJobState {
    val error = optJSONObject("error")
    return CollectionSyncJobState(
        jobId = getString("job_id"),
        status = CollectionSyncJobStatus.fromWireValue(optString("status", "unknown")),
        step = CollectionSyncJobStep.fromWireValue(optNullableString("step")),
        message = optString("message", ""),
        totalItems = optInt("total_items", 0),
        processedItems = optInt("processed_items", 0),
        addedCount = optInt("added_count", 0),
        updatedCount = optInt("updated_count", 0),
        removedCount = optInt("removed_count", 0),
        error =
            error?.let {
                CollectionSyncJobError(
                    code = it.optString("code", "collection_sync_failed"),
                    message = it.optString("message", "Collection sync failed."),
                    failedStep = it.optString("failed_step", "unknown"),
                )
            },
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

private fun JSONObject.optNullableLong(name: String): Long? = if (isNull(name)) null else optLong(name).takeIf { it > 0 }

private fun JSONObject.optNullableDouble(name: String): Double? = if (isNull(name)) null else optDouble(name)

private fun JSONObject?.toFieldErrors(): Map<String, String> {
    if (this == null) return emptyMap()
    val keys = keys()
    val fieldErrors = linkedMapOf<String, String>()
    while (keys.hasNext()) {
        val key = keys.next()
        val message = optNullableString(key) ?: continue
        fieldErrors[key] = message
    }
    return fieldErrors
}

private fun JSONObject.toAuthTokenPair(): AuthTokenPair =
    AuthTokenPair(
        accessToken = getString("access_token"),
        accessExpiresAt = getString("access_expires_at"),
        refreshToken = getString("refresh_token"),
        refreshExpiresAt = getString("refresh_expires_at"),
        tokenType = optString("token_type", "Bearer"),
        sessionId = getString("session_id"),
    )

private fun JSONObject.toAuthRegistrationResult(): AuthRegistrationResult =
    AuthRegistrationResult(
        userId = getString("user_id"),
        email = getString("email"),
        verificationExpiresAt = getString("verification_expires_at"),
    )

private fun JSONObject.toAuthAccountSummary(): AuthAccountSummary =
    AuthAccountSummary(
        userId = getString("user_id"),
        email = getString("email"),
        emailVerifiedAt = optNullableString("email_verified_at"),
    )

private fun JSONObject.toAuthVerificationResendResult(): AuthVerificationResendResult =
    AuthVerificationResendResult(
        userId = getString("user_id"),
        email = getString("email"),
        verificationExpiresAt = getString("verification_expires_at"),
        resendCount = getInt("resend_count"),
    )

private fun JSONObject.toAuthPasswordResetRequestResult(): AuthPasswordResetRequestResult =
    AuthPasswordResetRequestResult(
        accepted = optBoolean("accepted", false),
        email = getString("email"),
    )

private fun JSONObject.toAuthPasswordChangeResult(): AuthPasswordChangeResult =
    AuthPasswordChangeResult(
        changed = optBoolean("changed", false),
        revokedSessions = optInt("revoked_sessions", 0),
    )

private fun JSONObject.toAuthLogoutAllResult(): AuthLogoutAllResult =
    AuthLogoutAllResult(
        revokedSessions = optInt("revoked_sessions", 0),
    )

private fun JSONObject.toAuthDeleteAccountResult(): AuthDeleteAccountResult =
    AuthDeleteAccountResult(
        deleted = optBoolean("deleted", false),
        deletionReceiptId = getString("deletion_receipt_id"),
        deletedAt = getString("deleted_at"),
    )

private fun Int.toApiErrorKind(): ApiErrorKind =
    when (this) {
        402 -> ApiErrorKind.FeatureGated
        429 -> ApiErrorKind.RateLimited
        404 -> ApiErrorKind.NotFound
        422 -> ApiErrorKind.Validation
        in 500..599 -> ApiErrorKind.Server
        else -> ApiErrorKind.Unknown
    }

private fun JSONObject.toFeatureUsageLimit(): FeatureUsageLimit? {
    val code = optNullableString("code")
    if (code != FEATURE_USAGE_LIMIT_EXCEEDED) return null
    return FeatureUsageLimit(
        capability = optString("capability", ""),
        plan = optNullableString("plan"),
        limit = optNullableInt("limit"),
        used = optNullableInt("used"),
        resetAt = optNullableString("reset_at"),
    )
}

private fun FeatureUsageLimit.toUserMessage(): String {
    val base =
        when (capability) {
            OCR_IDENTIFY_CAPABILITY -> "Identify allowance reached. Manual Search is still available."
            else -> "This feature's current allowance has been reached."
        }
    return resetAt?.let { "$base Try again after $it." } ?: base
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
        code == "session_edit_window_expired" -> "This session can only be edited for 15 minutes after logging."
        code == "release_not_found" -> "This release is not available locally yet."
        code == "release_not_in_collection" -> "Add this record back to collection before logging a new session."
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

private fun JSONArray.toReleaseTracks(): List<ReleaseTrack> =
    mapObjects { item ->
        ReleaseTrack(
            position = item.optString("position"),
            title = item.optString("title"),
            duration = item.optNullableString("duration"),
            artists = item.optJSONArray("artists").orEmpty().toReleaseTrackArtists(),
            extraArtists =
                (
                    item.optJSONArray("extra_artists")
                        ?: item.optJSONArray("extraartists")
                ).orEmpty().toReleaseTrackCredits(),
        )
    }.filter { it.position.isNotBlank() && it.title.isNotBlank() }

private fun JSONArray.toReleaseTrackArtists(): List<ReleaseTrackArtist> =
    mapObjects { item ->
        ReleaseTrackArtist(
            name = item.optString("name"),
            join = item.optNullableString("join"),
            discogsArtistId = item.optNullableLong("discogs_artist_id") ?: item.optNullableLong("id"),
        )
    }.filter { it.name.isNotBlank() }

private fun JSONArray.toReleaseTrackCredits(): List<ReleaseTrackCredit> =
    mapObjects { item ->
        ReleaseTrackCredit(
            name = item.optString("name"),
            role = item.optNullableString("role"),
        )
    }.filter { it.name.isNotBlank() }

private fun JSONArray.toReleaseArtists(): List<ReleaseArtist> =
    mapObjects { item ->
        ReleaseArtist(
            name = item.optString("name"),
            discogsArtistId = item.optLong("discogs_artist_id"),
        )
    }.filter { it.name.isNotBlank() && it.discogsArtistId > 0 }

private fun JSONArray.toRecordFlowReleaseSummaries(): List<RecordFlowReleaseSummary> =
    mapObjects { item ->
        RecordFlowReleaseSummary(
            releaseId = item.optString("release_id"),
            artist = item.optString("artist", "Unknown artist"),
            title = item.optString("title", "Unknown title"),
            year = item.optNullableInt("year"),
            thumbnailUrl = item.optNullableString("thumbnail_url"),
            coverImageUrl = item.optNullableString("cover_image_url"),
            styles = item.optJSONArray("styles").orEmpty().mapStrings(),
            count = item.optInt("count", 0),
        )
    }.filter { it.releaseId.isNotBlank() && it.count > 0 }

private fun JSONArray.toRecordFlowMoodTransitions(): List<RecordFlowMoodTransition> =
    mapObjects { item ->
        RecordFlowMoodTransition(
            previousMood = item.optNullableString("previous_mood"),
            currentMood = item.optNullableString("current_mood"),
            nextMood = item.optNullableString("next_mood"),
            count = item.optInt("count", 0),
        )
    }.filter { it.count > 0 }

private fun JSONArray.toSessionTracks(): List<SessionTrack> =
    mapObjects { item ->
        SessionTrack(
            position = item.optString("position"),
            artist = item.optNullableString("artist") ?: item.optNullableString("track_artist"),
            title = item.optString("title"),
            duration = item.optNullableString("duration"),
            sequence = item.optNullableInt("sequence"),
        )
    }.filter { it.position.isNotBlank() && it.title.isNotBlank() }

private fun List<String>.toJSONArray(): JSONArray =
    JSONArray().also { array ->
        forEach { item -> array.put(item) }
    }

private fun <T> JSONArray.mapObjects(transform: (JSONObject) -> T): List<T> = List(length()) { index -> transform(getJSONObject(index)) }

private fun JSONObject.intEntries(): List<Pair<String, Int>> =
    buildList {
        val keys = keys()
        while (keys.hasNext()) {
            val key = keys.next()
            add(key to optInt(key, 0))
        }
    }
