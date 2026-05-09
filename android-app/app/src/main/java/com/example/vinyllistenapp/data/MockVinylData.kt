package com.example.vinyllistenapp.data

import com.example.vinyllistenapp.domain.ListeningSession
import com.example.vinyllistenapp.domain.MatchCandidate
import com.example.vinyllistenapp.domain.RecordSummary

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
            ),
        )

    val recentSessions =
        listOf(
            ListeningSession("release-001", "Alice Coltrane", "Journey in Satchidananda", "Yesterday", "Focused", 5),
            ListeningSession("release-002", "Floating Points", "Elaenia", "Last week", "Late night", 4),
            ListeningSession("release-003", "Sade", "Diamond Life", "2 weeks ago", "Relaxed", 5),
        )

    val matchCandidates =
        listOf(
            MatchCandidate("release-001", "Alice Coltrane", "Journey in Satchidananda", "Impulse!", 92),
            MatchCandidate("release-003", "Sade", "Diamond Life", "Epic", 71),
            MatchCandidate("release-002", "Floating Points", "Elaenia", "Pluto", 58),
        )

    val moods = listOf("Focused", "Relaxed", "Late night", "Social", "Deep listen")

    fun record(releaseId: String?): RecordSummary = records.firstOrNull { it.releaseId == releaseId } ?: records.first()
}
