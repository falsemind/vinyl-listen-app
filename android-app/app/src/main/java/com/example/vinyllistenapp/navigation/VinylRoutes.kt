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
    const val RELEASE_ID = "releaseId"
    const val SESSION_LOGGING_PATTERN = "session_logging/{$RELEASE_ID}"
    const val RECORD_DETAIL_PATTERN = "record_detail/{$RELEASE_ID}"
    const val ANALYTICS = "analytics"
    const val SETTINGS = "settings"

    fun sessionLogging(releaseId: String): String = "session_logging/${Uri.encode(releaseId)}"

    fun recordDetail(releaseId: String): String = "record_detail/${Uri.encode(releaseId)}"

    fun processing(imageUri: Uri): String = "processing?imageUri=${Uri.encode(imageUri.toString())}"
}
