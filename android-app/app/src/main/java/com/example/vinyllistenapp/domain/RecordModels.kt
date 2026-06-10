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
    val availableSides: List<String> = emptyList(),
    val availableSideOptions: List<ReleaseSideOption> = emptyList(),
    val inCollection: Boolean = true,
    val collectionAddedAt: String? = null,
    val collectionRemovedAt: String? = null,
    val hasFullDiscogsInfo: Boolean = false,
    val tracklist: List<ReleaseTrack> = emptyList(),
    val discogsArtists: List<ReleaseArtist> = emptyList(),
)

data class ReleaseSideOption(
    val value: String,
    val label: String,
)

data class ReleaseTrack(
    val position: String,
    val title: String,
    val duration: String? = null,
)

data class ReleaseArtist(
    val name: String,
    val discogsArtistId: Long,
)

data class SessionTrack(
    val position: String,
    val title: String,
    val duration: String? = null,
    val sequence: Int? = null,
)

data class ReleaseSearchResult(
    val releaseId: String? = null,
    val discogsReleaseId: Long,
    val artist: String,
    val title: String,
    val year: Int?,
    val label: String?,
    val catalogNumber: String?,
    val thumbnailUrl: String?,
    val format: String?,
)

data class ListeningSession(
    val releaseId: String,
    val artist: String,
    val title: String,
    val playedAt: String,
    val mood: String,
    val rating: Int,
    val thumbnailUrl: String? = null,
    val side: String? = null,
    val hasNotes: Boolean = false,
    val notes: String? = null,
    val sessionId: String? = null,
    val createdAt: String? = null,
    val canEdit: Boolean = false,
    val editableUntil: String? = null,
    val tracks: List<SessionTrack> = emptyList(),
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

data class MonthlyPlayCount(
    val month: String,
    val plays: Int,
)

data class AnalyticsTopRecordSummary(
    val record: RecordSummary,
    val plays: Int,
    val averageRating: String,
    val topTrack: String? = null,
    val topMood: String? = null,
)

data class RatingDistributionItem(
    val rating: Int,
    val count: Int,
)

data class MoodDistributionItem(
    val mood: String,
    val count: Int,
)

data class StyleDistributionItem(
    val style: String,
    val count: Int,
)

data class AnalyticsDashboard(
    val monthlyPlays: List<MonthlyPlayCount>,
    val topRecords: List<AnalyticsTopRecordSummary>,
    val ratingDistribution: List<RatingDistributionItem>,
    val moodDistribution: List<MoodDistributionItem>,
    val styleDistribution: List<StyleDistributionItem>,
)

data class AnalyticsPagination(
    val limit: Int,
    val offset: Int,
    val total: Int,
    val hasMore: Boolean,
)

data class AnalyticsSessionsPage(
    val sessions: List<ListeningSession>,
    val pagination: AnalyticsPagination,
)

data class AnalyticsRecordCountItem(
    val record: RecordSummary,
    val count: Int,
)

data class AnalyticsRecordCountsPage(
    val records: List<AnalyticsRecordCountItem>,
    val pagination: AnalyticsPagination,
)

data class CollectionRecord(
    val releaseId: String,
    val discogsReleaseId: Long,
    val artist: String,
    val title: String,
    val year: Int?,
    val format: String,
    val label: String?,
    val catalogNumber: String?,
    val styles: List<String>,
    val thumbnailUrl: String?,
    val collectionAddedAt: String?,
    val inCollection: Boolean,
)

data class CollectionRecordsPage(
    val records: List<CollectionRecord>,
    val limit: Int,
    val offset: Int,
    val hasMore: Boolean,
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
    val format: String? = null,
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
