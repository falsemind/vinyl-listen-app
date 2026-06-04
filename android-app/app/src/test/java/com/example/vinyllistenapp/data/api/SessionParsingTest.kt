package com.example.vinyllistenapp.data.api

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SessionParsingTest {
    @Test
    fun parsesEditableSessionResponse() {
        val session =
            JSONObject(
                """
                {
                  "id": "session-123",
                  "release_id": "release-123",
                  "played_at": "2026-06-04T20:12:00Z",
                  "vinyl_side": "B",
                  "rating": 4,
                  "mood": "Focused",
                  "notes": "Opened up after the second track.",
                  "created_at": "2026-06-04T20:13:00Z",
                  "can_edit": true,
                  "editable_until": "2026-06-04T20:28:00Z"
                }
                """.trimIndent(),
            ).toListeningSession()

        assertEquals("session-123", session.sessionId)
        assertEquals("release-123", session.releaseId)
        assertEquals("2026-06-04T20:12:00Z", session.playedAt)
        assertEquals("B", session.side)
        assertEquals(4, session.rating)
        assertEquals("Focused", session.mood)
        assertEquals("Opened up after the second track.", session.notes)
        assertTrue(session.hasNotes)
        assertEquals("2026-06-04T20:13:00Z", session.createdAt)
        assertTrue(session.canEdit)
        assertEquals("2026-06-04T20:28:00Z", session.editableUntil)
    }

    @Test
    fun parsesCompactSessionCardMetadata() {
        val session =
            JSONObject(
                """
                {
                  "session_id": "session-456",
                  "release_id": "release-456",
                  "artist": "Basic Channel",
                  "title": "Phylyps Trak",
                  "thumbnail_url": "https://example.com/cover.jpg",
                  "date": "2026-06-03",
                  "side": "A",
                  "rating": null,
                  "mood": null,
                  "has_notes": false,
                  "created_at": "2026-06-03T18:00:00Z",
                  "can_edit": false,
                  "editable_until": "2026-06-03T18:15:00Z"
                }
                """.trimIndent(),
            ).toListeningSession()

        assertEquals("session-456", session.sessionId)
        assertEquals("release-456", session.releaseId)
        assertEquals("Basic Channel", session.artist)
        assertEquals("Phylyps Trak", session.title)
        assertEquals("https://example.com/cover.jpg", session.thumbnailUrl)
        assertEquals("2026-06-03", session.playedAt)
        assertEquals("A", session.side)
        assertEquals(0, session.rating)
        assertEquals("Unspecified", session.mood)
        assertFalse(session.hasNotes)
        assertEquals("2026-06-03T18:00:00Z", session.createdAt)
        assertFalse(session.canEdit)
        assertEquals("2026-06-03T18:15:00Z", session.editableUntil)
    }
}
