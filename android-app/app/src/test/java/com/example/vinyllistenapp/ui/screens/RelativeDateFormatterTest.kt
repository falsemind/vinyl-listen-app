package com.example.vinyllistenapp.ui.screens

import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset

class RelativeDateFormatterTest {
    private val clock = Clock.fixed(Instant.parse("2026-05-10T12:00:00Z"), ZoneOffset.UTC)

    @Test
    fun currentDateReturnsToday() {
        assertEquals("Today", relativeLastPlayedLabel("2026-05-10", clock))
    }

    @Test
    fun recentDatesReturnDays() {
        assertEquals("1d", relativeLastPlayedLabel("2026-05-09", clock))
        assertEquals("6d", relativeLastPlayedLabel("2026-05-04", clock))
    }

    @Test
    fun olderDatesReturnWeeksMonthsAndYears() {
        assertEquals("1w", relativeLastPlayedLabel("2026-05-03", clock))
        assertEquals("1m", relativeLastPlayedLabel("2026-04-10", clock))
        assertEquals("1y", relativeLastPlayedLabel("2025-05-10", clock))
    }

    @Test
    fun unparseableDatesPassThrough() {
        assertEquals("Recent", relativeLastPlayedLabel("Recent", clock))
    }
}
