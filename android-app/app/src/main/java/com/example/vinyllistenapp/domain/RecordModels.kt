package com.example.vinyllistenapp.domain

data class RecordSummary(
    val releaseId: String,
    val discogsReleaseId: Long,
    val artist: String,
    val title: String,
    val label: String,
    val year: Int,
    val format: String,
    val rating: Int,
    val lastPlayed: String,
)

data class ListeningSession(
    val releaseId: String,
    val artist: String,
    val title: String,
    val playedAt: String,
    val mood: String,
    val rating: Int,
)

data class MatchCandidate(
    val releaseId: String,
    val artist: String,
    val title: String,
    val label: String,
    val confidence: Int,
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
