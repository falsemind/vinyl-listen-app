package com.example.vinyllistenapp.ui.screens

import com.example.vinyllistenapp.domain.RecordSummary
import com.example.vinyllistenapp.domain.ReleaseSideOption
import com.example.vinyllistenapp.domain.ReleaseTrack
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SessionSideOptionsTest {
    @Test
    fun sessionSideOptionsUsesReleaseAvailableSides() {
        val record = recordSummary(availableSides = listOf("A", "AA"))

        assertEquals(listOf(SessionSideOption("A", "Side A"), SessionSideOption("AA", "Side AA")), sessionSideOptions(record))
    }

    @Test
    fun sessionSideOptionsPrefersDetailedSideOptions() {
        val record =
            recordSummary(
                availableSides = listOf("X", "Y"),
                availableSideOptions =
                    listOf(
                        ReleaseSideOption("1:X", "Disc 1 - Side X"),
                        ReleaseSideOption("2:X", "Disc 2 - Side X"),
                    ),
            )

        assertEquals(
            listOf(
                SessionSideOption("1:X", "Disc 1 - Side X"),
                SessionSideOption("2:X", "Disc 2 - Side X"),
            ),
            sessionSideOptions(record),
        )
    }

    @Test
    fun sessionSideOptionsFallsBackToPrototypeSides() {
        val record = recordSummary(availableSides = emptyList())

        assertEquals(listOf(SessionSideOption("A", "Side A"), SessionSideOption("B", "Side B")), sessionSideOptions(record))
    }

    @Test
    fun sessionSideOptionsCanSuppressPrototypeFallback() {
        val record = recordSummary(availableSides = emptyList())

        assertEquals(emptyList<SessionSideOption>(), sessionSideOptions(record, usePrototypeFallback = false))
    }

    @Test
    fun displaySessionSideAddsReadablePrefix() {
        assertEquals("Side AA", displaySessionSide("AA"))
    }

    @Test
    fun sessionTrackOptionsFiltersTracksForSelectedSide() {
        val record =
            recordSummary(
                availableSides = listOf("X", "Y"),
                tracklist =
                    listOf(
                        ReleaseTrack("X1", "UNTITLED"),
                        ReleaseTrack("X2", "S.O.U.R"),
                        ReleaseTrack("Y1", "BLESSINGS"),
                    ),
            )

        assertEquals(
            listOf(
                SessionTrackOption("X1", "X1: UNTITLED"),
                SessionTrackOption("X2", "X2: S.O.U.R"),
            ),
            sessionTrackOptions(record, SessionSideOption("X", "Side X")),
        )
    }

    @Test
    fun sessionTrackOptionsMatchesDetailedDiscSideValue() {
        val record =
            recordSummary(
                availableSideOptions = listOf(ReleaseSideOption("1:X", "Disc 1 - Side X")),
                availableSides = listOf("X"),
                tracklist = listOf(ReleaseTrack("X2", "S.O.U.R", "5:12")),
            )

        assertEquals(
            listOf(SessionTrackOption("X2", "X2: S.O.U.R 5:12")),
            sessionTrackOptions(record, SessionSideOption("1:X", "Disc 1 - Side X")),
        )
    }

    @Test
    fun isBuiltInMoodMatchesIgnoringCaseAndWhitespace() {
        assertTrue(isBuiltInMood(" calm "))
        assertTrue(isBuiltInMood("FOCUSED"))
        assertFalse(isBuiltInMood("Late Night"))
    }

    @Test
    fun isExistingMoodMatchesCustomMoodsIgnoringCase() {
        assertTrue(isExistingMood(" late night ", customMoods = listOf("Late Night")))
        assertTrue(isExistingMood("calm", customMoods = listOf("Late Night")))
        assertFalse(isExistingMood("Dubby", customMoods = listOf("Late Night")))
    }

    @Test
    fun loadSessionRecordSkipsRefreshForFullRelease() =
        runBlocking {
            var refreshCalls = 0
            val fullRelease = recordSummary(availableSides = listOf("A"), hasFullDiscogsInfo = true)

            val result =
                loadSessionRecord(
                    releaseId = "release-123",
                    getRelease = { fullRelease },
                    refreshRelease = {
                        refreshCalls += 1
                        recordSummary(availableSides = listOf("X"), hasFullDiscogsInfo = true)
                    },
                )

            assertEquals(fullRelease, result)
            assertEquals(0, refreshCalls)
        }

    @Test
    fun loadSessionRecordRefreshesBasicRelease() =
        runBlocking {
            val basicRelease = recordSummary(availableSides = emptyList(), hasFullDiscogsInfo = false)
            val fullRelease =
                recordSummary(
                    availableSides = listOf("X"),
                    hasFullDiscogsInfo = true,
                    tracklist = listOf(ReleaseTrack("X1", "Hydrated")),
                )

            val result =
                loadSessionRecord(
                    releaseId = "release-123",
                    getRelease = { basicRelease },
                    refreshRelease = { fullRelease },
                )

            assertEquals(fullRelease, result)
        }

    @Test
    fun loadSessionRecordFallsBackToBasicReleaseWhenRefreshFails() =
        runBlocking {
            val basicRelease = recordSummary(availableSides = emptyList(), hasFullDiscogsInfo = false)

            val result =
                loadSessionRecord(
                    releaseId = "release-123",
                    getRelease = { basicRelease },
                    refreshRelease = { error("Discogs unavailable") },
                )

            assertEquals(basicRelease, result)
        }

    private fun recordSummary(
        availableSides: List<String>,
        availableSideOptions: List<ReleaseSideOption> = emptyList(),
        tracklist: List<ReleaseTrack> = emptyList(),
        hasFullDiscogsInfo: Boolean = false,
    ) = RecordSummary(
        releaseId = "release-123",
        discogsReleaseId = 555123,
        artist = "Artist",
        title = "Title",
        label = "Label",
        year = 2026,
        format = "Vinyl",
        rating = 0,
        lastPlayed = "Not logged yet",
        availableSides = availableSides,
        availableSideOptions = availableSideOptions,
        hasFullDiscogsInfo = hasFullDiscogsInfo,
        tracklist = tracklist,
    )
}
