package com.example.vinyllistenapp.domain

object ManualReleaseLimits {
    const val MAX_DRAFTS = 5
    const val MAX_COVER_BYTES = 3 * 1024 * 1024
    const val MAX_ARTISTS = 20
    const val MAX_TRACKS = 100
    const val MAX_VINYL_DISC_COUNT = 6
    const val ARTIST_NAME_MAX_LENGTH = 200
    const val TITLE_MAX_LENGTH = 200
    const val LABEL_MAX_LENGTH = 200
    const val CATALOG_NUMBER_MAX_LENGTH = 80
    const val TRACK_TITLE_MAX_LENGTH = 200
    const val TRACK_POSITION_MAX_LENGTH = 16
    const val TRACK_DURATION_MAX_LENGTH = 8
    const val TRACK_CREDIT_NAME_MAX_LENGTH = 200

    val SUPPORTED_COVER_CONTENT_TYPES = setOf("image/jpeg", "image/png", "image/webp")
}

enum class ManualReleaseFormat(
    val wireValue: String,
) {
    Vinyl("Vinyl"),
    Cd("CD"),
    Tape("Tape"),
    Other("Other"),
    ;

    companion object {
        fun fromWireValue(value: String?): ManualReleaseFormat? = entries.firstOrNull { it.wireValue == value }
    }
}

enum class ManualReleaseVinylSize(
    val wireValue: String,
) {
    SevenInch("7"),
    TenInch("10"),
    TwelveInch("12"),
    Other("Other"),
    ;

    companion object {
        fun fromWireValue(value: String?): ManualReleaseVinylSize? = entries.firstOrNull { it.wireValue == value }
    }
}

enum class ManualReleaseVinylSpeed(
    val wireValue: String,
) {
    ThirtyThree("33 1/3"),
    FortyFive("45"),
    SeventyEight("78"),
    Other("Other"),
    ;

    companion object {
        fun fromWireValue(value: String?): ManualReleaseVinylSpeed? = entries.firstOrNull { it.wireValue == value }
    }
}

enum class ManualReleaseTrackCreditRole(
    val wireValue: String,
) {
    Featuring("Featuring"),
    Remix("Remix"),
    Producer("Producer"),
    WrittenBy("Written-By"),
    Other("Other"),
    ;

    companion object {
        fun fromWireValue(value: String?): ManualReleaseTrackCreditRole? = entries.firstOrNull { it.wireValue == value }
    }
}

data class ManualReleaseTrackCreditInput(
    val role: ManualReleaseTrackCreditRole,
    val name: String? = null,
)

data class ManualReleaseTrackInput(
    val title: String? = null,
    val position: String? = null,
    val duration: String? = null,
    val credits: List<ManualReleaseTrackCreditInput> = emptyList(),
)

data class ManualReleaseFormData(
    val artists: List<String> = emptyList(),
    val title: String? = null,
    val label: String? = null,
    val catalogNumber: String? = null,
    val barcode: String? = null,
    val format: ManualReleaseFormat? = null,
    val vinylSize: ManualReleaseVinylSize? = null,
    val vinylSpeed: ManualReleaseVinylSpeed? = null,
    val vinylDiscCount: Int? = null,
    val genres: List<String> = emptyList(),
    val styles: List<String> = emptyList(),
    val tracklist: List<ManualReleaseTrackInput> = emptyList(),
)

data class ManualReleaseCompletionState(
    val requiredComplete: Boolean = false,
)

data class ManualReleaseDraftSummary(
    val id: String,
    val artist: String?,
    val title: String?,
    val label: String?,
    val catalogNumber: String?,
    val format: String?,
    val coverThumbnailUrl: String?,
    val completionState: ManualReleaseCompletionState?,
    val updatedAt: String,
)

data class ManualReleaseDraft(
    val id: String,
    val artist: String?,
    val title: String?,
    val label: String?,
    val catalogNumber: String?,
    val format: String?,
    val coverThumbnailUrl: String?,
    val completionState: ManualReleaseCompletionState?,
    val updatedAt: String,
    val formData: ManualReleaseFormData,
    val coverImageUrl: String?,
    val coverContentType: String?,
    val coverSizeBytes: Int?,
    val createdAt: String,
)

data class ManualReleaseDraftList(
    val items: List<ManualReleaseDraftSummary>,
    val limit: Int,
    val remainingSlots: Int,
)

data class ManualReleaseSaveResult(
    val id: String,
    val title: String,
    val artist: String,
    val inCollection: Boolean,
)

data class ManualReleaseCoverUploadResult(
    val contentType: String,
    val sizeBytes: Int,
)

