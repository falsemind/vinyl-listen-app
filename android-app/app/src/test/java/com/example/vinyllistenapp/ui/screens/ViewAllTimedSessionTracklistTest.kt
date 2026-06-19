package com.example.vinyllistenapp.ui.screens

import com.example.vinyllistenapp.domain.ListeningSession
import com.example.vinyllistenapp.domain.SessionTrack
import org.junit.Assert.assertEquals
import org.junit.Test

class ViewAllTimedSessionTracklistTest {
    @Test
    fun ordersTracksByPlayedTimeAndUsesTrackArtists() {
        val text =
            timedSessionTracklistText(
                listOf(
                    session(
                        playedAt = "2026-05-10T23:10:00Z",
                        artist = "Various",
                        title = "Tidal Waves",
                        year = 2023,
                        label = "Future Retro London",
                        catalogNumber = "FRL001",
                        tracks =
                            listOf(
                                SessionTrack(position = "A2", artist = "Tim Reaper", title = "Second", sequence = 2),
                                SessionTrack(
                                    position = "A1",
                                    artist = "Pixl & Tim Reaper",
                                    title = "Tidal Waves",
                                    sequence = 1,
                                ),
                            ),
                    ),
                    session(
                        playedAt = "2026-05-10T22:55:00Z",
                        artist = "Various",
                        title = "Opening Plate",
                        tracks =
                            listOf(
                                SessionTrack(position = "B1", artist = "Equinox & Tim Reaper", title = "Burger Sauce"),
                            ),
                    ),
                ),
            )

        assertEquals(
            listOf(
                "1. Equinox & Tim Reaper - Burger Sauce",
                "2. Pixl & Tim Reaper - Tidal Waves / 2023 / Future Retro London / FRL001",
                "3. Tim Reaper - Second / 2023 / Future Retro London / FRL001",
            ).joinToString("\n"),
            text,
        )
    }

    private fun session(
        playedAt: String,
        artist: String,
        title: String,
        year: Int? = null,
        label: String? = null,
        catalogNumber: String? = null,
        tracks: List<SessionTrack>,
    ): ListeningSession =
        ListeningSession(
            releaseId = title,
            artist = artist,
            title = title,
            year = year,
            label = label,
            catalogNumber = catalogNumber,
            playedAt = playedAt,
            mood = "Focused",
            rating = 5,
            tracks = tracks,
        )
}
