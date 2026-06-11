package com.example.vinyllistenapp.navigation

import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.navArgument
import com.example.vinyllistenapp.data.MockVinylData
import com.example.vinyllistenapp.data.api.VinylApiClient
import com.example.vinyllistenapp.domain.MatchCandidate
import com.example.vinyllistenapp.domain.TimedSessionGroup
import com.example.vinyllistenapp.ui.components.LocalActiveTimedSessionId
import com.example.vinyllistenapp.ui.components.LocalTimedSessionBanner
import com.example.vinyllistenapp.ui.components.LockPortraitOrientation
import com.example.vinyllistenapp.ui.components.TimedSessionBanner
import com.example.vinyllistenapp.ui.screens.AiInsightsScreen
import com.example.vinyllistenapp.ui.screens.AnalyticsScreen
import com.example.vinyllistenapp.ui.screens.CaptureRecordScreen
import com.example.vinyllistenapp.ui.screens.CollectionScreen
import com.example.vinyllistenapp.ui.screens.EditSessionScreen
import com.example.vinyllistenapp.ui.screens.HomeScreen
import com.example.vinyllistenapp.ui.screens.ManualSearchMode
import com.example.vinyllistenapp.ui.screens.ManualSearchScreen
import com.example.vinyllistenapp.ui.screens.MatchConfirmationScreen
import com.example.vinyllistenapp.ui.screens.MonthSessionsDrilldownScreen
import com.example.vinyllistenapp.ui.screens.MoodDistributionScreen
import com.example.vinyllistenapp.ui.screens.MoodRecordsDrilldownScreen
import com.example.vinyllistenapp.ui.screens.ProcessingScreen
import com.example.vinyllistenapp.ui.screens.RatingRecordsDrilldownScreen
import com.example.vinyllistenapp.ui.screens.RecentSessionsScreen
import com.example.vinyllistenapp.ui.screens.RecordDetailScreen
import com.example.vinyllistenapp.ui.screens.SessionLoggingScreen
import com.example.vinyllistenapp.ui.screens.SettingsScreen
import com.example.vinyllistenapp.ui.screens.StyleDistributionScreen
import com.example.vinyllistenapp.ui.screens.StyleRecordsDrilldownScreen
import com.example.vinyllistenapp.ui.screens.TopRecordsScreen
import com.example.vinyllistenapp.ui.screens.rememberAiInsightsScreenState
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private const val NAV_FADE_DURATION_MILLIS = 140
private const val TIMED_SESSION_REFRESH_MILLIS = 60_000L