data class ManualReleaseFormState(
    val formData: ManualReleaseFormData = ManualReleaseFormData(),
    val coverUri: String? = null,
    val coverContentType: String? = null,
    val coverSizeBytes: Int? = null,
    val dirtyFields: Set<String> = emptySet(),
    val fieldErrors: Map<String, String> = emptyMap(),
) {
    val localFieldErrors: Map<String, String>
        get() =
            buildMap {
                if (formData.artists.size > ManualReleaseLimits.MAX_ARTISTS) {
                    put("artists", "Use ${ManualReleaseLimits.MAX_ARTISTS} artists or fewer.")
                }
                if ((formData.title?.length ?: 0) > ManualReleaseLimits.TITLE_MAX_LENGTH) {
                    put("title", "Title must be ${ManualReleaseLimits.TITLE_MAX_LENGTH} characters or fewer.")
                }
                if ((formData.label?.length ?: 0) > ManualReleaseLimits.LABEL_MAX_LENGTH) {
                    put("label", "Label must be ${ManualReleaseLimits.LABEL_MAX_LENGTH} characters or fewer.")
                }
                if ((formData.catalogNumber?.length ?: 0) > ManualReleaseLimits.CATALOG_NUMBER_MAX_LENGTH) {
                    put(
                        "catalog_number",
                        "Catalog number must be ${ManualReleaseLimits.CATALOG_NUMBER_MAX_LENGTH} characters or fewer.",
                    )
                }
                if (formData.tracklist.size > ManualReleaseLimits.MAX_TRACKS) {
                    put("tracklist", "Use ${ManualReleaseLimits.MAX_TRACKS} tracks or fewer.")
                }
                formData.vinylDiscCount?.let { discCount ->
                    if (discCount !in 1..ManualReleaseLimits.MAX_VINYL_DISC_COUNT) {
                        put("vinyl_disc_count", "Vinyl disc count must be between 1 and 6.")
                    }
                }
                if (coverValidationState == ManualReleaseCoverValidationState.UnknownType) {
                    put("cover", "Cover image type could not be detected.")
                }
                if (coverValidationState == ManualReleaseCoverValidationState.UnsupportedType) {
                    put("cover", "Cover image must be JPEG, PNG, or WebP.")
                }
                if (coverValidationState == ManualReleaseCoverValidationState.TooLarge) {
                    put("cover", "Cover image must be 3 MB or smaller.")
                }
            } + fieldErrors

    val coverValidationState: ManualReleaseCoverValidationState
        get() =
            when {
                coverUri == null -> ManualReleaseCoverValidationState.Empty
                coverContentType == null -> ManualReleaseCoverValidationState.UnknownType
                coverSizeBytes != null && coverSizeBytes > ManualReleaseLimits.MAX_COVER_BYTES ->
                    ManualReleaseCoverValidationState.TooLarge
                coverContentType.lowercase() !in ManualReleaseLimits.SUPPORTED_COVER_CONTENT_TYPES ->
                    ManualReleaseCoverValidationState.UnsupportedType
                else -> ManualReleaseCoverValidationState.Valid
            }

    val hasAnyInput: Boolean
        get() =
            formData.artists.any { it.isNotBlank() } ||
                !formData.title.isNullOrBlank() ||
                !formData.label.isNullOrBlank() ||
                !formData.catalogNumber.isNullOrBlank() ||
                !formData.barcode.isNullOrBlank() ||
                formData.format != null ||
                formData.vinylSize != null ||
                formData.vinylSpeed != null ||
                formData.vinylDiscCount != null ||
                formData.genres.any { it.isNotBlank() } ||
                formData.styles.any { it.isNotBlank() } ||
                formData.tracklist.any { !it.title.isNullOrBlank() || !it.position.isNullOrBlank() } ||
                coverUri != null

    val requiredComplete: Boolean
        get() =
            formData.artists.any { it.isNotBlank() } &&
                !formData.title.isNullOrBlank() &&
                !formData.label.isNullOrBlank() &&
                formData.format != null &&
                formData.genres.any { it.isNotBlank() } &&
                formData.tracklist.any { !it.title.isNullOrBlank() } &&
                (formData.format != ManualReleaseFormat.Vinyl || hasRequiredVinylDetails) &&
                (!formData.genres.contains("Electronic") || formData.styles.any { it.isNotBlank() }) &&
                localFieldErrors.isEmpty()

    val primaryAction: ManualReleasePrimaryAction
        get() =
            when {
                requiredComplete -> ManualReleasePrimaryAction.SaveRelease
                hasAnyInput -> ManualReleasePrimaryAction.SaveDraft
                else -> ManualReleasePrimaryAction.DisabledSave
            }

    fun completionState(): ManualReleaseCompletionState = ManualReleaseCompletionState(requiredComplete = requiredComplete)

    private val hasRequiredVinylDetails: Boolean
        get() = formData.vinylSize != null && formData.vinylSpeed != null && formData.vinylDiscCount != null
}

enum class ManualReleasePrimaryAction {
    DisabledSave,
    SaveDraft,
    SaveRelease,
}

enum class ManualReleaseCoverValidationState {
    Empty,
    Valid,
    UnknownType,
    UnsupportedType,
    TooLarge,
}
