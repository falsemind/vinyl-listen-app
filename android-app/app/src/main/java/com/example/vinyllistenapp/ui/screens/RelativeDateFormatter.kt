package com.example.vinyllistenapp.ui.screens

import java.time.Clock
import java.time.LocalDate
import java.time.format.DateTimeParseException
import java.time.temporal.ChronoUnit

internal fun relativeLastPlayedLabel(
    dateText: String,
    clock: Clock = Clock.systemDefaultZone(),
): String {
    val playedDate = parseLocalDate(dateText) ?: return dateText
    val today = LocalDate.now(clock)
    val days = ChronoUnit.DAYS.between(playedDate, today).coerceAtLeast(0)
    return when {
        days == 0L -> "Today"
        days < 7L -> "${days}d"
        days < 30L -> "${days / 7L}w"
        days < 365L -> "${days / 30L}m"
        else -> "${days / 365L}y"
    }
}

private fun parseLocalDate(value: String): LocalDate? =
    try {
        LocalDate.parse(value.take(10))
    } catch (_: DateTimeParseException) {
        null
    }