@Composable
fun VinylNavHost(
    navController: NavHostController,
    modifier: Modifier = Modifier,
) {
    val apiClient = remember { VinylApiClient() }
    val aiInsightsState = rememberAiInsightsScreenState()
    val appScope = rememberCoroutineScope()
    val aiInsightsRequestScope = appScope
    var latestCandidates by rememberSaveable(stateSaver = MatchCandidateListSaver) {
        mutableStateOf(MockVinylData.matchCandidates)
    }
    var activeTimedSession by remember { mutableStateOf<TimedSessionGroup?>(null) }
    var isStartingTimedSession by remember { mutableStateOf(false) }
    var isStoppingTimedSession by remember { mutableStateOf(false) }
    var autoAddTimedSessionRecords by rememberSaveable { mutableStateOf(true) }
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination?.route
    LockPortraitOrientation(enabled = currentRoute.isPortraitLockedOverflowRoute())

    suspend fun refreshTimedSession() {
        runCatching { apiClient.getActiveSessionGroup() }
            .onSuccess { activeTimedSession = it }
    }

    fun startTimedSession() {
        if (isStartingTimedSession) return
        isStartingTimedSession = true
        appScope.launch {
            runCatching { apiClient.startSessionGroup() }
                .onSuccess { activeTimedSession = it }
                .onFailure { refreshTimedSession() }
            isStartingTimedSession = false
        }
    }

    fun stopTimedSession() {
        val sessionGroup = activeTimedSession ?: return
        if (isStoppingTimedSession) return
        isStoppingTimedSession = true
        appScope.launch {
            runCatching { apiClient.finishSessionGroup(sessionGroup.id) }
                .onSuccess { activeTimedSession = null }
                .onFailure { refreshTimedSession() }
            isStoppingTimedSession = false
        }
    }

    LaunchedEffect(Unit) {
        refreshTimedSession()
    }

    LaunchedEffect(activeTimedSession?.id) {
        while (activeTimedSession != null) {
            delay(TIMED_SESSION_REFRESH_MILLIS)
            refreshTimedSession()
        }
    }

    val timedSessionBanner: (@Composable () -> Unit)? =
        activeTimedSession
            ?.takeUnless { currentRoute.isIdentifyFlowWithoutTimedSessionBanner() }
            ?.let { sessionGroup ->
                {
                    TimedSessionBanner(
                        sessionGroup = sessionGroup,
                        autoAddEnabled = autoAddTimedSessionRecords,
                        isStopping = isStoppingTimedSession,
                        onAutoAddToggle = { autoAddTimedSessionRecords = !autoAddTimedSessionRecords },
                        onStop = ::stopTimedSession,
                    )
                }
            }

    CompositionLocalProvider(
        LocalTimedSessionBanner provides timedSessionBanner,
        LocalActiveTimedSessionId provides activeTimedSession?.id,
    ) {
        NavHost(
            navController = navController,
            startDestination = VinylRoutes.HOME,
            modifier = modifier,
            enterTransition = { fadeIn(animationSpec = tween(NAV_FADE_DURATION_MILLIS)) },
            exitTransition = { fadeOut(animationSpec = tween(NAV_FADE_DURATION_MILLIS)) },
            popEnterTransition = { fadeIn(animationSpec = tween(NAV_FADE_DURATION_MILLIS)) },
            popExitTransition = { fadeOut(animationSpec = tween(NAV_FADE_DURATION_MILLIS)) },
        ) {
            composable(VinylRoutes.HOME) {
                HomeScreen(
                    apiClient = apiClient,
                    onLogSession = { navController.navigate(VinylRoutes.CAPTURE_RECORD) },
                    onOpenRecord = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
                    onOpenAnalytics = { navController.navigate(VinylRoutes.ANALYTICS) },
                    onOpenInsights = { navController.navigate(VinylRoutes.AI_INSIGHTS) },
                    onOpenCollection = { navController.navigate(VinylRoutes.COLLECTION) },
                    onOpenSettings = { navController.navigate(VinylRoutes.SETTINGS) },
                    onViewAllSessions = { navController.navigate(VinylRoutes.RECENT_SESSIONS) },
                    onEditSession = { sessionId -> navController.navigate(VinylRoutes.sessionEdit(sessionId)) },
                    hasActiveTimedSession = activeTimedSession != null,
                    isStartingTimedSession = isStartingTimedSession,
                    onStartTimedSession = ::startTimedSession,
                )
            }
            composable(VinylRoutes.RECENT_SESSIONS) {
                RecentSessionsScreen(
                    apiClient = apiClient,
                    onBack = { navController.popBackStack() },
                    onOpenRecord = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
                    onEditSession = { sessionId -> navController.navigate(VinylRoutes.sessionEdit(sessionId)) },
                )
            }
            composable(VinylRoutes.CAPTURE_RECORD) {
                CaptureRecordScreen(
                    onImageSelected = { imageUri -> navController.navigate(VinylRoutes.processing(imageUri)) },
                    onManualSearch = { navController.navigate(VinylRoutes.MANUAL_SEARCH) },
                    onDismiss = {
                        navController.navigate(VinylRoutes.HOME) {
                            popUpTo(VinylRoutes.HOME) { inclusive = true }
                        }
                    },
                )
            }
            composable(
                route = VinylRoutes.PROCESSING_PATTERN,
                arguments =
                    listOf(
                        navArgument(VinylRoutes.IMAGE_URI) {
                            type = NavType.StringType
                            nullable = true
                            defaultValue = null
                        },
                    ),
            ) { backStackEntry ->
                ProcessingScreen(
                    imageUri = backStackEntry.arguments?.getString(VinylRoutes.IMAGE_URI),
                    apiClient = apiClient,
                    onComplete = { candidates ->
                        latestCandidates = candidates
                        navController.navigate(VinylRoutes.MATCH_CONFIRMATION) {
                            popUpTo(backStackEntry.destination.id) { inclusive = true }
                        }
                    },
                    onManualSearch = { navController.navigate(VinylRoutes.MANUAL_SEARCH) },
                    onDismiss = {
                        navController.navigate(VinylRoutes.HOME) {
                            popUpTo(VinylRoutes.HOME) { inclusive = true }
                        }
                    },
                )
            }
            composable(VinylRoutes.MATCH_CONFIRMATION) {
                MatchConfirmationScreen(
                    candidates = latestCandidates,
                    apiClient = apiClient,
                    onConfirm = { releaseId -> navController.navigate(VinylRoutes.sessionLogging(releaseId)) },
                    onManualSearch = { navController.navigate(VinylRoutes.MANUAL_SEARCH) },
                    onDismiss = {
                        navController.navigate(VinylRoutes.HOME) {
                            popUpTo(VinylRoutes.HOME) { inclusive = true }
                        }
                    },
                )
            }
            composable(VinylRoutes.MANUAL_SEARCH) {
                ManualSearchScreen(
                    apiClient = apiClient,
                    onSelectRecord = { releaseId -> navController.navigate(VinylRoutes.sessionLogging(releaseId)) },
                    onDismiss = {
                        navController.navigate(VinylRoutes.HOME) {
                            popUpTo(VinylRoutes.HOME) { inclusive = true }
                        }
                    },
                )
            }
            composable(VinylRoutes.COLLECTION_MANUAL_SEARCH) {
                ManualSearchScreen(
                    apiClient = apiClient,
                    mode = ManualSearchMode.Collection,
                    onSelectRecord = { releaseId ->
                        navController.navigate(VinylRoutes.recordDetail(releaseId)) {
                            popUpTo(VinylRoutes.COLLECTION_MANUAL_SEARCH) { inclusive = true }
                        }
                    },
                    onDismiss = { navController.popBackStack() },
                )
            }
            composable(
                route = VinylRoutes.SESSION_LOGGING_PATTERN,
                arguments = listOf(navArgument(VinylRoutes.RELEASE_ID) { type = NavType.StringType }),
            ) { backStackEntry ->
                SessionLoggingScreen(
                    releaseId = backStackEntry.arguments?.getString(VinylRoutes.RELEASE_ID),
                    apiClient = apiClient,
                    onSave = { releaseId ->
                        appScope.launch { refreshTimedSession() }
                        val previousRoute = navController.previousBackStackEntry?.destination?.route
                        navController.navigate(VinylRoutes.recordDetail(releaseId)) {
                            when (previousRoute) {
                                VinylRoutes.RECORD_DETAIL_PATTERN -> {
                                    popUpTo(VinylRoutes.RECORD_DETAIL_PATTERN) { inclusive = true }
                                }

                                VinylRoutes.MATCH_CONFIRMATION,
                                VinylRoutes.MANUAL_SEARCH,
                                -> {
                                    popUpTo(VinylRoutes.HOME)
                                }

                                else -> {
                                    popUpTo(backStackEntry.destination.id) { inclusive = true }
                                }
                            }
                        }
                    },
                    onCancel = { navController.popBackStack() },
                    activeSessionGroupId = activeTimedSession?.id?.takeIf { autoAddTimedSessionRecords },
                )
            }
            composable(
                route = VinylRoutes.SESSION_EDIT_PATTERN,
                arguments = listOf(navArgument(VinylRoutes.SESSION_ID) { type = NavType.StringType }),
            ) { backStackEntry ->
                EditSessionScreen(
                    sessionId = backStackEntry.arguments?.getString(VinylRoutes.SESSION_ID),
                    apiClient = apiClient,
                    onSave = { releaseId ->
                        val previousRoute = navController.previousBackStackEntry?.destination?.route
                        navController.navigate(VinylRoutes.recordDetail(releaseId)) {
                            if (previousRoute == VinylRoutes.RECORD_DETAIL_PATTERN) {
                                popUpTo(VinylRoutes.RECORD_DETAIL_PATTERN) { inclusive = true }
                            } else {
                                popUpTo(backStackEntry.destination.id) { inclusive = true }
                            }
                        }
                    },
                    onCancel = { navController.popBackStack() },
                )
            }
            composable(
                route = VinylRoutes.RECORD_DETAIL_PATTERN,
                arguments = listOf(navArgument(VinylRoutes.RELEASE_ID) { type = NavType.StringType }),
            ) { backStackEntry ->
                RecordDetailScreen(
                    releaseId = backStackEntry.arguments?.getString(VinylRoutes.RELEASE_ID),
                    apiClient = apiClient,
                    onAddSession = { releaseId -> navController.navigate(VinylRoutes.sessionLogging(releaseId)) },
                    onEditSession = { sessionId -> navController.navigate(VinylRoutes.sessionEdit(sessionId)) },
                    onOpenRecord = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
                    onBack = {
                        if (!navController.popBackStack()) {
                            navController.navigate(VinylRoutes.HOME)
                        }
                    },
                )
            }
            composable(VinylRoutes.ANALYTICS) {
                AnalyticsScreen(
                    apiClient = apiClient,
                    onHome = {
                        navController.navigate(VinylRoutes.HOME) {
                            popUpTo(VinylRoutes.HOME) { inclusive = true }
                        }
                    },
                    onOpenRecord = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
                    onInsights = { navController.navigate(VinylRoutes.AI_INSIGHTS) },
                    onCollection = { navController.navigate(VinylRoutes.COLLECTION) },
                    onViewAllTopRecords = { navController.navigate(VinylRoutes.TOP_RECORDS) },
                    onViewAllMoods = { navController.navigate(VinylRoutes.MOOD_DISTRIBUTION) },
                    onViewAllStyles = { navController.navigate(VinylRoutes.STYLE_DISTRIBUTION) },
                    onOpenMonthSessions = { month -> navController.navigate(VinylRoutes.analyticsMonthSessions(month)) },
                    onOpenRatingRecords = { rating -> navController.navigate(VinylRoutes.analyticsRatingRecords(rating)) },
                    onOpenMoodRecords = { mood -> navController.navigate(VinylRoutes.analyticsMoodRecords(mood)) },
                    onOpenStyleRecords = { style -> navController.navigate(VinylRoutes.analyticsStyleRecords(style)) },
                )
            }
            composable(VinylRoutes.AI_INSIGHTS) {
                AiInsightsScreen(
                    apiClient = apiClient,
                    state = aiInsightsState,
                    requestScope = aiInsightsRequestScope,
                    onHome = {
                        navController.navigate(VinylRoutes.HOME) {
                            popUpTo(VinylRoutes.HOME) { inclusive = true }
                        }
                    },
                    onStats = { navController.navigate(VinylRoutes.ANALYTICS) },
                    onCollection = { navController.navigate(VinylRoutes.COLLECTION) },
                )
            }
            composable(VinylRoutes.COLLECTION) {
                CollectionScreen(
                    apiClient = apiClient,
                    onHome = {
                        navController.navigate(VinylRoutes.HOME) {
                            popUpTo(VinylRoutes.HOME) { inclusive = true }
                        }
                    },
                    onStats = { navController.navigate(VinylRoutes.ANALYTICS) },
                    onInsights = { navController.navigate(VinylRoutes.AI_INSIGHTS) },
                    onManualSearch = { navController.navigate(VinylRoutes.COLLECTION_MANUAL_SEARCH) },
                    onOpenRecord = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
                )
            }
            composable(VinylRoutes.TOP_RECORDS) {
                TopRecordsScreen(
                    apiClient = apiClient,
                    onBack = { navController.popBackStack() },
                    onOpenRecord = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
                )
            }
            composable(VinylRoutes.MOOD_DISTRIBUTION) {
                MoodDistributionScreen(
                    apiClient = apiClient,
                    onBack = { navController.popBackStack() },
                    onOpenMoodRecords = { mood -> navController.navigate(VinylRoutes.analyticsMoodRecords(mood)) },
                )
            }
            composable(VinylRoutes.STYLE_DISTRIBUTION) {
                StyleDistributionScreen(
                    apiClient = apiClient,
                    onBack = { navController.popBackStack() },
                    onOpenStyleRecords = { style -> navController.navigate(VinylRoutes.analyticsStyleRecords(style)) },
                )
            }
            composable(
                route = VinylRoutes.ANALYTICS_MONTH_SESSIONS_PATTERN,
                arguments = listOf(navArgument(VinylRoutes.MONTH) { type = NavType.StringType }),
            ) { backStackEntry ->
                MonthSessionsDrilldownScreen(
                    apiClient = apiClient,
                    month = backStackEntry.arguments?.getString(VinylRoutes.MONTH).orEmpty(),
                    onBack = { navController.popBackStack() },
                    onOpenRecord = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
                )
            }
            composable(
                route = VinylRoutes.ANALYTICS_RATING_RECORDS_PATTERN,
                arguments = listOf(navArgument(VinylRoutes.RATING) { type = NavType.IntType }),
            ) { backStackEntry ->
                RatingRecordsDrilldownScreen(
                    apiClient = apiClient,
                    rating = backStackEntry.arguments?.getInt(VinylRoutes.RATING) ?: 0,
                    onBack = { navController.popBackStack() },
                    onOpenRecord = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
                )
            }
            composable(
                route = VinylRoutes.ANALYTICS_MOOD_RECORDS_PATTERN,
                arguments = listOf(navArgument(VinylRoutes.MOOD) { type = NavType.StringType }),
            ) { backStackEntry ->
                MoodRecordsDrilldownScreen(
                    apiClient = apiClient,
                    mood = backStackEntry.arguments?.getString(VinylRoutes.MOOD).orEmpty(),
                    onBack = { navController.popBackStack() },
                    onOpenRecord = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
                )
            }
            composable(
                route = VinylRoutes.ANALYTICS_STYLE_RECORDS_PATTERN,
                arguments = listOf(navArgument(VinylRoutes.STYLE) { type = NavType.StringType }),
            ) { backStackEntry ->
                StyleRecordsDrilldownScreen(
                    apiClient = apiClient,
                    style = backStackEntry.arguments?.getString(VinylRoutes.STYLE).orEmpty(),
                    onBack = { navController.popBackStack() },
                    onOpenRecord = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
                )
            }
            composable(VinylRoutes.SETTINGS) {
                SettingsScreen(
                    message = "Settings stays out of this prototype pass.",
                    onHome = {
                        navController.navigate(VinylRoutes.HOME) {
                            popUpTo(VinylRoutes.HOME) { inclusive = true }
                        }
                    },
                    onStats = { navController.navigate(VinylRoutes.ANALYTICS) },
                    onInsights = { navController.navigate(VinylRoutes.AI_INSIGHTS) },
                    onCollection = { navController.navigate(VinylRoutes.COLLECTION) },
                )
            }
        }
    }
}

