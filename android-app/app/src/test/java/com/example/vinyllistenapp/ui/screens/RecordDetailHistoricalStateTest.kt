package com.example.vinyllistenapp.ui.screens

import com.example.vinyllistenapp.domain.RecordSummary
import com.example.vinyllistenapp.domain.ReleaseArtist
import com.example.vinyllistenapp.domain.ReleaseTrack
import com.example.vinyllistenapp.domain.ReleaseTrackArtist
import com.example.vinyllistenapp.domain.ReleaseTrackCredit
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
    fun releaseSyncOnlyShowsForDiscogsBackedRecords() {
        val discogsBackedRecord =
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

        assertTrue(canSyncRelease(discogsBackedRecord))
        assertTrue(shouldAutoImportFullRelease(discogsBackedRecord))
        assertTrue(canSyncRelease(discogsBackedRecord.copy(hasFullDiscogsInfo = true)))
        assertFalse(shouldAutoImportFullRelease(discogsBackedRecord.copy(hasFullDiscogsInfo = true)))
        assertTrue(canSyncRelease(discogsBackedRecord.copy(inCollection = false)))
        assertFalse(canSyncRelease(discogsBackedRecord.copy(discogsReleaseId = 0)))
        assertFalse(canSyncRelease(discogsBackedRecord.copy(releaseId = "release-001")))
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
    fun actionMenusIncludeTrackArtists() {
        val record =
            RecordSummary(
                releaseId = "release-full",
                discogsReleaseId = 18590200,
                artist = "Various",
                title = "Meeting Of The Minds Vol. 8",
                label = "Western Lore",
                year = 2021,
                format = "Vinyl",
                rating = 0,
                lastPlayed = "0",
                hasFullDiscogsInfo = true,
                tracklist =
                    listOf(
                        ReleaseTrack(
                            position = "A1",
                            title = "Burger Sauce",
                            artists =
                                listOf(
                                    ReleaseTrackArtist(name = "Equinox (3)", join = "&", discogsArtistId = 67456),
                                    ReleaseTrackArtist(name = "Tim Reaper", discogsArtistId = 1881856),
                                ),
                        ),
                        ReleaseTrack(
                            position = "A2",
                            title = "Re-Entry",
                            artists =
                                listOf(
                                    ReleaseTrackArtist(name = "Infest (3)", join = "&", discogsArtistId = 1379026),
                                    ReleaseTrackArtist(name = "Tim Reaper", discogsArtistId = 1881856),
                                ),
                        ),
                    ),
            )

        assertTrue(shouldShowArtistDiscographyAction(record))
        assertEquals(listOf("Equinox", "Tim Reaper", "Infest"), collectionArtistNames(record))
        assertEquals(
            listOf(
                ReleaseArtist("Equinox", 67456),
                ReleaseArtist("Tim Reaper", 1881856),
                ReleaseArtist("Infest", 1379026),
            ),
            discogsArtistRows(record),
        )
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

    @Test
    fun recordDetailStyleTagsPreferStylesAndFallbackToGenres() {
        val record =
            recordWithTracks(
                hasFullDiscogsInfo = true,
                tracklist = listOf(ReleaseTrack(position = "A1", title = "Track", duration = "3:12")),
            )

        assertEquals(
            listOf("Techno"),
            recordDetailStyleTags(record.copy(genres = listOf("Electronic"), styles = listOf("Techno"))),
        )
        assertEquals(
            listOf("Electronic"),
            recordDetailStyleTags(record.copy(genres = listOf("Electronic"), styles = emptyList())),
        )
        assertTrue(recordDetailStyleTags(record.copy(genres = emptyList(), styles = emptyList())).isEmpty())
    }

    @Test
    fun trackCreditsDisplayRoleAndArtistNames() {
        val track =
            ReleaseTrack(
                position = "B2",
                title = "Ketel",
                artists =
                    listOf(
                        ReleaseTrackArtist(name = "Equinox", join = "&"),
                        ReleaseTrackArtist(name = "Tim Reaper"),
                    ),
                extraArtists =
                    listOf(
                        ReleaseTrackCredit(name = "TMSV", role = "Remix"),
                        ReleaseTrackCredit(name = "Requake", role = " remix "),
                        ReleaseTrackCredit(name = "TMSV", role = "Remix"),
                        ReleaseTrackCredit(name = "Begum X", role = "Featuring"),
                        ReleaseTrackCredit(name = "Delhi Sultanate", role = "Featuring"),
                        ReleaseTrackCredit(name = "Dub Studio"),
                    ),
            )

        assertEquals("B2: Equinox & Tim Reaper - Ketel", displayReleaseTrack(track))
        assertEquals("Equinox & Tim Reaper", displayReleaseTrackArtists(track))
        assertEquals(
            "Remix: TMSV, Requake; Featuring: Begum X, Delhi Sultanate; Dub Studio",
            displayReleaseTrackCredits(track),
        )
        assertEquals(
            "B2: Equinox, Tim Reaper - Ketel",
            displayReleaseTrack(track.copy(artists = track.artists.map { it.copy(join = null) })),
        )
        assertNull(displayReleaseTrackCredits(track.copy(extraArtists = emptyList())))
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
