package com.example.vinyllistenapp.data.api

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AnalyticsPageParsingTest {
    @Test
    fun parsesMonthSessionsPage() {
        val page =
            JSONObject(
                """
                {
                  "sessions": [
                    {
                      "session_id": "session-123",
                      "release_id": "release-123",
                      "artist": "Rhythm & Sound",
                      "title": "Carrier",
                      "thumbnail_url": "https://example.com/cover.jpg",
                      "date": "2026-05-10",
                      "played_at": "2026-05-10T23:30:00Z",
                      "side": "A",
                      "rating": 5,
                      "mood": "Focused",
                      "has_notes": true
                    }
                  ],
                  "pagination": {
                    "limit": 10,
                    "offset": 0,
                    "total": 12,
                    "has_more": true
                  }
                }
                """.trimIndent(),
            ).toAnalyticsSessionsPage()

        assertEquals(1, page.sessions.size)
        assertEquals("session-123", page.sessions.first().sessionId)
        assertEquals("release-123", page.sessions.first().releaseId)
        assertEquals("Rhythm & Sound", page.sessions.first().artist)
        assertEquals("Carrier", page.sessions.first().title)
        assertEquals("2026-05-10T23:30:00Z", page.sessions.first().playedAt)
        assertEquals("Focused", page.sessions.first().mood)
        assertEquals(5, page.sessions.first().rating)
        assertEquals("A", page.sessions.first().side)
        assertTrue(page.sessions.first().hasNotes)
        assertEquals(10, page.pagination.limit)
        assertEquals(0, page.pagination.offset)
        assertEquals(12, page.pagination.total)
        assertTrue(page.pagination.hasMore)
    }

    @Test
    fun parsesSessionPageFallbacksAndEmptyPagination() {
        val page =
            JSONObject(
                """
                {
                  "sessions": [
                    {
                      "release_id": "release-456",
                      "artist": "Unknown Artist",
                      "title": "Untitled",
                      "date": "2026-05-11",
                      "rating": null,
                      "mood": null,
                      "has_notes": false
                    }
                  ]
                }
                """.trimIndent(),
            ).toAnalyticsSessionsPage()

        assertEquals("2026-05-11", page.sessions.first().playedAt)
        assertEquals("Unspecified", page.sessions.first().mood)
        assertEquals(0, page.sessions.first().rating)
        assertNull(page.sessions.first().sessionId)
        assertFalse(page.sessions.first().hasNotes)
        assertEquals(10, page.pagination.limit)
        assertEquals(0, page.pagination.offset)
        assertEquals(0, page.pagination.total)
        assertFalse(page.pagination.hasMore)
    }

    @Test
    fun parsesRecordCountsPage() {
        val page =
            JSONObject(
                """
                {
                  "records": [
                    {
                      "release_id": "release-789",
                      "discogs_release_id": 555123,
                      "artist": "Basic Channel",
                      "title": "Phylyps Trak",
                      "thumbnail_url": "https://example.com/basic.jpg",
                      "count": 7
                    }
                  ],
                  "pagination": {
                    "limit": 10,
                    "offset": 10,
                    "total": 17,
                    "has_more": false
                  }
                }
                """.trimIndent(),
            ).toAnalyticsRecordCountsPage()

        assertEquals(1, page.records.size)
        val item = page.records.first()
        assertEquals("release-789", item.record.releaseId)
        assertEquals(555123L, item.record.discogsReleaseId)
        assertEquals("Basic Channel", item.record.artist)
        assertEquals("Phylyps Trak", item.record.title)
        assertEquals("https://example.com/basic.jpg", item.record.coverImageUrl)
        assertEquals(7, item.count)
        assertEquals(10, page.pagination.limit)
        assertEquals(10, page.pagination.offset)
        assertEquals(17, page.pagination.total)
        assertFalse(page.pagination.hasMore)
    }

    @Test
    fun parsesEmptyRecordCountsPage() {
        val page =
            JSONObject(
                """
                {
                  "records": [],
                  "pagination": {
                    "limit": 10,
                    "offset": 0,
                    "total": 0,
                    "has_more": false
                  }
                }
                """.trimIndent(),
            ).toAnalyticsRecordCountsPage()

        assertTrue(page.records.isEmpty())
        assertEquals(10, page.pagination.limit)
        assertEquals(0, page.pagination.offset)
        assertEquals(0, page.pagination.total)
        assertFalse(page.pagination.hasMore)
    }
}
