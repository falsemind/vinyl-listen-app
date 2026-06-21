package com.example.vinyllistenapp.data.api

import com.example.vinyllistenapp.domain.ManualReleaseCoverValidationState
import com.example.vinyllistenapp.domain.ManualReleaseFormState
import com.example.vinyllistenapp.domain.ManualReleaseFormat
import com.example.vinyllistenapp.domain.ManualReleasePrimaryAction
import com.example.vinyllistenapp.domain.ManualReleaseTrackCreditRole
import com.example.vinyllistenapp.domain.ManualReleaseTrackInput
import com.example.vinyllistenapp.domain.ManualReleaseVinylSize
import com.example.vinyllistenapp.domain.ManualReleaseVinylSpeed
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ManualReleaseParsingTest {
    @Test
    fun parsesManualReleaseDraftListAndFullDraft() {
        val draft =
            JSONObject(
                """
                {
                  "id": "draft-1",
                  "artist": "Gradient Sync",
                  "title": "Night Plates",
                  "label": "Room Tone",
                  "catalog_number": "RT-12",
                  "format": "Vinyl",
                  "cover_thumbnail_url": "https://example.com/thumb.jpg",
                  "completion_state": {
                    "required_complete": true
                  },
                  "updated_at": "2026-06-21T12:00:00Z",
                  "created_at": "2026-06-20T12:00:00Z",
                  "form_data": {
                    "artists": ["Gradient Sync"],
                    "title": "Night Plates",
                    "label": "Room Tone",
                    "catalog_number": "RT-12",
                    "barcode": "1234567890123",
                    "format": "Vinyl",
                    "vinyl_size": "12",
                    "vinyl_speed": "33 1/3",
                    "vinyl_disc_count": 2,
                    "genres": ["Electronic"],
                    "styles": ["Techno"],
                    "tracklist": [
                      {
                        "position": "A1",
                        "title": "Low Ceiling",
                        "duration": "6:30",
                        "credits": [
                          {
                            "role": "Featuring",
                            "name": "Guest Artist"
                          }
                        ]
                      }
                    ]
                  },
                  "cover_image_url": "https://example.com/full.jpg",
                  "cover_content_type": "image/jpeg",
                  "cover_size_bytes": 1024
                }
                """.trimIndent(),
            ).toManualReleaseDraft()

        assertEquals("draft-1", draft.id)
        assertEquals("Gradient Sync", draft.artist)
        assertEquals("RT-12", draft.catalogNumber)
        assertTrue(draft.completionState?.requiredComplete == true)
        assertEquals("https://example.com/full.jpg", draft.coverImageUrl)
        assertEquals("image/jpeg", draft.coverContentType)
        assertEquals(1024, draft.coverSizeBytes)
        assertEquals(ManualReleaseFormat.Vinyl, draft.formData.format)
        assertEquals(ManualReleaseVinylSize.TwelveInch, draft.formData.vinylSize)
        assertEquals(ManualReleaseVinylSpeed.ThirtyThree, draft.formData.vinylSpeed)
        assertEquals(2, draft.formData.vinylDiscCount)
        assertEquals(listOf("Electronic"), draft.formData.genres)
        assertEquals(listOf("Techno"), draft.formData.styles)
        assertEquals(
            "Low Ceiling",
            draft.formData.tracklist
                .first()
                .title,
        )
        assertEquals(
            ManualReleaseTrackCreditRole.Featuring,
            draft.formData.tracklist
                .first()
                .credits
                .first()
                .role,
        )

        val list =
            JSONObject(
                """
                {
                  "items": [
                    {
                      "id": "draft-1",
                      "artist": "Gradient Sync",
                      "title": "Night Plates",
                      "label": "Room Tone",
                      "catalog_number": "RT-12",
                      "format": "Vinyl",
                      "cover_thumbnail_url": null,
                      "completion_state": {
                        "required_complete": false
                      },
                      "updated_at": "2026-06-21T12:00:00Z"
                    }
                  ],
                  "limit": 5,
                  "remaining_slots": 4
                }
                """.trimIndent(),
            ).toManualReleaseDraftList()

        assertEquals(1, list.items.size)
        assertEquals(5, list.limit)
        assertEquals(4, list.remainingSlots)
        assertFalse(
            list.items
                .first()
                .completionState
                ?.requiredComplete == true,
        )
    }

    @Test
    fun parsesManualReleaseSaveAndCoverResponses() {
        val saved =
            JSONObject(
                """
                {
                  "id": "manual-1",
                  "title": "Night Plates",
                  "artist": "Gradient Sync",
                  "in_collection": true
                }
                """.trimIndent(),
            ).toManualReleaseSaveResult()
        val cover =
            JSONObject(
                """
                {
                  "content_type": "image/jpeg",
                  "size_bytes": 2048
                }
                """.trimIndent(),
            ).toManualReleaseCoverUploadResult()

        assertEquals("manual-1", saved.id)
        assertEquals("Night Plates", saved.title)
        assertTrue(saved.inCollection)
        assertEquals("image/jpeg", cover.contentType)
        assertEquals(2048, cover.sizeBytes)
    }

    @Test
    fun manualReleaseFormStateChoosesPrimaryActionFromRequiredFields() {
        val emptyState = ManualReleaseFormState()

        assertFalse(emptyState.hasAnyInput)
        assertEquals(ManualReleasePrimaryAction.DisabledSave, emptyState.primaryAction)

        val draftState =
            emptyState.copy(
                formData = emptyState.formData.copy(title = "Partial title"),
            )

        assertTrue(draftState.hasAnyInput)
        assertEquals(ManualReleasePrimaryAction.SaveDraft, draftState.primaryAction)

        val releaseState =
            emptyState.copy(
                formData =
                    emptyState.formData.copy(
                        artists = listOf("Gradient Sync"),
                        title = "Night Plates",
                        label = "Room Tone",
                        format = ManualReleaseFormat.Vinyl,
                        vinylSize = ManualReleaseVinylSize.TwelveInch,
                        vinylSpeed = ManualReleaseVinylSpeed.ThirtyThree,
                        vinylDiscCount = 2,
                        genres = listOf("Electronic"),
                        styles = listOf("Techno"),
                        tracklist =
                            listOf(
                                ManualReleaseTrackInput(title = "Low Ceiling"),
                            ),
                    ),
            )

        assertTrue(releaseState.requiredComplete)
        assertEquals(ManualReleasePrimaryAction.SaveRelease, releaseState.primaryAction)
    }

    @Test
    fun manualReleaseFormStateTracksDirtyFieldsAndCoverValidation() {
        val state =
            ManualReleaseFormState(
                coverUri = "content://covers/draft-1",
                coverContentType = "image/gif",
                coverSizeBytes = 4 * 1024 * 1024,
                dirtyFields = setOf("title", "cover"),
                fieldErrors = mapOf("title" to "Backend title error."),
            )

        assertEquals(setOf("title", "cover"), state.dirtyFields)
        assertEquals(ManualReleaseCoverValidationState.TooLarge, state.coverValidationState)
        assertEquals("Backend title error.", state.localFieldErrors["title"])
        assertEquals("Cover image must be 3 MB or smaller.", state.localFieldErrors["cover"])
    }
}
