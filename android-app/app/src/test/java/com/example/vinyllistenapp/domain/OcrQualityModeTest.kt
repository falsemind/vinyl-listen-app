package com.example.vinyllistenapp.domain

import org.junit.Assert.assertEquals
import org.junit.Test

class OcrQualityModeTest {
    @Test
    fun fastModeDownsamplesLargeImagesMoreAggressively() {
        val sizing = OcrQualityMode.FAST.inputSizing(sourceWidth = 4032, sourceHeight = 3024)

        assertEquals(4, sizing.sampleSize)
        assertEquals(1008, sizing.inputWidth)
        assertEquals(756, sizing.inputHeight)
        assertEquals("4032x3024", sizing.sourceSizeLabel)
        assertEquals("1008x756", sizing.inputSizeLabel)
    }

    @Test
    fun balancedModeKeepsModerateInputSize() {
        val sizing = OcrQualityMode.BALANCED.inputSizing(sourceWidth = 4032, sourceHeight = 3024)

        assertEquals(2, sizing.sampleSize)
        assertEquals(2016, sizing.inputWidth)
        assertEquals(1512, sizing.inputHeight)
    }

    @Test
    fun highAccuracyModeKeepsOriginalSize() {
        val sizing = OcrQualityMode.HIGH_ACCURACY.inputSizing(sourceWidth = 4032, sourceHeight = 3024)

        assertEquals(1, sizing.sampleSize)
        assertEquals(4032, sizing.inputWidth)
        assertEquals(3024, sizing.inputHeight)
    }

    @Test
    fun unknownSourceSizeKeepsUnknownLabels() {
        val sizing = OcrQualityMode.BALANCED.inputSizing(sourceWidth = null, sourceHeight = null)

        assertEquals(1, sizing.sampleSize)
        assertEquals("unknown size", sizing.sourceSizeLabel)
        assertEquals("unknown size", sizing.inputSizeLabel)
    }
}
