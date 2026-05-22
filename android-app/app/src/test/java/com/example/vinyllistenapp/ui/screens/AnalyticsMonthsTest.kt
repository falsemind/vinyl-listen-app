package com.example.vinyllistenapp.ui.screens

import com.example.vinyllistenapp.domain.AnalyticsDashboard
import com.example.vinyllistenapp.domain.MonthlyPlayCount
import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.YearMonth

class AnalyticsMonthsTest {
    @Test
    fun lastTwelveMonthsPadsMissingMonths() {
        val months =
            lastTwelveMonths(
                monthlyPlays = listOf(MonthlyPlayCount("2026-05", 3)),
                currentMonth = YearMonth.parse("2026-05"),
            )

        assertEquals(12, months.size)
        assertEquals("2025-06", months.first().month)
        assertEquals(0, months.first().plays)
        assertEquals("2026-05", months.last().month)
        assertEquals(3, months.last().plays)
    }

    @Test
    fun emptyAnalyticsDashboardContainsNoPrototypeData() {
        val dashboard =
            AnalyticsDashboard(
                monthlyPlays = emptyList(),
                topRecords = emptyList(),
                ratingDistribution = emptyList(),
                moodDistribution = emptyList(),
                styleDistribution = emptyList(),
            )

        assertEquals(dashboard, emptyAnalyticsDashboard())
    }
}
