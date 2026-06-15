package com.example.vinyllistenapp.data.api

import com.example.vinyllistenapp.domain.CollectionSourceOfTruth
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CollectionParsingTest {
    @Test
    fun parsesCollectionRecordsPage() {
        val page =
            JSONObject(
                """
                {
                  "items": [
                    {
                      "id": "release-123",
                      "discogs_release_id": 11646493,
                      "artist": "Babe Roots",
                      "title": "Ruff Out Deh",
                      "year": 2018,
                      "format": "Vinyl, 7\", 45 RPM",
                      "label": "4Weed Records",
                      "catalog_number": "4WDV009",
                      "styles": ["Dub", "Dub Techno"],
                      "thumb_url": "https://example.com/thumb.jpg",
                      "collection_added_at": "2021-10-05T12:32:40-07:00",
                      "in_collection": true
                    }
                  ],
                  "limit": 25,
                  "offset": 0,
                  "total": 41,
                  "has_more": true
                }
                """.trimIndent(),
            ).toCollectionRecordsPage()

        assertEquals(1, page.records.size)
        val record = page.records.first()
        assertEquals("release-123", record.releaseId)
        assertEquals(11646493L, record.discogsReleaseId)
        assertEquals("Babe Roots", record.artist)
        assertEquals("Ruff Out Deh", record.title)
        assertEquals(2018, record.year)
        assertEquals("Vinyl, 7\", 45 RPM", record.format)
        assertEquals("4Weed Records", record.label)
        assertEquals("4WDV009", record.catalogNumber)
        assertEquals(listOf("Dub", "Dub Techno"), record.styles)
        assertEquals("https://example.com/thumb.jpg", record.thumbnailUrl)
        assertTrue(record.inCollection)
        assertEquals(25, page.limit)
        assertEquals(0, page.offset)
        assertEquals(41, page.total)
        assertTrue(page.hasMore)
    }

    @Test
    fun parsesCollectionSyncJobState() {
        val state =
            JSONObject(
                """
                {
                  "job_id": "job-123",
                  "status": "running",
                  "step": "finalizing",
                  "message": "Finalizing collection sync",
                  "total_items": 150,
                  "processed_items": 150,
                  "added_count": 10,
                  "updated_count": 4,
                  "removed_count": 2,
                  "error": null
                }
                """.trimIndent(),
            ).toCollectionSyncJobState()

        assertEquals("job-123", state.jobId)
        assertEquals(CollectionSyncJobStatus.Running, state.status)
        assertEquals(CollectionSyncJobStep.Finalizing, state.step)
        assertEquals("Finalizing collection sync", state.message)
        assertEquals(150, state.totalItems)
        assertEquals(150, state.processedItems)
        assertEquals(10, state.addedCount)
        assertEquals(4, state.updatedCount)
        assertEquals(2, state.removedCount)
        assertFalse(state.status.isTerminal)
    }

    @Test
    fun parsesCollectionSourceOfTruthSettings() {
        assertEquals(
            CollectionSourceOfTruth.App,
            JSONObject("""{"source_of_truth": "APP"}""").toCollectionSourceOfTruth(),
        )
        assertEquals(
            CollectionSourceOfTruth.Discogs,
            JSONObject("""{"source_of_truth": "DISCOGS"}""").toCollectionSourceOfTruth(),
        )
        assertEquals(
            CollectionSourceOfTruth.App,
            JSONObject("""{"source_of_truth": "unknown"}""").toCollectionSourceOfTruth(),
        )
    }

    @Test
    fun parsesDiscogsIntegrationStatus() {
        val status =
            JSONObject(
                """
                {
                  "provider": "DISCOGS",
                  "access_token_saved": true,
                  "external_user_id": "123",
                  "external_username": "alex",
                  "source_of_truth": "DISCOGS",
                  "backend_identify_enabled": true
                }
                """.trimIndent(),
            ).toDiscogsIntegrationStatus()

        assertTrue(status.accessTokenSaved)
        assertEquals("123", status.externalUserId)
        assertEquals("alex", status.externalUsername)
        assertEquals(CollectionSourceOfTruth.Discogs, status.sourceOfTruth)
        assertTrue(status.backendIdentifyEnabled)
    }

    @Test
    fun parsesMissingDiscogsIntegrationStatusFieldsAsUnsaved() {
        val status = JSONObject("{}").toDiscogsIntegrationStatus()

        assertFalse(status.accessTokenSaved)
        assertEquals(null, status.externalUserId)
        assertEquals(null, status.externalUsername)
        assertEquals(CollectionSourceOfTruth.App, status.sourceOfTruth)
        assertFalse(status.backendIdentifyEnabled)
    }

    @Test
    fun parsesExpiredCollectionSyncJobStateAsTerminal() {
        val state =
            JSONObject(
                """
                {
                  "job_id": "job-123",
                  "status": "expired",
                  "step": "fetching",
                  "message": "Collection sync expired. Start a new sync.",
                  "error": {
                    "code": "collection_sync_job_stale",
                    "message": "Collection sync expired. Start a new sync.",
                    "failed_step": "fetching"
                  }
                }
                """.trimIndent(),
            ).toCollectionSyncJobState()

        assertEquals(CollectionSyncJobStatus.Expired, state.status)
        assertTrue(state.status.isTerminal)
        assertEquals("Collection sync expired. Start a new sync.", state.error?.message)
        assertEquals("fetching", state.error?.failedStep)
    }
}
