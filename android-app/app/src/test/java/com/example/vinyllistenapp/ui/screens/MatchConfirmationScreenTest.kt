package com.example.vinyllistenapp.ui.screens

import com.example.vinyllistenapp.domain.MatchCandidate
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class MatchConfirmationScreenTest {
    @Test
    fun fallbackRecordDoesNotUseMockRecordForUnknownLocalReleaseId() {
        val candidate =
            matchCandidate(
                releaseId = "real-backend-release-id",
                discogsReleaseId = 249504,
                matchSource = "local",
            )

        assertNull(matchFallbackRecord(candidate))
    }

    @Test
    fun discogsCandidateCanStillUseMockRecordFallback() {
        val candidate =
            matchCandidate(
                releaseId = null,
                discogsReleaseId = 249504,
                matchSource = "discogs",
            )

        assertEquals(249504L, matchFallbackRecord(candidate)?.discogsReleaseId)
    }

    @Test
    fun localCandidateFallsBackToVinylFormatWhenBackendCandidateHasNoFormat() {
        val candidate =
            matchCandidate(
                releaseId = "real-backend-release-id",
                discogsReleaseId = 999999,
                matchSource = "local",
                format = null,
            )

        assertEquals("Vinyl", matchDisplayFormat(candidate, fallbackRecord = null))
    }

    @Test
    fun discogsCandidateStillShowsUnknownFormatWhenNoFormatWasReturned() {
        val candidate =
            matchCandidate(
                releaseId = null,
                discogsReleaseId = 999999,
                matchSource = "discogs",
                format = null,
            )

        assertEquals("Unknown format", matchDisplayFormat(candidate, fallbackRecord = null))
    }

    @Test
    fun barcodeCandidateImportsFromDeviceWhenNoLocalReleaseExists() {
        val candidate =
            matchCandidate(
                releaseId = null,
                discogsReleaseId = 999999,
                matchSource = "Barcode scan",
            )

        assertEquals(true, candidate.shouldImportFromDevice())
    }

    @Test
    fun backendDiscogsCandidateUsesBackendImport() {
        val candidate =
            matchCandidate(
                releaseId = null,
                discogsReleaseId = 999999,
                matchSource = "discogs",
            )

        assertEquals(false, candidate.shouldImportFromDevice())
    }

    @Test
    fun collectionAddModeUsesBackendCollectionImportForBarcodeCandidates() {
        val candidate =
            matchCandidate(
                releaseId = null,
                discogsReleaseId = 999999,
                matchSource = "Barcode scan",
            )

        assertEquals(false, candidate.shouldImportFromDevice(MatchConfirmationMode.CollectionAdd))
    }

    private fun matchCandidate(
        releaseId: String?,
        discogsReleaseId: Long,
        matchSource: String?,
        format: String? = "Vinyl, LP",
    ) = MatchCandidate(
        releaseId = releaseId,
        discogsReleaseId = discogsReleaseId,
        artist = "Artist",
        title = "Title",
        label = "Label",
        confidence = 90,
        format = format,
        matchSource = matchSource,
    )
}
