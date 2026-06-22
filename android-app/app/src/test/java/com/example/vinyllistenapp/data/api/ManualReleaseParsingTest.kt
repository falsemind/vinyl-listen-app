package com.example.vinyllistenapp.data.api

import com.example.vinyllistenapp.BuildConfig
import com.example.vinyllistenapp.domain.ManualReleaseCoverValidationState
import com.example.vinyllistenapp.domain.ManualReleaseFormData
import com.example.vinyllistenapp.domain.ManualReleaseFormState
import com.example.vinyllistenapp.domain.ManualReleaseFormat
import com.example.vinyllistenapp.domain.ManualReleasePrimaryAction
import com.example.vinyllistenapp.domain.ManualReleaseTrackCreditInput
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
                  "cover_thumbnail_url": "/media/manual-release-covers/user-1/draft-1/cover.jpg",
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
                  "cover_image_url": "/media/manual-release-covers/user-1/draft-1/cover.jpg",
                  "cover_content_type": "image/jpeg",
                  "cover_size_bytes": 1024
                }
                """.trimIndent(),
            ).toManualReleaseDraft()

        assertEquals("draft-1", draft.id)
        assertEquals("Gradient Sync", draft.artist)
        assertEquals("RT-12", draft.catalogNumber)
        assertTrue(draft.completionState?.requiredComplete == true)
        val expectedCoverUrl =
            BuildConfig.VINYL_API_BASE_URL
                .removeSuffix("/api/v1")
                .trimEnd('/') + "/media/manual-release-covers/user-1/draft-1/cover.jpg"
        assertEquals(expectedCoverUrl, draft.coverImageUrl)
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
                      "cover_thumbnail_url": "/media/manual-release-covers/user-1/draft-1/cover.jpg",
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
        assertEquals(expectedCoverUrl, list.items.first().coverThumbnailUrl)
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
    fun manualReleaseFormStateValidatesTrackFieldsBeforeSaveRelease() {
        val state =
            ManualReleaseFormState(
                formData =
                    validManualReleaseFormData().copy(
                        tracklist =
                            listOf(
                                ManualReleaseTrackInput(
                                    title = "Low Ceiling",
                                    duration = "5m",
                                    credits = listOf(ManualReleaseTrackCreditInput(ManualReleaseTrackCreditRole.Remix)),
                                ),
                            ),
                    ),
            )

        assertFalse(state.requiredComplete)
        assertEquals(ManualReleasePrimaryAction.SaveDraft, state.primaryAction)
        assertEquals("Track duration must use m:ss or h:mm:ss.", state.localFieldErrors["tracklist.0.duration"])
        assertEquals("Credit name is required.", state.localFieldErrors["tracklist.0.credits.0.name"])
    }

    @Test
    fun manualReleaseFormStateTracksDirtyFieldsAndCoverValidation() {
        val state =
            ManualReleaseFormState(
                coverUri = "content://covers/draft-1",
                coverContentType = "image/gif",
                coverSizeBytes = 4 * 1024 * 1024,
                coverWidthPx = 500,
                coverHeightPx = 500,
                dirtyFields = setOf("title", "cover"),
                fieldErrors = mapOf("title" to "Backend title error."),
            )

        assertEquals(setOf("title", "cover"), state.dirtyFields)
        assertEquals(ManualReleaseCoverValidationState.TooLarge, state.coverValidationState)
        assertEquals("Backend title error.", state.localFieldErrors["title"])
        assertEquals("Cover image must be 500 KB or smaller.", state.localFieldErrors["cover"])

        val unknownTypeState =
            state.copy(
                coverContentType = null,
                coverSizeBytes = 1024,
            )

        assertEquals(ManualReleaseCoverValidationState.UnknownType, unknownTypeState.coverValidationState)
        assertEquals("Cover image type could not be detected.", unknownTypeState.localFieldErrors["cover"])

        val tooSmallDimensionsState =
            state.copy(
                coverContentType = "image/jpeg",
                coverSizeBytes = 1024,
                coverWidthPx = 99,
                coverHeightPx = 80,
            )

        assertEquals(ManualReleaseCoverValidationState.TooSmallDimensions, tooSmallDimensionsState.coverValidationState)
        assertEquals("Cover image longest side must be at least 100 px.", tooSmallDimensionsState.localFieldErrors["cover"])

        val tooLargeDimensionsState =
            tooSmallDimensionsState.copy(
                coverWidthPx = 1201,
                coverHeightPx = 100,
            )

        assertEquals(ManualReleaseCoverValidationState.TooLargeDimensions, tooLargeDimensionsState.coverValidationState)
        assertEquals("Cover image longest side must be 1200 px or smaller.", tooLargeDimensionsState.localFieldErrors["cover"])
    }
}

private fun validManualReleaseFormData(): ManualReleaseFormData =
    ManualReleaseFormData(
        artists = listOf("Gradient Sync"),
        title = "Night Plates",
        label = "Room Tone",
        format = ManualReleaseFormat.Vinyl,
        vinylSize = ManualReleaseVinylSize.TwelveInch,
        vinylSpeed = ManualReleaseVinylSpeed.ThirtyThree,
        vinylDiscCount = 2,
        genres = listOf("Electronic"),
        styles = listOf("Techno"),
        tracklist = listOf(ManualReleaseTrackInput(title = "Low Ceiling")),
    )
