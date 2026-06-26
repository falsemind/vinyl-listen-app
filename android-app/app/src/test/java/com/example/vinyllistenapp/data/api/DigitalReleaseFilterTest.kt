package com.example.vinyllistenapp.data.api

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DigitalReleaseFilterTest {
    @Test
    fun detectsFileBasedDigitalFormats() {
        assertTrue(isLikelyDigitalReleaseFormat("File, MP3, Album"))
        assertTrue(isLikelyDigitalReleaseFormat("File, WAV"))
        assertTrue(isLikelyDigitalReleaseFormat("FLAC"))
    }

    @Test
    fun keepsPhysicalFormats() {
        assertFalse(isLikelyDigitalReleaseFormat("Vinyl, LP"))
        assertFalse(isLikelyDigitalReleaseFormat("CD, Album"))
        assertFalse(isLikelyDigitalReleaseFormat("Vinyl, 12\", File, MP3"))
    }
}
