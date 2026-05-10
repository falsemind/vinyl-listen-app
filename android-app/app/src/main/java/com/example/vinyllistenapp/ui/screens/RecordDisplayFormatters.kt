package com.example.vinyllistenapp.ui.screens

internal fun matchCatalogNumber(
    releaseId: String,
    index: Int,
): String =
    when (releaseId) {
        "release-001" -> "AS-9203"
        "release-002" -> "PLUTO 001LP"
        "release-003" -> "EPC 26044"
        else -> "CAT-${index + 1}"
    }
