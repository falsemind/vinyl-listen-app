package com.example.vinyllistenapp.data

import com.example.vinyllistenapp.domain.ListeningSession
import com.example.vinyllistenapp.domain.MatchCandidate
import com.example.vinyllistenapp.domain.RecordSummary
import com.example.vinyllistenapp.domain.TopRecordSummary

object MockVinylData {
    val records =
        listOf(
            RecordSummary(
                releaseId = "release-001",
                discogsReleaseId = 249504,
                artist = "Alice Coltrane",
                title = "Journey in Satchidananda",
                label = "Impulse!",
                year = 1971,
                format = "LP",
                rating = 5,
                lastPlayed = "Yesterday",
                catalogNumber = "AS-9203",
                coverImageUrl = "https://img.discogs.com/alice-coltrane-thumb.jpg",
            ),
            RecordSummary(
                releaseId = "release-002",
                discogsReleaseId = 1191434,
                artist = "Floating Points",
                title = "Elaenia",
                label = "Pluto",
                year = 2015,
                format = "2xLP",
                rating = 4,
                lastPlayed = "Last week",
                catalogNumber = "FPLP01",
                coverImageUrl = "https://img.discogs.com/floating-points-thumb.jpg",
            ),
            RecordSummary(
                releaseId = "release-003",
                discogsReleaseId = 527549,
                artist = "Sade",
                title = "Diamond Life",
                label = "Epic",
                year = 1984,
                format = "LP",
                rating = 5,
                lastPlayed = "2 weeks ago",
                catalogNumber = "FE 39581",
                coverImageUrl = "https://img.discogs.com/sade-thumb.jpg",
            ),
        )

    val recentSessions =
        listOf(
            ListeningSession(
                releaseId = "release-001",
                artist = "Alice Coltrane",
                title = "Journey in Satchidananda",
                playedAt = "Yesterday",
                mood = "Focused",
                rating = 5,
                thumbnailUrl = records[0].coverImageUrl,
            ),
            ListeningSession(
                releaseId = "release-002",
                artist = "Floating Points",
                title = "Elaenia",
                playedAt = "Last week",
                mood = "Late night",
                rating = 4,
                thumbnailUrl = records[1].coverImageUrl,
            ),
            ListeningSession(
                releaseId = "release-003",
                artist = "Sade",
                title = "Diamond Life",
                playedAt = "2 weeks ago",
                mood = "Relaxed",
                rating = 5,
                thumbnailUrl = records[2].coverImageUrl,
            ),
        )

    val matchCandidates =
        listOf(
            MatchCandidate(
                releaseId = "release-001",
                discogsReleaseId = 249504,
                artist = "Alice Coltrane",
                title = "Journey in Satchidananda",
                label = "Impulse!",
                confidence = 92,
                year = 1971,
                catalogNumber = "AS-9203",
                coverImageUrl = records[0].coverImageUrl,
            ),
            MatchCandidate(
                releaseId = "release-003",
                discogsReleaseId = 527549,
                artist = "Sade",
                title = "Diamond Life",
                label = "Epic",
                confidence = 71,
                year = 1984,
                catalogNumber = "FE 39581",
                coverImageUrl = records[2].coverImageUrl,
            ),
            MatchCandidate(
                releaseId = "release-002",
                discogsReleaseId = 1191434,
                artist = "Floating Points",
                title = "Elaenia",
                label = "Pluto",
                confidence = 58,
                year = 2015,
                catalogNumber = "FPLP01",
                coverImageUrl = records[1].coverImageUrl,
            ),
        )

    val moods = listOf("Focused", "Relaxed", "Late night", "Social", "Deep listen")

    val topRecords =
        listOf(
            TopRecordSummary(records[0], 12, "4.8"),
            TopRecordSummary(records[1], 2, "4.0"),
        )

    fun record(releaseId: String?): RecordSummary = records.firstOrNull { it.releaseId == releaseId } ?: records.first()

    fun recordByDiscogsId(discogsReleaseId: Long): RecordSummary? = records.firstOrNull { it.discogsReleaseId == discogsReleaseId }
}
