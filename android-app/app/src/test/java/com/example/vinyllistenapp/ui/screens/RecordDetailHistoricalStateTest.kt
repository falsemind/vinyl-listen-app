package com.example.vinyllistenapp.ui.screens

import com.example.vinyllistenapp.domain.RecordSummary
import com.example.vinyllistenapp.domain.ReleaseArtist
import com.example.vinyllistenapp.domain.ReleaseTrack
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
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
            "This record is not in your collection.",
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

    @Test
    fun artistDiscographyActionOnlyShowsForFullReleaseWithArtists() {
        val record =
            RecordSummary(
                releaseId = "release-full",
                discogsReleaseId = 11646493,
                artist = "Babe Roots",
                title = "Ruff Out Deh",
                label = "4Weed Records",
                year = 2018,
                format = "Vinyl",
                rating = 0,
                lastPlayed = "0",
                hasFullDiscogsInfo = true,
                discogsArtists = listOf(ReleaseArtist("Babe Roots", 5440883)),
            )

        assertTrue(shouldShowArtistDiscographyAction(record))
        assertFalse(shouldShowArtistDiscographyAction(record.copy(hasFullDiscogsInfo = false)))
        assertFalse(shouldShowArtistDiscographyAction(record.copy(discogsArtists = emptyList())))
        assertEquals("https://www.discogs.com/artist/5440883", discogsArtistUrl(5440883))
    }

    @Test
    fun releaseTotalPlayTimeOnlyShowsForFullReleaseWithEveryDuration() {
        val fullRecord =
            recordWithTracks(
                hasFullDiscogsInfo = true,
                tracklist =
                    listOf(
                        ReleaseTrack(position = "A1", title = "Intro", duration = "1:17"),
                        ReleaseTrack(position = "A2", title = "Long Form", duration = "1:02:03"),
                        ReleaseTrack(position = "B1", title = "Outro", duration = "5:40"),
                    ),
            )

        assertEquals("Total time: 1h 9m 0s", releaseTotalPlayTimeText(fullRecord))
        assertEquals(
            "Total time: 6m 57s",
            releaseTotalPlayTimeText(fullRecord.copy(tracklist = listOf(ReleaseTrack("A1", "Short Tune", "6:57")))),
        )
        assertNull(releaseTotalPlayTimeText(fullRecord.copy(hasFullDiscogsInfo = false)))
        assertNull(releaseTotalPlayTimeText(fullRecord.copy(tracklist = fullRecord.tracklist + ReleaseTrack("B2", "Dub"))))
        assertNull(releaseTotalPlayTimeText(fullRecord.copy(tracklist = listOf(ReleaseTrack("A1", "Bad", "3:99")))))
    }

    private fun recordWithTracks(
        hasFullDiscogsInfo: Boolean,
        tracklist: List<ReleaseTrack>,
    ): RecordSummary =
        RecordSummary(
            releaseId = "release-with-tracks",
            discogsReleaseId = 11646493,
            artist = "Babe Roots",
            title = "Ruff Out Deh",
            label = "4Weed Records",
            year = 2018,
            format = "Vinyl",
            rating = 0,
            lastPlayed = "0",
            hasFullDiscogsInfo = hasFullDiscogsInfo,
            tracklist = tracklist,
        )
}
