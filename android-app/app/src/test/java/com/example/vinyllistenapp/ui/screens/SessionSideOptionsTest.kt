package com.example.vinyllistenapp.ui.screens

import com.example.vinyllistenapp.domain.RecordSummary
import org.junit.Assert.assertEquals
import org.junit.Test

class SessionSideOptionsTest {
    @Test
    fun sessionSideOptionsUsesReleaseAvailableSides() {
        val record = recordSummary(availableSides = listOf("A", "AA"))

        assertEquals(listOf("A", "AA"), sessionSideOptions(record))
    }

    @Test
    fun sessionSideOptionsFallsBackToPrototypeSides() {
        val record = recordSummary(availableSides = emptyList())

        assertEquals(listOf("A", "B"), sessionSideOptions(record))
    }

    @Test
    fun sessionSideOptionsCanSuppressPrototypeFallback() {
        val record = recordSummary(availableSides = emptyList())

        assertEquals(emptyList<String>(), sessionSideOptions(record, usePrototypeFallback = false))
    }

    @Test
    fun displaySessionSideAddsReadablePrefix() {
        assertEquals("Side AA", displaySessionSide("AA"))
    }

    private fun recordSummary(availableSides: List<String>) =
        RecordSummary(
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
        )
}
