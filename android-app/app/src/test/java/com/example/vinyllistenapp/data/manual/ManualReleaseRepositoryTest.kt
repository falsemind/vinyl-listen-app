package com.example.vinyllistenapp.data.manual

import com.example.vinyllistenapp.domain.ManualReleaseCompletionState
import com.example.vinyllistenapp.domain.ManualReleaseCoverUploadResult
import com.example.vinyllistenapp.domain.ManualReleaseDetail
import com.example.vinyllistenapp.domain.ManualReleaseDraft
import com.example.vinyllistenapp.domain.ManualReleaseDraftList
import com.example.vinyllistenapp.domain.ManualReleaseFormData
import com.example.vinyllistenapp.domain.ManualReleaseFormState
import com.example.vinyllistenapp.domain.ManualReleaseFormat
import com.example.vinyllistenapp.domain.ManualReleaseSaveResult
import com.example.vinyllistenapp.domain.ManualReleaseTrackInput
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ManualReleaseRepositoryTest {
    @Test
    fun listDraftsReturnsDraftPage() =
        runBlocking {
            val repository =
                repository(
                    listDrafts = {
                        ManualReleaseDraftList(
                            items = emptyList(),
                            limit = 5,
                            remainingSlots = 3,
                        )
                    },
                )

            val result = repository.listDrafts()

            assertEquals(5, result.limit)
            assertEquals(3, result.remainingSlots)
        }

    @Test
    fun getDraftDelegatesDraftId() =
        runBlocking {
            var capturedDraftId: String? = null
            val repository =
                repository(
                    getDraft = { draftId ->
                        capturedDraftId = draftId
                        draft(id = draftId)
                    },
                )

            val result = repository.getDraft("draft-2")

            assertEquals("draft-2", result.id)
            assertEquals("draft-2", capturedDraftId)
        }

    @Test
    fun createDraftSubmitsFormDataAndCompletionState() =
        runBlocking {
            val formData = ManualReleaseFormData(title = "Partial")
            var capturedFormData: ManualReleaseFormData? = null
            var capturedCompletionState: ManualReleaseCompletionState? = null
            val repository =
                repository(
                    createDraft = { requestFormData, completionState ->
                        capturedFormData = requestFormData
                        capturedCompletionState = completionState
                        draft(formData = requestFormData)
                    },
                )

            val result =
                repository.createDraft(
                    ManualReleaseFormState(
                        formData = formData,
                    ),
                )

            assertEquals("draft-1", result.id)
            assertEquals(formData, capturedFormData)
            assertEquals(false, capturedCompletionState?.requiredComplete)
        }

    @Test
    fun updateDraftSubmitsDraftIdFormDataAndCompletionState() =
        runBlocking {
            val formData = ManualReleaseFormData(title = "Updated")
            var capturedDraftId: String? = null
            var capturedFormData: ManualReleaseFormData? = null
            var capturedCompletionState: ManualReleaseCompletionState? = null
            val repository =
                repository(
                    updateDraft = { draftId, requestFormData, completionState ->
                        capturedDraftId = draftId
                        capturedFormData = requestFormData
                        capturedCompletionState = completionState
                        draft(formData = requestFormData)
                    },
                )

            repository.updateDraft(
                draftId = "draft-1",
                formState = ManualReleaseFormState(formData = formData),
            )

            assertEquals("draft-1", capturedDraftId)
            assertEquals(formData, capturedFormData)
            assertEquals(false, capturedCompletionState?.requiredComplete)
        }

    @Test
    fun deleteDraftDelegatesDraftId() =
        runBlocking {
            var deletedDraftId: String? = null
            val repository =
                repository(
                    deleteDraft = { draftId ->
                        deletedDraftId = draftId
                    },
                )

            repository.deleteDraft("draft-1")

            assertEquals("draft-1", deletedDraftId)
        }

    @Test
    fun saveDraftAsReleaseSendsOnlyDraftId() =
        runBlocking {
            var capturedFormData: ManualReleaseFormData? = ManualReleaseFormData(title = "unexpected")
            var capturedDraftId: String? = null
            val repository =
                repository(
                    saveRelease = { formData, draftId ->
                        capturedFormData = formData
                        capturedDraftId = draftId
                        saveResult()
                    },
                )

            val result = repository.saveDraftAsRelease("draft-1")

            assertEquals("manual-1", result.id)
            assertNull(capturedFormData)
            assertEquals("draft-1", capturedDraftId)
        }

    @Test
    fun saveReleaseSendsOnlyFormData() =
        runBlocking {
            val formData = completeFormData()
            var capturedFormData: ManualReleaseFormData? = null
            var capturedDraftId: String? = "unexpected"
            val repository =
                repository(
                    saveRelease = { requestFormData, draftId ->
                        capturedFormData = requestFormData
                        capturedDraftId = draftId
                        saveResult()
                    },
                )

            repository.saveRelease(formData)

            assertEquals(formData, capturedFormData)
            assertNull(capturedDraftId)
        }

    @Test
    fun getReleaseDelegatesReleaseId() =
        runBlocking {
            var capturedReleaseId: String? = null
            val repository =
                repository(
                    getRelease = { releaseId ->
                        capturedReleaseId = releaseId
                        release(id = releaseId)
                    },
                )

            val result = repository.getRelease("manual-2")

            assertEquals("manual-2", result.id)
            assertEquals("manual-2", capturedReleaseId)
        }

    @Test
    fun updateReleaseSubmitsReleaseIdAndFormData() =
        runBlocking {
            val formData = completeFormData().copy(title = "Updated Night Plates")
            var capturedReleaseId: String? = null
            var capturedFormData: ManualReleaseFormData? = null
            val repository =
                repository(
                    updateRelease = { releaseId, requestFormData ->
                        capturedReleaseId = releaseId
                        capturedFormData = requestFormData
                        release(id = releaseId, formData = requestFormData)
                    },
                )

            val result = repository.updateRelease("manual-1", formData)

            assertEquals("manual-1", result.id)
            assertEquals("Updated Night Plates", result.title)
            assertEquals("manual-1", capturedReleaseId)
            assertEquals(formData, capturedFormData)
        }

    @Test
    fun deleteReleaseCoverDelegatesReleaseId() =
        runBlocking {
            var capturedReleaseId: String? = null
            val repository =
                repository(
                    deleteReleaseCover = { releaseId ->
                        capturedReleaseId = releaseId
                    },
                )

            repository.deleteReleaseCover("manual-1")

            assertEquals("manual-1", capturedReleaseId)
        }

    private fun repository(
        listDrafts: suspend () -> ManualReleaseDraftList = {
            ManualReleaseDraftList(items = emptyList(), limit = 5, remainingSlots = 5)
        },
        getDraft: suspend (String) -> ManualReleaseDraft = { draftId -> draft(id = draftId) },
        createDraft: suspend (ManualReleaseFormData, ManualReleaseCompletionState?) -> ManualReleaseDraft = { formData, _ ->
            draft(formData = formData)
        },
        updateDraft: suspend (String, ManualReleaseFormData, ManualReleaseCompletionState?) -> ManualReleaseDraft = { _, formData, _ ->
            draft(formData = formData)
        },
        deleteDraft: suspend (String) -> Unit = {},
        saveRelease: suspend (ManualReleaseFormData?, String?) -> ManualReleaseSaveResult = { _, _ -> saveResult() },
        uploadCover: suspend (
            android.content.Context,
            String,
            android.net.Uri,
        ) -> ManualReleaseCoverUploadResult = { _, _, _ ->
            ManualReleaseCoverUploadResult(
                contentType = "image/jpeg",
                sizeBytes = 1,
            )
        },
        getRelease: suspend (String) -> ManualReleaseDetail = { releaseId -> release(id = releaseId) },
        updateRelease: suspend (String, ManualReleaseFormData) -> ManualReleaseDetail = { releaseId, formData ->
            release(id = releaseId, formData = formData)
        },
        uploadReleaseCover: suspend (
            android.content.Context,
            String,
            android.net.Uri,
        ) -> ManualReleaseCoverUploadResult = { _, _, _ ->
            ManualReleaseCoverUploadResult(
                contentType = "image/jpeg",
                sizeBytes = 1,
            )
        },
        deleteReleaseCover: suspend (String) -> Unit = {},
    ): ManualReleaseRepository =
        ManualReleaseRepository(
            listDraftsRequest = listDrafts,
            getDraftRequest = getDraft,
            createDraftRequest = createDraft,
            updateDraftRequest = updateDraft,
            deleteDraftRequest = deleteDraft,
            saveReleaseRequest = saveRelease,
            uploadCoverRequest = uploadCover,
            getReleaseRequest = getRelease,
            updateReleaseRequest = updateRelease,
            uploadReleaseCoverRequest = uploadReleaseCover,
            deleteReleaseCoverRequest = deleteReleaseCover,
        )

    private fun completeFormData(): ManualReleaseFormData =
        ManualReleaseFormData(
            artists = listOf("Gradient Sync"),
            title = "Night Plates",
            label = "Room Tone",
            format = ManualReleaseFormat.Cd,
            genres = listOf("Rock"),
            tracklist = listOf(ManualReleaseTrackInput(title = "Track")),
        )

    private fun draft(
        formData: ManualReleaseFormData = ManualReleaseFormData(title = "Draft"),
        id: String = "draft-1",
    ): ManualReleaseDraft =
        ManualReleaseDraft(
            id = id,
            artist = formData.artists.firstOrNull(),
            title = formData.title,
            year = formData.year,
            label = formData.label,
            catalogNumber = formData.catalogNumber,
            format = formData.format?.wireValue,
            coverThumbnailUrl = null,
            completionState = ManualReleaseCompletionState(requiredComplete = false),
            updatedAt = "2026-06-21T12:00:00Z",
            formData = formData,
            coverImageUrl = null,
            coverContentType = null,
            coverSizeBytes = null,
            createdAt = "2026-06-21T12:00:00Z",
        )

    private fun saveResult(): ManualReleaseSaveResult =
        ManualReleaseSaveResult(
            id = "manual-1",
            title = "Night Plates",
            artist = "Gradient Sync",
            inCollection = true,
        )

    private fun release(
        formData: ManualReleaseFormData = completeFormData(),
        id: String = "manual-1",
    ): ManualReleaseDetail =
        ManualReleaseDetail(
            id = id,
            title = formData.title.orEmpty(),
            artist = formData.artists.firstOrNull().orEmpty(),
            inCollection = true,
            formData = formData,
            coverImageUrl = "https://example.test/manual-1.jpg",
            coverThumbnailUrl = "https://example.test/manual-1-thumb.jpg",
            coverContentType = "image/jpeg",
            coverSizeBytes = 2048,
            createdAt = "2026-06-21T12:00:00Z",
            updatedAt = "2026-06-21T12:00:00Z",
        )
}
