package com.example.vinyllistenapp

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.navigation.NavHostController
import androidx.navigation.compose.rememberNavController
import com.example.vinyllistenapp.navigation.VinylNavHost
import com.example.vinyllistenapp.navigation.VinylRoutes
import com.example.vinyllistenapp.ui.theme.VinylListenAppTheme
import org.junit.Rule
import org.junit.Test

class VinylNavigationSmokeTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun homeLogSessionCanReachManualSearch() {
        composeRule.setContent {
            VinylListenAppTheme {
                VinylNavHost(navController = rememberNavController())
            }
        }

        composeRule.onNodeWithText("Log Session").performClick()
        composeRule.onNodeWithText("Capture Record").assertIsDisplayed()

        composeRule.onNodeWithText("Manual Search").performClick()
        composeRule.onNodeWithText("Search for your record manually").assertIsDisplayed()
    }

    @Test
    fun processingSuccessIsRemovedBeforeMatchConfirmation() {
        lateinit var navController: NavHostController
        composeRule.setContent {
            VinylListenAppTheme {
                navController = rememberNavController()
                VinylNavHost(navController = navController)
            }
        }

        composeRule.runOnIdle {
            navController.navigate(VinylRoutes.PROCESSING)
        }
        composeRule.waitUntil(timeoutMillis = 5_000) {
            composeRule.onAllNodes(hasText("Confirm Match")).fetchSemanticsNodes().isNotEmpty()
        }
        composeRule.onNodeWithText("Confirm Match").assertIsDisplayed()

        composeRule.runOnIdle {
            navController.popBackStack()
        }

        composeRule.onNodeWithText("Vinyl Listen").assertIsDisplayed()
    }
}
