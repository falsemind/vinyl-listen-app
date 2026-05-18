package com.example.vinyllistenapp.navigation

import com.example.vinyllistenapp.domain.MatchCandidate
import org.junit.Assert.assertEquals
import org.junit.Test

class VinylNavHostStateTest {
    @Test
    fun matchCandidatesRoundTripThroughSavedStatePayload() {
        val candidates =
            listOf(
                MatchCandidate(
                    releaseId = "release-123",
                    discogsReleaseId = 555123,
                    artist = "Artist",
                    title = "Title",
                    label = "Label",
                    confidence = 88,
                    year = 2026,
                    catalogNumber = "CAT001",
                    barcode = "1234567890123",
                    coverImageUrl = "https://example.com/cover.jpg",
                    format = "Vinyl, LP",
                    matchSource = "local",
                    matchedOn = listOf("local_lookup", "title"),
                ),
            )

        val restored = decodeMatchCandidatesFromSavedState(encodeMatchCandidatesForSavedState(candidates))

        assertEquals(candidates, restored)
    }
}