internal fun String?.isPortraitLockedOverflowRoute(): Boolean =
    this in
        setOf(
            VinylRoutes.CAPTURE_RECORD,
            VinylRoutes.PROCESSING_PATTERN,
            VinylRoutes.MATCH_CONFIRMATION,
            VinylRoutes.MANUAL_SEARCH,
            VinylRoutes.COLLECTION_MANUAL_SEARCH,
            VinylRoutes.SESSION_LOGGING_PATTERN,
            VinylRoutes.SESSION_EDIT_PATTERN,
            VinylRoutes.RECORD_DETAIL_PATTERN,
            VinylRoutes.AI_INSIGHTS,
        )

private fun String?.isIdentifyFlowWithoutTimedSessionBanner(): Boolean =
    this in
        setOf(
            VinylRoutes.CAPTURE_RECORD,
            VinylRoutes.PROCESSING_PATTERN,
            VinylRoutes.MATCH_CONFIRMATION,
        )

private const val MATCHED_ON_SEPARATOR = "\u001F"

private val MatchCandidateListSaver: Saver<List<MatchCandidate>, List<List<String?>>> =
    Saver(
        save = { candidates -> encodeMatchCandidatesForSavedState(candidates) },
        restore = { value -> decodeMatchCandidatesFromSavedState(value) },
    )

