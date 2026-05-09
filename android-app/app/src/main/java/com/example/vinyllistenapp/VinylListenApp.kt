package com.example.vinyllistenapp

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.navigation.compose.rememberNavController
import com.example.vinyllistenapp.navigation.VinylNavHost

@Composable
fun VinylListenApp(modifier: Modifier = Modifier) {
    val navController = rememberNavController()

    VinylNavHost(
        navController = navController,
        modifier = modifier,
    )
}
