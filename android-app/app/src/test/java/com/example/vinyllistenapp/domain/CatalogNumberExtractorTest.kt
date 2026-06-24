package com.example.vinyllistenapp.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CatalogNumberExtractorTest {
    @Test
    fun extractsCatalogNumberNearCatalogKeyword() {
        val candidates = CatalogNumberExtractor.extract(listOf("Cat No ABC-123", "Stereo LP"))

        assertEquals("ABC-123", candidates.first().value)
        assertTrue(candidates.first().reasons.contains("near catalog keyword"))
    }

    @Test
    fun ranksRepeatedCatalogNumberHigher() {
        val candidates =
            CatalogNumberExtractor.extract(
                listOf(
                    "ABC-123",
                    "ABC-123",
                    "XYZ-9",
                ),
            )

        assertEquals("ABC-123", candidates.first().value)
        assertTrue(candidates.first().reasons.contains("appears more than once"))
    }

    @Test
    fun rejectsBarcodeOnlyAndYearOnlyText() {
        val candidates =
            CatalogNumberExtractor.extract(
                listOf(
                    "0123456789012",
                    "2024",
                    "1999",
                ),
            )

        assertTrue(candidates.isEmpty())
    }

    @Test
    fun keepsMixedLetterNumberIdentifierFromNoisyText() {
        val candidates =
            CatalogNumberExtractor.extract(
                listOf(
                    "Manufactured by Example Records",
                    "For licensing contact label@example.com",
                    "Matrix / Runout: LBL 2049-A",
                ),
            )

        assertEquals("LBL 2049-A", candidates.first().value)
        assertTrue(candidates.first().score > 0)
    }

    @Test
    fun repairsOcrLetterOInDigitLikeCatalogSegments() {
        val separatedCandidate = CatalogNumberExtractor.extract(listOf("DAT o88")).first()
        val joinedCandidate = CatalogNumberExtractor.extract(listOf("DATO88")).first()
        val suffixedCandidate = CatalogNumberExtractor.extract(listOf("RUPLDN O02LP")).first()

        assertEquals("DAT 088", separatedCandidate.value)
        assertEquals("DAT088", joinedCandidate.value)
        assertEquals("RUPLDN 002LP", suffixedCandidate.value)
    }

    @Test
    fun doesNotRepairLetterOInNormalWords() {
        val candidates = CatalogNumberExtractor.extract(listOf("OASIS 001"))

        assertEquals("OASIS 001", candidates.first().value)
    }

    @Test
    fun limitsCandidateCount() {
        val candidates =
            CatalogNumberExtractor.extract(
                lines =
                    listOf(
                        "AAA-111",
                        "BBB-222",
                        "CCC-333",
                    ),
                limit = 2,
            )

        assertEquals(2, candidates.size)
        assertFalse(candidates.any { it.value == "CCC-333" })
    }
}
