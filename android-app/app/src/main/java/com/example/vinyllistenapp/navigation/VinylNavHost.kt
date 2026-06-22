package com.example.vinyllistenapp.navigation

import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
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
import com.example.vinyllistenapp.data.auth.AuthAccountRepository
import com.example.vinyllistenapp.domain.CollectionFolder
import com.example.vinyllistenapp.domain.MatchCandidate
import com.example.vinyllistenapp.domain.TimedSessionGroup
import com.example.vinyllistenapp.ui.components.LocalActiveTimedSessionId
import com.example.vinyllistenapp.ui.components.LocalTimedSessionBanner
import com.example.vinyllistenapp.ui.components.LockPortraitOrientation
import com.example.vinyllistenapp.ui.components.TimedSessionBanner
import com.example.vinyllistenapp.ui.screens.AiInsightsScreen
import com.example.vinyllistenapp.ui.screens.AllDiscogsFoldersScreen
import com.example.vinyllistenapp.ui.screens.AnalyticsScreen
import com.example.vinyllistenapp.ui.screens.BarcodeProcessingScreen
import com.example.vinyllistenapp.ui.screens.CaptureRecordScreen
import com.example.vinyllistenapp.ui.screens.CollectionScreen
import com.example.vinyllistenapp.ui.screens.EditSessionScreen
import com.example.vinyllistenapp.ui.screens.HomeScreen
import com.example.vinyllistenapp.ui.screens.ManualReleaseFormScreen
import com.example.vinyllistenapp.ui.screens.ManualSearchMode
import com.example.vinyllistenapp.ui.screens.ManualSearchScreen
import com.example.vinyllistenapp.ui.screens.ManualSubmissionsScreen
import com.example.vinyllistenapp.ui.screens.MatchConfirmationMode
import com.example.vinyllistenapp.ui.screens.MatchConfirmationScreen
import com.example.vinyllistenapp.ui.screens.MonthSessionsDrilldownScreen
import com.example.vinyllistenapp.ui.screens.MoodDistributionScreen
import com.example.vinyllistenapp.ui.screens.MoodRecordsDrilldownScreen
import com.example.vinyllistenapp.ui.screens.ProcessingScreen
import com.example.vinyllistenapp.ui.screens.RatingRecordsDrilldownScreen
import com.example.vinyllistenapp.ui.screens.RecentSessionsScreen
import com.example.vinyllistenapp.ui.screens.RecordActionItemsScreen
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
private const val COLLECTION_MEMBERSHIP_REFRESH_KEY = "collectionMembershipRefreshKey"
private const val MANUAL_SUBMISSIONS_REFRESH_KEY = "manualSubmissionsRefreshKey"

