package com.example.vinyllistenapp.navigation

import android.net.Uri

object VinylRoutes {
    const val HOME = "home"
    const val CAPTURE_RECORD = "capture_record"
    const val PROCESSING = "processing"
    const val PROCESSING_PATTERN = "processing?imageUri={imageUri}"
    const val IMAGE_URI = "imageUri"
    const val MATCH_CONFIRMATION = "match_confirmation"
    const val MANUAL_SEARCH = "manual_search"
    const val COLLECTION_MANUAL_SEARCH = "collection_manual_search"
    const val RECENT_SESSIONS = "recent_sessions"
    const val TOP_RECORDS = "top_records"
    const val MOOD_DISTRIBUTION = "mood_distribution"
    const val STYLE_DISTRIBUTION = "style_distribution"
    const val ANALYTICS_MONTH_SESSIONS = "analytics_month_sessions"
    const val ANALYTICS_RATING_RECORDS = "analytics_rating_records"
    const val ANALYTICS_MOOD_RECORDS = "analytics_mood_records"
    const val ANALYTICS_STYLE_RECORDS = "analytics_style_records"
    const val RELEASE_ID = "releaseId"
    const val SESSION_ID = "sessionId"
    const val MONTH = "month"
    const val RATING = "rating"
    const val MOOD = "mood"
    const val STYLE = "style"
    const val SESSION_LOGGING_PATTERN = "session_logging/{$RELEASE_ID}"
    const val SESSION_EDIT = "session_edit"
    const val SESSION_EDIT_PATTERN = "$SESSION_EDIT/{$SESSION_ID}"
    const val RECORD_DETAIL_PATTERN = "record_detail/{$RELEASE_ID}"
    const val ANALYTICS_MONTH_SESSIONS_PATTERN = "$ANALYTICS_MONTH_SESSIONS/{$MONTH}"
    const val ANALYTICS_RATING_RECORDS_PATTERN = "$ANALYTICS_RATING_RECORDS/{$RATING}"
    const val ANALYTICS_MOOD_RECORDS_PATTERN = "$ANALYTICS_MOOD_RECORDS/{$MOOD}"
    const val ANALYTICS_STYLE_RECORDS_PATTERN = "$ANALYTICS_STYLE_RECORDS/{$STYLE}"
    const val ANALYTICS = "analytics"
    const val AI_INSIGHTS = "ai_insights"
    const val COLLECTION = "collection"
    const val SETTINGS = "settings"

    fun sessionLogging(releaseId: String): String = "session_logging/${Uri.encode(releaseId)}"

    fun sessionEdit(sessionId: String): String = "$SESSION_EDIT/${Uri.encode(sessionId)}"

    fun recordDetail(releaseId: String): String = "record_detail/${Uri.encode(releaseId)}"

    fun analyticsMonthSessions(month: String): String = "$ANALYTICS_MONTH_SESSIONS/${Uri.encode(month)}"

    fun analyticsRatingRecords(rating: Int): String = "$ANALYTICS_RATING_RECORDS/$rating"

    fun analyticsMoodRecords(mood: String): String = "$ANALYTICS_MOOD_RECORDS/${Uri.encode(mood)}"

    fun analyticsStyleRecords(style: String): String = "$ANALYTICS_STYLE_RECORDS/${Uri.encode(style)}"

    fun processing(imageUri: Uri): String = "processing?imageUri=${Uri.encode(imageUri.toString())}"
}
