package com.example.vinyllistenapp.data.api

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class IdentifyJobStateParsingTest {
    @Test
    fun parsesCanceledStatusAndCancelRequestedFlag() {
        val state =
            JSONObject(
                """
                {
                  "job_id": "job-123",
                  "status": "canceled",
                  "message": "Identify canceled",
                  "cancel_requested": true,
                  "result": null,
                  "error": null
                }
                """.trimIndent(),
            ).toIdentifyJobState()

        assertEquals("job-123", state.jobId)
        assertEquals(IdentifyJobStatus.Canceled, state.status)
        assertEquals("Identify canceled", state.message)
        assertTrue(state.cancelRequested)
        assertTrue(state.status.isTerminal)
    }

    @Test
    fun defaultsMissingCancelRequestedToFalse() {
        val state =
            JSONObject(
                """
                {
                  "job_id": "job-456",
                  "status": "upload_received",
                  "message": "Image upload received",
                  "result": null,
                  "error": null
                }
                """.trimIndent(),
            ).toIdentifyJobState()

        assertEquals(IdentifyJobStatus.UploadReceived, state.status)
        assertFalse(state.cancelRequested)
        assertFalse(state.status.isTerminal)
    }
}
