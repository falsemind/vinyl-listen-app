package com.example.vinyllistenapp.navigation

import com.example.vinyllistenapp.data.api.TextIdentifyJobInput
import com.example.vinyllistenapp.domain.MatchCandidate
import com.example.vinyllistenapp.ui.screens.AiInsightsScreenState
import com.example.vinyllistenapp.ui.screens.ChatMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.launch
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class VinylNavHostStateTest {
    @Test
    fun matchCandidatesRoundTripThroughSavedStatePayload() {
        val candidates =
            listOf(
                MatchCandidate(
                    releaseId = "release-123",
                    discogsReleaseId = 555123,
                    artist = "Artist",
                    title = "Title",
                    label = "Label",
                    confidence = 88,
                    year = 2026,
                    catalogNumber = "CAT001",
                    barcode = "1234567890123",
                    coverImageUrl = "https://example.com/cover.jpg",
                    format = "Vinyl, LP",
                    matchSource = "local",
                    matchedOn = listOf("local_lookup", "title"),
                ),
            )

        val restored = decodeMatchCandidatesFromSavedState(encodeMatchCandidatesForSavedState(candidates))

        assertEquals(candidates, restored)
    }

    @Test
    fun emptyMatchCandidatePayloadDoesNotRestoreMockCandidates() {
        val restored = decodeMatchCandidatesFromSavedState(emptyList())

        assertTrue(restored.isEmpty())
    }

    @Test
    fun textIdentifyInputRoundTripThroughSavedStatePayload() {
        val input =
            TextIdentifyJobInput(
                lines = listOf("CAT No: SW038", "Nebula"),
                selectedCatalogNumber = "SW038",
            )

        val restored = decodeTextIdentifyInputFromSavedState(encodeTextIdentifyInputForSavedState(input))

        assertEquals(input, restored)
    }

    @Test
    fun textIdentifyInputSavedStateCapsOversizedPayload() {
        val input =
            TextIdentifyJobInput(
                lines = List(90) { index -> "  ${index.toString().padStart(2, '0')}-${"A".repeat(300)}  " },
                selectedCatalogNumber = "  ${"C".repeat(140)}  ",
                selectedBarcode = "  ${"1".repeat(48)}  ",
            )

        val restored = decodeTextIdentifyInputFromSavedState(encodeTextIdentifyInputForSavedState(input))

        checkNotNull(restored)
        assertTrue(restored.lines.size <= 80)
        assertTrue(restored.lines.all { line -> line.length <= 240 })
        assertTrue(restored.lines.sumOf { line -> line.length } <= 4_000)
        assertEquals("C".repeat(100), restored.selectedCatalogNumber)
        assertEquals("1".repeat(32), restored.selectedBarcode)
    }

    @Test
    fun aiInsightsStateResetClearsAccountScopedChatState() {
        val state = AiInsightsScreenState()
        state.messages.clear()
        state.messages.add(ChatMessage.User("What did I play yesterday?"))
        state.messages.add(ChatMessage.Assistant("You played deleted data."))
        state.inputValue = "draft prompt"
        state.isLoadingHistory = true
        state.hasLoadedHistory = true
        state.isTyping = true
        state.isClearingHistory = true
        state.isExportingHistory = true
        state.showClearConfirmation = true
        state.shouldFocusLoadedHistory = true
        state.conversationId = "conversation-old"

        state.resetForAccountDataReset()

        assertEquals(1, state.messages.size)
        assertTrue(state.messages.single() is ChatMessage.Assistant)
        assertEquals("Ask about your listening habits, collection patterns, moods, styles, or records.", state.messages.single().text)
        assertEquals("", state.inputValue)
        assertFalse(state.isLoadingHistory)
        assertFalse(state.hasLoadedHistory)
        assertFalse(state.isTyping)
        assertFalse(state.isClearingHistory)
        assertFalse(state.isExportingHistory)
        assertFalse(state.showClearConfirmation)
        assertFalse(state.shouldFocusLoadedHistory)
        assertEquals(null, state.conversationId)
    }

    @Test
    fun accountDataResetCancelsAccountScopedRequestsBeforeClearingChatState() {
        val state = AiInsightsScreenState()
        state.messages.clear()
        state.messages.add(ChatMessage.User("What did I play yesterday?"))
        state.conversationId = "conversation-before-reset"
        state.isTyping = true

        val requestScope = CoroutineScope(SupervisorJob())
        val inFlightRequest = requestScope.launch { awaitCancellation() }
        var scopeResetCount = 0
        var requestWasCancelledBeforeScopeReset = false

        resetAccountScopedRequestsAfterAccountDataReset(
            state = state,
            requestScope = requestScope,
            onRequestScopeReset = {
                scopeResetCount += 1
                requestWasCancelledBeforeScopeReset = inFlightRequest.isCancelled
            },
        )

        assertEquals(1, scopeResetCount)
        assertTrue(requestWasCancelledBeforeScopeReset)
        assertTrue(inFlightRequest.isCancelled)
        assertEquals(1, state.messages.size)
        assertTrue(state.messages.single() is ChatMessage.Assistant)
        assertEquals(null, state.conversationId)
        assertFalse(state.isTyping)
    }

    @Test
    fun aiInsightsRouteIsPortraitLocked() {
        assertTrue(VinylRoutes.AI_INSIGHTS.isPortraitLockedOverflowRoute())
    }

    @Test
    fun recordDetailRouteIsPortraitLocked() {
        assertTrue(VinylRoutes.RECORD_DETAIL_PATTERN.isPortraitLockedOverflowRoute())
    }

    @Test
    fun analyticsDrilldownRoutePatternsUseExpectedArguments() {
        assertEquals("analytics_month_sessions/{month}", VinylRoutes.ANALYTICS_MONTH_SESSIONS_PATTERN)
        assertEquals("analytics_rating_records/{rating}", VinylRoutes.ANALYTICS_RATING_RECORDS_PATTERN)
        assertEquals("analytics_mood_records/{mood}", VinylRoutes.ANALYTICS_MOOD_RECORDS_PATTERN)
        assertEquals("analytics_style_records/{style}", VinylRoutes.ANALYTICS_STYLE_RECORDS_PATTERN)
    }

    @Test
    fun editSessionRoutePatternUsesExpectedArgument() {
        assertEquals("session_edit/{sessionId}", VinylRoutes.SESSION_EDIT_PATTERN)
    }

    @Test
    fun collectionRouteUsesExpectedPath() {
        assertEquals("collection", VinylRoutes.COLLECTION)
    }

    @Test
    fun collectionManualSearchRouteUsesExpectedPath() {
        assertEquals("collection_manual_search", VinylRoutes.COLLECTION_MANUAL_SEARCH)
    }

    @Test
    fun manualSearchRoutesExposeCatalogQueryArgument() {
        assertEquals("manual_search?barcode={barcode}&catalog={catalog}", VinylRoutes.MANUAL_SEARCH_PATTERN)
        assertEquals("collection_manual_search?catalog={catalog}", VinylRoutes.COLLECTION_MANUAL_SEARCH_PATTERN)
    }

    @Test
    fun identifyRoutesCarryCollectionAddFlowMode() {
        assertEquals("capture_record?flowMode=collection_add", VinylRoutes.captureRecord(VinylRoutes.FLOW_MODE_COLLECTION_ADD))
        assertEquals("processing?imageUri=&flowMode=collection_add", VinylRoutes.textProcessing(VinylRoutes.FLOW_MODE_COLLECTION_ADD))
        assertEquals(
            "match_confirmation?flowMode=collection_add",
            VinylRoutes.matchConfirmation(VinylRoutes.FLOW_MODE_COLLECTION_ADD),
        )
    }

    @Test
    fun editSessionRouteIsPortraitLocked() {
        assertTrue(VinylRoutes.SESSION_EDIT_PATTERN.isPortraitLockedOverflowRoute())
    }

    @Test
    fun collectionManualSearchRouteIsPortraitLocked() {
        assertTrue(VinylRoutes.COLLECTION_MANUAL_SEARCH.isPortraitLockedOverflowRoute())
    }

    @Test
    fun analyticsDrilldownRoutesDoNotLockPortrait() {
        assertFalse(VinylRoutes.ANALYTICS_MONTH_SESSIONS_PATTERN.isPortraitLockedOverflowRoute())
        assertFalse(VinylRoutes.ANALYTICS_RATING_RECORDS_PATTERN.isPortraitLockedOverflowRoute())
        assertFalse(VinylRoutes.ANALYTICS_MOOD_RECORDS_PATTERN.isPortraitLockedOverflowRoute())
        assertFalse(VinylRoutes.ANALYTICS_STYLE_RECORDS_PATTERN.isPortraitLockedOverflowRoute())
    }
}
