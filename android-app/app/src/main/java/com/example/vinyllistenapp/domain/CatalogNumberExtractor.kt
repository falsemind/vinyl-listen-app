package com.example.vinyllistenapp.domain

data class CatalogNumberCandidate(
    val value: String,
    val score: Int,
    val matchedLine: String,
    val reasons: List<String>,
)

object CatalogNumberExtractor {
    private val candidateTextPattern = Regex("[A-Z0-9]+(?:[ ./-][A-Z0-9]+){0,3}")
    private val catalogShapePatterns =
        listOf(
            Regex("[A-Z]{1,6}[- ]?\\d{2,7}[A-Z]?"),
            Regex("[A-Z]{1,4}\\d{1,5}[- ][A-Z0-9]{1,6}"),
            Regex("\\d{1,4}[- ][A-Z]{1,5}[- ]?\\d{1,7}"),
            Regex("[A-Z0-9]{2,8}-[A-Z0-9]{1,8}(?:-[A-Z0-9]{1,6})?"),
        )
    private val catalogContextKeywords =
        listOf("CAT", "CATALOG", "CATALOGUE", "CAT NO", "CAT.", "NO.", "MATRIX", "LABEL")
    private val joinedPrefixAndDigitLikeSuffixPattern = Regex("([A-Z]{2,})(O[0-9]+)$")
    private val joinedPrefixAndSuffixedNumberPattern = Regex("([A-Z]{2,})O([0-9]{2,}[A-Z]{0,3})$")
    private val leadingDigitLikeOcrPattern = Regex("^O(?=[0-9])")

    fun extract(
        lines: List<String>,
        limit: Int = 5,
    ): List<CatalogNumberCandidate> {
        val rawCandidates =
            lines.flatMap { line ->
                val normalizedLine = line.uppercase()
                candidateTextPattern
                    .findAll(normalizedLine)
                    .mapNotNull { match -> buildCandidate(match.value, line, normalizedLine) }
                    .toList()
            }
        val countsByKey = rawCandidates.groupingBy { it.key }.eachCount()

        return rawCandidates
            .map { candidate ->
                val duplicateBoost = if ((countsByKey[candidate.key] ?: 0) > 1) 15 else 0
                candidate.toPublicCandidate(duplicateBoost = duplicateBoost)
            }.groupBy { normalizeCandidateKey(it.value) }
            .map { (_, candidates) -> candidates.maxBy { it.score } }
            .sortedWith(compareByDescending<CatalogNumberCandidate> { it.score }.thenBy { it.value })
            .take(limit)
    }

    private fun buildCandidate(
        rawValue: String,
        originalLine: String,
        normalizedLine: String,
    ): InternalCatalogCandidate? {
        val value = normalizeCandidateValue(rawValue)
        val key = normalizeCandidateKey(value)
        if (!isPlausibleCandidate(value, key)) return null

        val reasons = mutableListOf<String>()
        var score = 0

        if (catalogShapePatterns.any { it.matches(value) || it.matches(key) }) {
            score += 30
            reasons += "catalog-shaped"
        }
        if (key.length in 4..16) {
            score += 20
            reasons += "plausible length"
        }
        if (key.any(Char::isLetter) && key.any(Char::isDigit)) {
            score += 25
            reasons += "letters and numbers"
        }
        if (value.any { it == '-' || it == '/' || it == '.' || it == ' ' }) {
            score += 10
            reasons += "identifier separator"
        }
        if (catalogContextKeywords.any { normalizedLine.contains(it) }) {
            score += 15
            reasons += "near catalog keyword"
        }

        return InternalCatalogCandidate(
            value = value,
            key = key,
            matchedLine = originalLine,
            baseScore = score,
            reasons = reasons,
        )
    }

    private fun isPlausibleCandidate(
        value: String,
        key: String,
    ): Boolean {
        if (key.length !in 4..20) return false
        if (!key.any(Char::isLetter) || !key.any(Char::isDigit)) return false
        if (key.all(Char::isDigit)) return false
        if (key.matches(Regex("(19|20)\\d{2}"))) return false
        if (key.length in 8..14 && key.all(Char::isDigit)) return false
        if (value in nonCatalogTokens) return false
        return true
    }

    private fun normalizeCandidateValue(value: String): String =
        value
            .uppercase()
            .trim(' ', '.', ',', ':', ';', '#')
            .replace(Regex("^(CAT(?:ALOG(?:UE)?)?(?: NO)?|CAT\\.?|NO\\.?)\\s+"), "")
            .replace(Regex("\\s+"), " ")
            .repairLikelyCatalogDigitOcr()

    private fun normalizeCandidateKey(value: String): String = value.filter(Char::isLetterOrDigit)

    private fun String.repairLikelyCatalogDigitOcr(): String =
        split(" ").joinToString(" ") { segment ->
            segment
                .split("-")
                .joinToString("-") { part ->
                    when {
                        part.any(Char::isDigit) && part.all { it == 'O' || it.isDigit() } -> part.replace('O', '0')
                        else -> {
                            val leadingRepaired = part.replace(leadingDigitLikeOcrPattern, "0")
                            val suffixedRepaired =
                                leadingRepaired.replace(joinedPrefixAndSuffixedNumberPattern) { match ->
                                    match.groupValues[1] + "0" + match.groupValues[2]
                                }
                            suffixedRepaired.replace(joinedPrefixAndDigitLikeSuffixPattern) { match ->
                                match.groupValues[1] + match.groupValues[2].replace('O', '0')
                            }
                        }
                    }
                }
        }

    private data class InternalCatalogCandidate(
        val value: String,
        val key: String,
        val matchedLine: String,
        val baseScore: Int,
        val reasons: List<String>,
    ) {
        fun toPublicCandidate(duplicateBoost: Int): CatalogNumberCandidate {
            val duplicateReasons = if (duplicateBoost > 0) listOf("appears more than once") else emptyList()
            return CatalogNumberCandidate(
                value = value,
                score = baseScore + duplicateBoost,
                matchedLine = matchedLine,
                reasons = reasons + duplicateReasons,
            )
        }
    }
}

private val nonCatalogTokens =
    setOf(
        "SIDE A",
        "SIDE B",
        "SIDE 1",
        "SIDE 2",
        "STEREO",
        "MONO",
        "VINYL",
    )