@Composable
fun VinylNavHost(
    navController: NavHostController,
    modifier: Modifier = Modifier,
    apiClient: VinylApiClient? = null,
    authAccountRepository: AuthAccountRepository? = null,
    onAuthSessionEnded: () -> Unit = {},
    onAccountDeleted: () -> Unit = {},
) {
    val activeApiClient = apiClient ?: remember { VinylApiClient() }
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
        runCatching { activeApiClient.getActiveSessionGroup() }
            .onSuccess { activeTimedSession = it }
    }

    fun notifyCollectionMembershipChanged() {
        val handle =
            sequenceOf(VinylRoutes.COLLECTION_PATTERN, VinylRoutes.COLLECTION)
                .mapNotNull { route ->
                    runCatching { navController.getBackStackEntry(route).savedStateHandle }.getOrNull()
                }.firstOrNull()
                ?: return
        handle.set(
            COLLECTION_MEMBERSHIP_REFRESH_KEY,
            (handle.get<Int>(COLLECTION_MEMBERSHIP_REFRESH_KEY) ?: 0) + 1,
        )
    }

    fun notifyManualSubmissionsChanged() {
        val handle =
            runCatching { navController.getBackStackEntry(VinylRoutes.COLLECTION_MANUAL_ENTRY).savedStateHandle }
                .getOrNull()
                ?: return
        handle.set(
            MANUAL_SUBMISSIONS_REFRESH_KEY,
            (handle.get<Int>(MANUAL_SUBMISSIONS_REFRESH_KEY) ?: 0) + 1,
        )
    }

    fun startTimedSession(
        styleFocus: String,
        moodDirection: String,
        sessionType: String,
        notes: String?,
    ) {
        if (isStartingTimedSession) return
        isStartingTimedSession = true
        appScope.launch {
            runCatching {
                activeApiClient.startSessionGroup(
                    styleFocus = styleFocus,
                    moodDirection = moodDirection,
                    sessionType = sessionType,
                    notes = notes,
                )
            }.onSuccess { activeTimedSession = it }
                .onFailure { refreshTimedSession() }
            isStartingTimedSession = false
        }
    }

    fun stopTimedSession() {
        val sessionGroup = activeTimedSession ?: return
        if (isStoppingTimedSession) return
        isStoppingTimedSession = true
        appScope.launch {
            runCatching { activeApiClient.finishSessionGroup(sessionGroup.id) }
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
                    apiClient = activeApiClient,
                    onLogSession = { navController.navigate(VinylRoutes.captureRecord()) },
                    onOpenRecord = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
                    onOpenAnalytics = { navController.navigate(VinylRoutes.ANALYTICS) },
                    onOpenInsights = { navController.navigate(VinylRoutes.AI_INSIGHTS) },
                    onOpenCollection = { navController.navigate(VinylRoutes.COLLECTION) },
                    onOpenSettings = { navController.navigate(VinylRoutes.SETTINGS) },
                    onViewAllSessions = { navController.navigate(VinylRoutes.RECENT_SESSIONS) },
                    onEditSession = { sessionId -> navController.navigate(VinylRoutes.sessionEdit(sessionId)) },
                    hasActiveTimedSession = activeTimedSession != null,
                    isStartingTimedSession = isStartingTimedSession,
                    autoAddTimedSessionRecords = autoAddTimedSessionRecords,
                    onAutoAddTimedSessionRecordsToggle = {
                        autoAddTimedSessionRecords = !autoAddTimedSessionRecords
                    },
                    onStartTimedSession = ::startTimedSession,
                )
            }
            composable(VinylRoutes.RECENT_SESSIONS) {
                RecentSessionsScreen(
                    apiClient = activeApiClient,
                    onBack = { navController.popBackStack() },
                    onOpenRecord = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
                    onEditSession = { sessionId -> navController.navigate(VinylRoutes.sessionEdit(sessionId)) },
                )
            }
            composable(
                route = VinylRoutes.CAPTURE_RECORD_PATTERN,
                arguments =
                    listOf(
                        navArgument(VinylRoutes.FLOW_MODE) {
                            type = NavType.StringType
                            defaultValue = VinylRoutes.FLOW_MODE_SESSION
                        },
                    ),
            ) { backStackEntry ->
                val flowMode = backStackEntry.arguments?.getString(VinylRoutes.FLOW_MODE).asIdentifyFlowMode()
                CaptureRecordScreen(
                    apiClient = activeApiClient,
                    onImageSelected = { imageUri -> navController.navigate(VinylRoutes.processing(imageUri, flowMode)) },
                    onManualSearch = { navController.navigate(flowMode.manualSearchRoute()) },
                    onBarcodeDetected = { barcode ->
                        navController.navigate(VinylRoutes.barcodeProcessing(barcode, flowMode)) {
                            popUpTo(VinylRoutes.CAPTURE_RECORD_PATTERN) { inclusive = true }
                        }
                    },
                    onDismiss = {
                        if (flowMode == VinylRoutes.FLOW_MODE_COLLECTION_ADD) {
                            navController.popBackStack()
                        } else {
                            navController.navigate(VinylRoutes.HOME) {
                                popUpTo(VinylRoutes.HOME) { inclusive = true }
                            }
                        }
                    },
                )
            }
            composable(
                route = VinylRoutes.BARCODE_PROCESSING_PATTERN,
                arguments =
                    listOf(
                        navArgument(VinylRoutes.BARCODE) {
                            type = NavType.StringType
                            defaultValue = ""
                        },
                    ),
            ) { backStackEntry ->
                val barcode = backStackEntry.arguments?.getString(VinylRoutes.BARCODE).orEmpty()
                val flowMode = backStackEntry.arguments?.getString(VinylRoutes.FLOW_MODE).asIdentifyFlowMode()
                BarcodeProcessingScreen(
                    barcode = barcode,
                    onComplete = { candidates ->
                        latestCandidates = candidates
                        navController.navigate(VinylRoutes.matchConfirmation(flowMode)) {
                            popUpTo(VinylRoutes.BARCODE_PROCESSING_PATTERN) { inclusive = true }
                        }
                    },
                    onRetryScan = {
                        navController.navigate(VinylRoutes.captureRecord(flowMode)) {
                            popUpTo(VinylRoutes.BARCODE_PROCESSING_PATTERN) { inclusive = true }
                        }
                    },
                    onManualSearch = { detectedBarcode ->
                        if (flowMode == VinylRoutes.FLOW_MODE_COLLECTION_ADD) {
                            navController.navigate(VinylRoutes.COLLECTION_MANUAL_SEARCH) {
                                popUpTo(VinylRoutes.BARCODE_PROCESSING_PATTERN) { inclusive = true }
                            }
                        } else {
                            navController.navigate(VinylRoutes.manualSearchBarcode(detectedBarcode)) {
                                popUpTo(VinylRoutes.BARCODE_PROCESSING_PATTERN) { inclusive = true }
                            }
                        }
                    },
                    onDismiss = {
                        if (flowMode == VinylRoutes.FLOW_MODE_COLLECTION_ADD) {
                            navController.popBackStack()
                        } else {
                            navController.navigate(VinylRoutes.HOME) {
                                popUpTo(VinylRoutes.HOME) { inclusive = true }
                            }
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
                val flowMode = backStackEntry.arguments?.getString(VinylRoutes.FLOW_MODE).asIdentifyFlowMode()
                ProcessingScreen(
                    imageUri = backStackEntry.arguments?.getString(VinylRoutes.IMAGE_URI),
                    apiClient = activeApiClient,
                    onComplete = { candidates ->
                        latestCandidates = candidates
                        navController.navigate(VinylRoutes.matchConfirmation(flowMode)) {
                            popUpTo(backStackEntry.destination.id) { inclusive = true }
                        }
                    },
                    onManualSearch = { navController.navigate(flowMode.manualSearchRoute()) },
                    onDismiss = {
                        if (flowMode == VinylRoutes.FLOW_MODE_COLLECTION_ADD) {
                            if (!navController.popBackStack(VinylRoutes.COLLECTION_PATTERN, inclusive = false)) {
                                navController.navigate(VinylRoutes.COLLECTION)
                            }
                        } else {
                            navController.navigate(VinylRoutes.HOME) {
                                popUpTo(VinylRoutes.HOME) { inclusive = true }
                            }
                        }
                    },
                )
            }
            composable(
                route = VinylRoutes.MATCH_CONFIRMATION_PATTERN,
                arguments =
                    listOf(
                        navArgument(VinylRoutes.FLOW_MODE) {
                            type = NavType.StringType
                            defaultValue = VinylRoutes.FLOW_MODE_SESSION
                        },
                    ),
            ) { backStackEntry ->
                val flowMode = backStackEntry.arguments?.getString(VinylRoutes.FLOW_MODE).asIdentifyFlowMode()
                val matchMode = flowMode.toMatchConfirmationMode()
                MatchConfirmationScreen(
                    candidates = latestCandidates,
                    apiClient = activeApiClient,
                    mode = matchMode,
                    onConfirm = { releaseId ->
                        if (matchMode == MatchConfirmationMode.CollectionAdd) {
                            notifyCollectionMembershipChanged()
                            val hasCollectionBackStack =
                                runCatching { navController.getBackStackEntry(VinylRoutes.COLLECTION_PATTERN) }.isSuccess ||
                                    runCatching { navController.getBackStackEntry(VinylRoutes.COLLECTION) }.isSuccess
                            navController.navigate(VinylRoutes.recordDetail(releaseId)) {
                                if (hasCollectionBackStack) {
                                    popUpTo(VinylRoutes.COLLECTION_PATTERN)
                                }
                            }
                        } else {
                            navController.navigate(VinylRoutes.sessionLogging(releaseId))
                        }
                    },
                    onManualSearch = { navController.navigate(flowMode.manualSearchRoute()) },
                    onDismiss = {
                        if (flowMode == VinylRoutes.FLOW_MODE_COLLECTION_ADD) {
                            navController.popBackStack()
                        } else {
                            navController.navigate(VinylRoutes.HOME) {
                                popUpTo(VinylRoutes.HOME) { inclusive = true }
                            }
                        }
                    },
                )
            }
            composable(
                route = VinylRoutes.MANUAL_SEARCH_PATTERN,
                arguments =
                    listOf(
                        navArgument(VinylRoutes.BARCODE) {
                            type = NavType.StringType
                            defaultValue = ""
                        },
                    ),
            ) { backStackEntry ->
                ManualSearchScreen(
                    apiClient = activeApiClient,
                    initialBarcode = backStackEntry.arguments?.getString(VinylRoutes.BARCODE).orEmpty(),
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
                    apiClient = activeApiClient,
                    mode = ManualSearchMode.Collection,
                    onSelectRecord = { releaseId ->
                        navController.navigate(VinylRoutes.recordDetail(releaseId)) {
                            popUpTo(VinylRoutes.COLLECTION_MANUAL_SEARCH) { inclusive = true }
                        }
                    },
                    onDismiss = { navController.popBackStack() },
                )
            }
            composable(VinylRoutes.COLLECTION_MANUAL_ENTRY) {
                val manualSubmissionsRefreshKey by
                    it.savedStateHandle
                        .getStateFlow(MANUAL_SUBMISSIONS_REFRESH_KEY, 0)
                        .collectAsState()
                ManualSubmissionsScreen(
                    apiClient = activeApiClient,
                    refreshKey = manualSubmissionsRefreshKey,
                    onHome = {
                        navController.navigate(VinylRoutes.HOME) {
                            popUpTo(VinylRoutes.HOME) { inclusive = true }
                        }
                    },
                    onStats = { navController.navigate(VinylRoutes.ANALYTICS) },
                    onInsights = { navController.navigate(VinylRoutes.AI_INSIGHTS) },
                    onCollection = { navController.navigate(VinylRoutes.COLLECTION) },
                    onAddRelease = { navController.navigate(VinylRoutes.manualReleaseForm()) },
                    onOpenDraft = { draftId -> navController.navigate(VinylRoutes.manualReleaseForm(draftId)) },
                )
            }
            composable(
                route = VinylRoutes.COLLECTION_MANUAL_FORM_PATTERN,
                arguments =
                    listOf(
                        navArgument(VinylRoutes.DRAFT_ID) {
                            type = NavType.StringType
                            nullable = true
                            defaultValue = null
                        },
                    ),
            ) { backStackEntry ->
                ManualReleaseFormScreen(
                    apiClient = activeApiClient,
                    draftId = backStackEntry.arguments?.getString(VinylRoutes.DRAFT_ID),
                    onCancel = { navController.popBackStack() },
                    onDraftSaved = {
                        notifyManualSubmissionsChanged()
                        navController.popBackStack()
                    },
                    onReleaseSaved = { releaseId ->
                        notifyManualSubmissionsChanged()
                        notifyCollectionMembershipChanged()
                        navController.navigate(VinylRoutes.recordDetail(releaseId)) {
                            popUpTo(VinylRoutes.COLLECTION_PATTERN)
                        }
                    },
                )
            }
            composable(
                route = VinylRoutes.SESSION_LOGGING_PATTERN,
                arguments = listOf(navArgument(VinylRoutes.RELEASE_ID) { type = NavType.StringType }),
            ) { backStackEntry ->
                SessionLoggingScreen(
                    releaseId = backStackEntry.arguments?.getString(VinylRoutes.RELEASE_ID),
                    apiClient = activeApiClient,
                    onSave = { releaseId ->
                        appScope.launch { refreshTimedSession() }
                        val previousRoute = navController.previousBackStackEntry?.destination?.route
                        navController.navigate(VinylRoutes.recordDetail(releaseId)) {
                            when (previousRoute) {
                                VinylRoutes.RECORD_DETAIL_PATTERN -> {
                                    popUpTo(VinylRoutes.RECORD_DETAIL_PATTERN) { inclusive = true }
                                }

                                VinylRoutes.MATCH_CONFIRMATION_PATTERN,
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
                    apiClient = activeApiClient,
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
                    apiClient = activeApiClient,
                    onAddSession = { releaseId -> navController.navigate(VinylRoutes.sessionLogging(releaseId)) },
                    onEditSession = { sessionId -> navController.navigate(VinylRoutes.sessionEdit(sessionId)) },
                    onOpenRecord = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
                    onOpenArtistCollection = { artist -> navController.navigate(VinylRoutes.collectionArtist(artist)) },
                    onOpenLabelCollection = { label -> navController.navigate(VinylRoutes.collectionLabel(label)) },
                    onOpenRecordActionItems = { releaseId, actionType ->
                        navController.navigate(VinylRoutes.recordActionItems(releaseId, actionType))
                    },
                    onCollectionMembershipChanged = {
                        val handle = navController.previousBackStackEntry?.savedStateHandle
                        handle?.set(
                            COLLECTION_MEMBERSHIP_REFRESH_KEY,
                            (handle.get<Int>(COLLECTION_MEMBERSHIP_REFRESH_KEY) ?: 0) + 1,
                        )
                    },
                    onBack = {
                        if (!navController.popBackStack()) {
                            navController.navigate(VinylRoutes.HOME)
                        }
                    },
                    onBackToHome = {
                        navController.navigate(VinylRoutes.HOME) {
                            popUpTo(VinylRoutes.HOME) { inclusive = true }
                            launchSingleTop = true
                        }
                    },
                )
            }
            composable(VinylRoutes.ANALYTICS) {
                AnalyticsScreen(
                    apiClient = activeApiClient,
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
                    apiClient = activeApiClient,
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
            composable(
                route = VinylRoutes.RECORD_ACTION_ITEMS_PATTERN,
                arguments =
                    listOf(
                        navArgument(VinylRoutes.RELEASE_ID) { type = NavType.StringType },
                        navArgument(VinylRoutes.ACTION_TYPE) { type = NavType.StringType },
                    ),
            ) { backStackEntry ->
                RecordActionItemsScreen(
                    releaseId = backStackEntry.arguments?.getString(VinylRoutes.RELEASE_ID),
                    actionType = backStackEntry.arguments?.getString(VinylRoutes.ACTION_TYPE),
                    apiClient = activeApiClient,
                    onBack = { navController.popBackStack() },
                    onOpenArtistCollection = { artist ->
                        navController.navigate(VinylRoutes.collectionArtist(artist)) {
                            popUpTo(backStackEntry.destination.id) { inclusive = true }
                        }
                    },
                    onOpenLabelCollection = { label ->
                        navController.navigate(VinylRoutes.collectionLabel(label)) {
                            popUpTo(backStackEntry.destination.id) { inclusive = true }
                        }
                    },
                )
            }
            composable(
                route = VinylRoutes.COLLECTION_PATTERN,
                arguments =
                    listOf(
                        navArgument(VinylRoutes.ARTIST) {
                            type = NavType.StringType
                            nullable = true
                            defaultValue = null
                        },
                        navArgument(VinylRoutes.LABEL) {
                            type = NavType.StringType
                            nullable = true
                            defaultValue = null
                        },
                        navArgument(VinylRoutes.FOLDER_ID) {
                            type = NavType.StringType
                            nullable = true
                            defaultValue = null
                        },
                        navArgument(VinylRoutes.FOLDER_NAME) {
                            type = NavType.StringType
                            nullable = true
                            defaultValue = null
                        },
                        navArgument(VinylRoutes.FOLDER_COUNT) {
                            type = NavType.StringType
                            nullable = true
                            defaultValue = null
                        },
                    ),
            ) { backStackEntry ->
                val collectionRefreshKey by backStackEntry.savedStateHandle
                    .getStateFlow(COLLECTION_MEMBERSHIP_REFRESH_KEY, 0)
                    .collectAsState()
                val initialFolderFilter =
                    collectionFolderFromArgs(
                        id = backStackEntry.arguments?.getString(VinylRoutes.FOLDER_ID),
                        name = backStackEntry.arguments?.getString(VinylRoutes.FOLDER_NAME),
                        count = backStackEntry.arguments?.getString(VinylRoutes.FOLDER_COUNT),
                    )
                CollectionScreen(
                    apiClient = activeApiClient,
                    refreshKey = collectionRefreshKey,
                    onHome = {
                        navController.navigate(VinylRoutes.HOME) {
                            popUpTo(VinylRoutes.HOME) { inclusive = true }
                        }
                    },
                    onStats = { navController.navigate(VinylRoutes.ANALYTICS) },
                    onInsights = { navController.navigate(VinylRoutes.AI_INSIGHTS) },
                    onCollectionSettings = { navController.navigate(VinylRoutes.SETTINGS) },
                    onIdentifyRecord = {
                        navController.navigate(VinylRoutes.captureRecord(VinylRoutes.FLOW_MODE_COLLECTION_ADD))
                    },
                    onManualEntry = { navController.navigate(VinylRoutes.COLLECTION_MANUAL_ENTRY) },
                    onManualSearch = { navController.navigate(VinylRoutes.COLLECTION_MANUAL_SEARCH) },
                    onOpenRecord = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
                    onArtistFilterCleared = {
                        navController.navigate(VinylRoutes.COLLECTION) {
                            popUpTo(backStackEntry.destination.id) { inclusive = true }
                        }
                    },
                    onLabelFilterCleared = {
                        navController.navigate(VinylRoutes.COLLECTION) {
                            popUpTo(backStackEntry.destination.id) { inclusive = true }
                        }
                    },
                    onFolderFilterCleared = {
                        navController.navigate(VinylRoutes.COLLECTION) {
                            popUpTo(backStackEntry.destination.id) { inclusive = true }
                        }
                    },
                    onViewAllCollectionFolders = {
                        navController.navigate(VinylRoutes.ALL_DISCOGS_FOLDERS)
                    },
                    initialArtistFilter = backStackEntry.arguments?.getString(VinylRoutes.ARTIST),
                    initialLabelFilter = backStackEntry.arguments?.getString(VinylRoutes.LABEL),
                    initialFolderFilter = initialFolderFilter,
                )
            }
            composable(VinylRoutes.ALL_DISCOGS_FOLDERS) {
                AllDiscogsFoldersScreen(
                    apiClient = activeApiClient,
                    onBack = { navController.popBackStack() },
                    onOpenFolder = { folder ->
                        navController.navigate(VinylRoutes.collectionFolder(folder)) {
                            popUpTo(VinylRoutes.ALL_DISCOGS_FOLDERS) { inclusive = true }
                        }
                    },
                )
            }
            composable(VinylRoutes.TOP_RECORDS) {
                TopRecordsScreen(
                    apiClient = activeApiClient,
                    onBack = { navController.popBackStack() },
                    onOpenRecord = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
                )
            }
            composable(VinylRoutes.MOOD_DISTRIBUTION) {
                MoodDistributionScreen(
                    apiClient = activeApiClient,
                    onBack = { navController.popBackStack() },
                    onOpenMoodRecords = { mood -> navController.navigate(VinylRoutes.analyticsMoodRecords(mood)) },
                )
            }
            composable(VinylRoutes.STYLE_DISTRIBUTION) {
                StyleDistributionScreen(
                    apiClient = activeApiClient,
                    onBack = { navController.popBackStack() },
                    onOpenStyleRecords = { style -> navController.navigate(VinylRoutes.analyticsStyleRecords(style)) },
                )
            }
            composable(
                route = VinylRoutes.ANALYTICS_MONTH_SESSIONS_PATTERN,
                arguments = listOf(navArgument(VinylRoutes.MONTH) { type = NavType.StringType }),
            ) { backStackEntry ->
                MonthSessionsDrilldownScreen(
                    apiClient = activeApiClient,
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
                    apiClient = activeApiClient,
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
                    apiClient = activeApiClient,
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
                    apiClient = activeApiClient,
                    style = backStackEntry.arguments?.getString(VinylRoutes.STYLE).orEmpty(),
                    onBack = { navController.popBackStack() },
                    onOpenRecord = { releaseId -> navController.navigate(VinylRoutes.recordDetail(releaseId)) },
                )
            }
            composable(VinylRoutes.SETTINGS) {
                SettingsScreen(
                    apiClient = activeApiClient,
                    authAccountRepository = authAccountRepository,
                    message = "Application settings",
                    onAuthSessionEnded = onAuthSessionEnded,
                    onAccountDeleted = onAccountDeleted,
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
            VinylRoutes.CAPTURE_RECORD_PATTERN,
            VinylRoutes.PROCESSING_PATTERN,
            VinylRoutes.BARCODE_PROCESSING_PATTERN,
            VinylRoutes.MATCH_CONFIRMATION_PATTERN,
            VinylRoutes.MANUAL_SEARCH,
            VinylRoutes.MANUAL_SEARCH_PATTERN,
            VinylRoutes.COLLECTION_MANUAL_SEARCH,
            VinylRoutes.COLLECTION_MANUAL_ENTRY,
            VinylRoutes.COLLECTION_MANUAL_FORM_PATTERN,
            VinylRoutes.SESSION_LOGGING_PATTERN,
            VinylRoutes.SESSION_EDIT_PATTERN,
            VinylRoutes.RECORD_DETAIL_PATTERN,
            VinylRoutes.RECORD_ACTION_ITEMS_PATTERN,
            VinylRoutes.ALL_DISCOGS_FOLDERS,
            VinylRoutes.AI_INSIGHTS,
        )

private fun String?.isIdentifyFlowWithoutTimedSessionBanner(): Boolean =
    this in
        setOf(
            VinylRoutes.CAPTURE_RECORD_PATTERN,
            VinylRoutes.PROCESSING_PATTERN,
            VinylRoutes.BARCODE_PROCESSING_PATTERN,
            VinylRoutes.MATCH_CONFIRMATION_PATTERN,
        )

private fun String?.asIdentifyFlowMode(): String =
    when (this) {
        VinylRoutes.FLOW_MODE_COLLECTION_ADD -> VinylRoutes.FLOW_MODE_COLLECTION_ADD
        else -> VinylRoutes.FLOW_MODE_SESSION
    }

private fun String.manualSearchRoute(): String =
    if (this == VinylRoutes.FLOW_MODE_COLLECTION_ADD) {
        VinylRoutes.COLLECTION_MANUAL_SEARCH
    } else {
        VinylRoutes.MANUAL_SEARCH
    }

private fun String.toMatchConfirmationMode(): MatchConfirmationMode =
    if (this == VinylRoutes.FLOW_MODE_COLLECTION_ADD) {
        MatchConfirmationMode.CollectionAdd
    } else {
        MatchConfirmationMode.SessionLogging
    }

private fun collectionFolderFromArgs(
    id: String?,
    name: String?,
    count: String?,
): CollectionFolder? {
    val folderId = id?.toLongOrNull() ?: return null
    val folderName = name?.takeIf { it.isNotBlank() } ?: return null
    return CollectionFolder(
        id = folderId,
        name = folderName,
        count = count?.toIntOrNull(),
        isDefault = false,
    )
}

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
