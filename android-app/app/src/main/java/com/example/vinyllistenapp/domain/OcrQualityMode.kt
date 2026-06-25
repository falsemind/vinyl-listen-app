package com.example.vinyllistenapp.domain

enum class OcrQualityMode(
    val displayName: String,
    val maxInputDimension: Int?,
) {
    FAST("fast", 1280),
    BALANCED("balanced", 2048),
    HIGH_ACCURACY("high-accuracy", null),
}

data class OcrInputSizing(
    val sourceWidth: Int?,
    val sourceHeight: Int?,
    val inputWidth: Int?,
    val inputHeight: Int?,
    val sampleSize: Int,
) {
    val sourceSizeLabel: String
        get() = sizeLabel(sourceWidth, sourceHeight)

    val inputSizeLabel: String
        get() = sizeLabel(inputWidth, inputHeight)

    private fun sizeLabel(
        width: Int?,
        height: Int?,
    ): String =
        if (width != null && height != null && width > 0 && height > 0) {
            "${width}x$height"
        } else {
            "unknown size"
        }
}

fun OcrQualityMode.inputSizing(
    sourceWidth: Int?,
    sourceHeight: Int?,
): OcrInputSizing {
    val sourceMaxDimension = maxOf(sourceWidth ?: 0, sourceHeight ?: 0)
    val sampleSize =
        maxInputDimension
            ?.takeIf { sourceMaxDimension > it }
            ?.let { targetMaxDimension -> sampleSizeFor(sourceMaxDimension, targetMaxDimension) }
            ?: 1
    return OcrInputSizing(
        sourceWidth = sourceWidth,
        sourceHeight = sourceHeight,
        inputWidth = sourceWidth?.takeIf { it > 0 }?.let { it / sampleSize },
        inputHeight = sourceHeight?.takeIf { it > 0 }?.let { it / sampleSize },
        sampleSize = sampleSize,
    )
}

private fun sampleSizeFor(
    sourceMaxDimension: Int,
    targetMaxDimension: Int,
): Int {
    var sampleSize = 1
    while (sourceMaxDimension / sampleSize > targetMaxDimension) {
        sampleSize *= 2
    }
    return sampleSize
}
