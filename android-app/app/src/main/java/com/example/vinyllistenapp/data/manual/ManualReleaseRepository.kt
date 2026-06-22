package com.example.vinyllistenapp.data.manual

import android.content.Context
import android.net.Uri
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.domain.ManualReleaseCompletionState
import com.example.vinyllistenapp.domain.ManualReleaseCoverUploadResult
import com.example.vinyllistenapp.domain.ManualReleaseDraft
import com.example.vinyllistenapp.domain.ManualReleaseDraftList
import com.example.vinyllistenapp.domain.ManualReleaseFormData
import com.example.vinyllistenapp.domain.ManualReleaseFormState
import com.example.vinyllistenapp.domain.ManualReleaseSaveResult

class ManualReleaseRepository(
    private val listDraftsRequest: suspend () -> ManualReleaseDraftList,
    private val getDraftRequest: suspend (String) -> ManualReleaseDraft,
    private val createDraftRequest: suspend (ManualReleaseFormData, ManualReleaseCompletionState?) -> ManualReleaseDraft,
    private val updateDraftRequest: suspend (String, ManualReleaseFormData, ManualReleaseCompletionState?) -> ManualReleaseDraft,
    private val deleteDraftRequest: suspend (String) -> Unit,
    private val saveReleaseRequest: suspend (ManualReleaseFormData?, String?) -> ManualReleaseSaveResult,
    private val uploadCoverRequest: suspend (Context, String, Uri) -> ManualReleaseCoverUploadResult,
) {
    constructor(apiClient: VinylApiClient) : this(
        listDraftsRequest = apiClient::listManualReleaseDrafts,
        getDraftRequest = apiClient::getManualReleaseDraft,
        createDraftRequest = apiClient::createManualReleaseDraft,
        updateDraftRequest = apiClient::updateManualReleaseDraft,
        deleteDraftRequest = apiClient::deleteManualReleaseDraft,
        saveReleaseRequest = apiClient::saveManualRelease,
        uploadCoverRequest = apiClient::uploadManualReleaseDraftCover,
    )

    suspend fun listDrafts(): ManualReleaseDraftList = listDraftsRequest()

    suspend fun getDraft(draftId: String): ManualReleaseDraft = getDraftRequest(draftId)

    suspend fun createDraft(formState: ManualReleaseFormState): ManualReleaseDraft =
        createDraftRequest(formState.formData, formState.completionState())

    suspend fun updateDraft(
        draftId: String,
        formState: ManualReleaseFormState,
    ): ManualReleaseDraft = updateDraftRequest(draftId, formState.formData, formState.completionState())

    suspend fun deleteDraft(draftId: String) {
        deleteDraftRequest(draftId)
    }

    suspend fun saveRelease(formData: ManualReleaseFormData): ManualReleaseSaveResult = saveReleaseRequest(formData, null)

    suspend fun saveDraftAsRelease(draftId: String): ManualReleaseSaveResult = saveReleaseRequest(null, draftId)

    suspend fun uploadCover(
        context: Context,
        draftId: String,
        imageUri: Uri,
    ): ManualReleaseCoverUploadResult = uploadCoverRequest(context, draftId, imageUri)
}
