package com.example.vinyllistenapp.ui.screens

import com.example.vinyllistenapp.domain.RecordSummary
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RecordDetailHistoricalStateTest {
    @Test
    fun noSessionBackendRecordShowsZeroStatsAndNoDataSections() {
        val releaseId = "6e3e1c1c-b5c5-4c0e-bbc8-2b5bdb5c4e21"

        assertEquals(0, recordDetailTotalPlays(releaseId, emptyList()))
        assertEquals("0", recordDetailAverageRating(releaseId, emptyList()))
        assertEquals("0", recordDetailLastPlayed(releaseId, emptyList()))
        assertTrue(recordDetailMoodData(releaseId, emptyList()).isEmpty())
        assertTrue(recordDetailHistory(releaseId, emptyList()).isEmpty())
        assertFalse(hasRecordDetailSessionData(releaseId, emptyList()))
    }

    @Test
    fun prototypeRecordsKeepPreviewFallbacks() {
        assertEquals(12, recordDetailTotalPlays("release-001", emptyList()))
        assertEquals("4.8", recordDetailAverageRating("release-001", emptyList()))
        assertFalse(recordDetailMoodData("release-001", emptyList()).isEmpty())
        assertFalse(recordDetailHistory("release-001", emptyList()).isEmpty())
        assertTrue(hasRecordDetailSessionData("release-001", emptyList()))
    }

    @Test
    fun removedCollectionRecordShowsHistoricalBanner() {
        val removedRecord =
            RecordSummary(
                releaseId = "release-removed",
                discogsReleaseId = 11646493,
                artist = "Babe Roots",
                title = "Ruff Out Deh",
                label = "4Weed Records",
                year = 2018,
                format = "Vinyl",
                rating = 0,
                lastPlayed = "0",
                inCollection = false,
                collectionRemovedAt = "2026-06-04T12:00:00Z",
            )

        assertTrue(shouldShowCollectionRemovedMessage(removedRecord))
        assertEquals(
            "This record was removed from your Discogs collection.",
            recordCollectionRemovedMessage(removedRecord),
        )
    }

    @Test
    fun fullReleaseActionOnlyShowsForBasicCollectionRecords() {
        val basicCollectionRecord =
            RecordSummary(
                releaseId = "release-basic",
                discogsReleaseId = 11646493,
                artist = "Babe Roots",
                title = "Ruff Out Deh",
                label = "4Weed Records",
                year = 2018,
                format = "Vinyl",
                rating = 0,
                lastPlayed = "0",
                inCollection = true,
                hasFullDiscogsInfo = false,
            )

        assertTrue(shouldShowGetFullReleaseAction(basicCollectionRecord))
        assertFalse(shouldShowGetFullReleaseAction(basicCollectionRecord.copy(hasFullDiscogsInfo = true)))
        assertFalse(shouldShowGetFullReleaseAction(basicCollectionRecord.copy(inCollection = false)))
        assertFalse(shouldShowGetFullReleaseAction(basicCollectionRecord.copy(releaseId = "release-001")))
    }
}
