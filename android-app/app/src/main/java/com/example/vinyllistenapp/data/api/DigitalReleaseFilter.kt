package com.example.vinyllistenapp.data.api

private val digitalReleaseFormatTokens =
    setOf(
        "aac",
        "aiff",
        "alac",
        "ape",
        "dsd",
        "file",
        "flac",
        "m4a",
        "mp3",
        "ogg",
        "wav",
        "wma",
    )

private val physicalReleaseFormatTokens =
    setOf(
        "7",
        "10",
        "12",
        "acetate",
        "bluray",
        "blu",
        "cassette",
        "cd",
        "cdr",
        "dvd",
        "flexi",
        "lathe",
        "lp",
        "minidisc",
        "sacd",
        "shellac",
        "vinyl",
    )

internal fun isLikelyDigitalReleaseFormat(format: String?): Boolean {
    val tokens = format.releaseFormatTokens()
    if (tokens.isEmpty()) return false

    val hasDigitalFormat = tokens.any { it in digitalReleaseFormatTokens }
    val hasPhysicalFormat = tokens.any { it in physicalReleaseFormatTokens }
    return hasDigitalFormat && !hasPhysicalFormat
}

private fun String?.releaseFormatTokens(): Set<String> =
    this
        ?.lowercase()
        ?.split(Regex("[^a-z0-9]+"))
        ?.filterTo(mutableSetOf()) { it.isNotBlank() }
        .orEmpty()
