package com.example.vinyllistenapp.domain

data class RecordSummary(
    val releaseId: String,
    val discogsReleaseId: Long,
    val artist: String,
    val title: String,
    val label: String,
    val year: Int?,
    val format: String,
    val rating: Int,
    val lastPlayed: String,
    val catalogNumber: String? = null,
    val barcode: String? = null,
    val genres: List<String> = emptyList(),
    val styles: List<String> = emptyList(),
    val coverImageUrl: String? = null,
)

data class ListeningSession(
    val releaseId: String,
    val artist: String,
    val title: String,
    val playedAt: String,
    val mood: String,
    val rating: Int,
    val side: String? = null,
    val hasNotes: Boolean = false,
)

data class TopRecordSummary(
    val record: RecordSummary,
    val plays: Int,
    val averageRating: String,
)

data class HomeSummary(
    val recentSessions: List<ListeningSession>,
    val totalSessions: Int,
    val recordsThisMonth: Int,
    val topRecords: List<TopRecordSummary>,
)

data class MatchCandidate(
    val releaseId: String?,
    val discogsReleaseId: Long,
    val artist: String,
    val title: String,
    val label: String,
    val confidence: Int,
    val year: Int? = null,
    val catalogNumber: String? = null,
    val barcode: String? = null,
    val coverImageUrl: String? = null,
    val matchSource: String? = null,
    val matchedOn: List<String> = emptyList(),
)

enum class ConfidenceLevel {
    High,
    Medium,
    Low,
}

fun confidenceLevel(confidence: Int): ConfidenceLevel =
    when {
        confidence >= 85 -> ConfidenceLevel.High
        confidence >= 60 -> ConfidenceLevel.Medium
        else -> ConfidenceLevel.Low
    }
