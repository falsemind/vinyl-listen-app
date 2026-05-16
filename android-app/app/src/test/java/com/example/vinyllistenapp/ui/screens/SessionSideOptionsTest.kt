package com.example.vinyllistenapp.ui.screens

import com.example.vinyllistenapp.domain.RecordSummary
import com.example.vinyllistenapp.domain.ReleaseSideOption
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

    private fun recordSummary(
        availableSides: List<String>,
        availableSideOptions: List<ReleaseSideOption> = emptyList(),
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
    )
}
