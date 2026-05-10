package com.example.vinyllistenapp.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.vinyllistenapp.domain.RecordSummary
import com.example.vinyllistenapp.ui.components.AccentCard
import com.example.vinyllistenapp.ui.components.AlbumArtBlock
import com.example.vinyllistenapp.ui.components.CaptureCircleButton
import com.example.vinyllistenapp.ui.components.GlassPrimaryButton
import com.example.vinyllistenapp.ui.theme.VinylColors
import com.example.vinyllistenapp.ui.theme.VinylShapes
import com.example.vinyllistenapp.ui.theme.VinylSpacing

@Composable
fun ManualSearchScreen(
    records: List<RecordSummary>,
    onSelectRecord: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    var artistQuery by remember { mutableStateOf("") }
    var titleQuery by remember { mutableStateOf("") }
    var catalogQuery by remember { mutableStateOf("") }
    var yearQuery by remember { mutableStateOf("") }

    Column(
        modifier =
            Modifier
                .fillMaxSize()
                .background(VinylColors.AppBackground)
                .padding(horizontal = VinylSpacing.SpaceXl),
    ) {
        ManualSearchHeader(onDismiss = onDismiss)
        Text(
            modifier = Modifier.fillMaxWidth(),
            text = "Search for your record manually",
            color = VinylColors.TextSecondary,
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.bodyMedium,
        )
        Spacer(Modifier.height(VinylSpacing.SpaceLg))
        Column(
            verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
        ) {
            ManualSearchField(
                label = "Artist",
                placeholder = "Search by artist name",
                value = artistQuery,
                onValueChange = { artistQuery = it },
            )
            ManualSearchField(
                label = "Title",
                placeholder = "Search by album title",
                value = titleQuery,
                onValueChange = { titleQuery = it },
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
            ) {
                ManualSearchField(
                    label = "Catalog Number",
                    placeholder = "Cat #",
                    value = catalogQuery,
                    onValueChange = { catalogQuery = it },
                    modifier = Modifier.weight(1f),
                )
                ManualSearchField(
                    label = "Year",
                    placeholder = "Year",
                    value = yearQuery,
                    onValueChange = { yearQuery = it },
                    modifier = Modifier.weight(1f),
                )
            }
        }
        Spacer(Modifier.height(VinylSpacing.SpaceLg))
        GlassPrimaryButton("Search", onClick = {})
        Spacer(Modifier.height(VinylSpacing.SpaceXl))
        Text(
            text = "Results",
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.bodyMedium,
        )
        Spacer(Modifier.height(VinylSpacing.SpaceMd))
        Column(
            modifier =
                Modifier
                    .weight(1f)
                    .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceMd),
        ) {
            records.forEach { record ->
                ManualSearchResultRow(record = record, onClick = { onSelectRecord(record.releaseId) })
            }
            Spacer(Modifier.height(VinylSpacing.SpaceXl))
        }
    }
}

@Composable
private fun ManualSearchHeader(onDismiss: () -> Unit) {
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .padding(top = 48.dp, bottom = VinylSpacing.SpaceLg),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        CaptureCircleButton(label = "X", onClick = onDismiss)
        Text(
            text = "Manual Search",
            color = VinylColors.TextPrimary,
            style = MaterialTheme.typography.titleMedium,
        )
        Spacer(Modifier.width(40.dp))
    }
}

@Composable
private fun ManualSearchField(
    label: String,
    placeholder: String,
    value: String,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
    ) {
        Text(
            text = label,
            color = VinylColors.TextSecondary,
            style = MaterialTheme.typography.bodyMedium.copy(fontSize = 12.sp, lineHeight = 14.sp),
        )
        Box(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .height(48.dp)
                    .clip(VinylShapes.Card)
                    .background(VinylColors.SurfacePrimary)
                    .border(1.dp, VinylColors.BorderDefault, VinylShapes.Card)
                    .padding(horizontal = VinylSpacing.SpaceLg),
            contentAlignment = Alignment.CenterStart,
        ) {
            BasicTextField(
                value = value,
                onValueChange = onValueChange,
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                textStyle =
                    MaterialTheme.typography.bodyMedium.copy(
                        color = VinylColors.TextPrimary,
                    ),
                cursorBrush = SolidColor(VinylColors.AccentGreen),
                decorationBox = { innerTextField ->
                    if (value.isEmpty()) {
                        Text(
                            text = placeholder,
                            color = VinylColors.TextSecondary,
                            style = MaterialTheme.typography.bodyMedium,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    innerTextField()
                },
            )
        }
    }
}

@Composable
private fun ManualSearchResultRow(
    record: RecordSummary,
    onClick: () -> Unit,
) {
    AccentCard(
        modifier = Modifier.clickable(onClick = onClick),
    ) {
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(vertical = VinylSpacing.SpaceXs),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            AlbumArtBlock(accentColor = VinylColors.AccentGreen, compact = true)
            Spacer(Modifier.width(VinylSpacing.SpaceMd))
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceXs),
            ) {
                Text(
                    text = record.artist,
                    color = VinylColors.TextPrimary,
                    style = MaterialTheme.typography.bodyLarge,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = record.title,
                    color = VinylColors.TextSecondary,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Row(
                    horizontalArrangement = Arrangement.spacedBy(VinylSpacing.SpaceSm),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = record.year.toString(),
                        color = VinylColors.TextSecondary,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Text(
                        text = "-",
                        color = VinylColors.BorderDefault,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Text(
                        text = record.label,
                        color = VinylColors.TextSecondary,
                        style = MaterialTheme.typography.bodyMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
    }
}