internal fun encodeMatchCandidatesForSavedState(candidates: List<MatchCandidate>): List<List<String?>> =
    candidates.map { candidate ->
        listOf(
            candidate.releaseId,
            candidate.discogsReleaseId.toString(),
            candidate.artist,
            candidate.title,
            candidate.label,
            candidate.confidence.toString(),
            candidate.year?.toString(),
            candidate.catalogNumber,
            candidate.barcode,
            candidate.coverImageUrl,
            candidate.format,
            candidate.matchSource,
            candidate.matchedOn.joinToString(MATCHED_ON_SEPARATOR),
        )
    }

internal fun decodeMatchCandidatesFromSavedState(value: List<List<String?>>): List<MatchCandidate> {
    val decodedCandidates =
        value.mapNotNull { candidate ->
            val discogsReleaseId = candidate.getOrNull(1)?.toLongOrNull() ?: return@mapNotNull null
            MatchCandidate(
                releaseId = candidate.getOrNull(0),
                discogsReleaseId = discogsReleaseId,
                artist = candidate.getOrNull(2) ?: "Unknown artist",
                title = candidate.getOrNull(3) ?: "Unknown title",
                label = candidate.getOrNull(4) ?: "Unknown label",
                confidence = candidate.getOrNull(5)?.toIntOrNull() ?: 0,
                year = candidate.getOrNull(6)?.toIntOrNull(),
                catalogNumber = candidate.getOrNull(7),
                barcode = candidate.getOrNull(8),
                coverImageUrl = candidate.getOrNull(9),
                format = candidate.getOrNull(10),
                matchSource = candidate.getOrNull(11),
                matchedOn =
                    candidate
                        .getOrNull(12)
                        ?.split(MATCHED_ON_SEPARATOR)
                        ?.filter { it.isNotBlank() }
                        .orEmpty(),
            )
        }

    return decodedCandidates.ifEmpty { MockVinylData.matchCandidates }
}
