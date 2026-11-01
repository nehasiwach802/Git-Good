
package com.example.gitgood.ui.theme.screen.experiment

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.tooling.preview.Preview
import com.example.gitgood.data.model.Experiment
import com.example.gitgood.data.model.localExperiments
import com.example.gitgood.ui.theme.*

@Composable
fun ExperimentScreen(
    experiments: List<Experiment>,
    selectedId: String?,
    onSelect: (String) -> Unit,
    onContinue: () -> Unit,
    modifier: Modifier = Modifier,
    loading: Boolean = false,
    error: String? = null,
    onRetry: () -> Unit = {},
    onSignInAgain: (() -> Unit)? = null
) {
    val canContinue = !loading &&
            error == null &&
            experiments.any { it.id == selectedId && it.canStart }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(BackgroundColor)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 28.dp)
            .padding(top = 10.dp, bottom = 24.dp),
        verticalArrangement = Arrangement.spacedBy(24.dp)
    ) {

        // App name
        Text(
            text = "Circuitly",
            modifier = Modifier.align(Alignment.End),
            fontSize = 16.sp,
            fontWeight = FontWeight.SemiBold,
            letterSpacing = (-0.4).sp,
            color = PrimaryGreen
        )

        // Heading
        Column(
            modifier = Modifier.padding(top = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                text = "Choose an experiment.",
                fontSize = 34.sp,
                lineHeight = 40.sp,
                fontWeight = FontWeight.Medium,
                letterSpacing = (-1.3).sp,
                color = PrimaryTextColor
            )

            Text(
                text = "Select what you're working on. Next, upload or record a circuit video and add a description.",
                fontSize = 15.sp,
                lineHeight = 22.sp,
                color = SecondaryTextColor
            )
        }

        // Information banner
        Surface(
            color = LightGreen,
            shape = RoundedCornerShape(12.dp)
        ) {
            Text(
                text = "Choose from five experiments. Available demos are labeled; other workflows will unlock when the backend supports them.",
                modifier = Modifier.padding(14.dp),
                fontSize = 13.sp,
                lineHeight = 19.sp,
                color = PrimaryGreen
            )
        }

        // Loading state
        if (loading) {
            Box(
                modifier = Modifier.fillMaxWidth(),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(
                    color = PrimaryGreen
                )
            }
        }

        // Error state
        if (error != null) {
            Column(
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text(
                    text = error,
                    color = MaterialTheme.colorScheme.error,
                    fontSize = 14.sp
                )

                onSignInAgain?.let { signInAgain ->
                    Button(onClick = signInAgain, enabled = !loading,
                        colors = ButtonDefaults.buttonColors(containerColor = PrimaryGreen)) {
                        Text("Sign in again")
                    }
                }
                TextButton(
                    onClick = onRetry,
                    enabled = !loading
                ) {
                    Text("Retry")
                }
            }
        }

        // Experiment list
        if (!loading && experiments.isEmpty() && error == null) {
            Text(
                text = "No experiments available right now. Please try again later.",
                fontSize = 14.sp,
                color = SecondaryTextColor
            )
        }

        Column(
            modifier = Modifier.selectableGroup(),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            experiments.forEach { experiment ->

                val selected = selectedId == experiment.id

                Surface(
                    shape = RoundedCornerShape(14.dp),
                    color = if (selected) {
                        LightGreen
                    } else {
                        MaterialTheme.colorScheme.surface
                    },
                    border = BorderStroke(
                        1.dp,
                        if (selected) PrimaryGreen else BorderColor
                    )
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .selectable(
                                selected = selected,
                                enabled = !loading && error == null,
                                role = Role.RadioButton,
                                onClick = {
                                    onSelect(experiment.id)
                                }
                            )
                            .padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {

                        Column(
                            modifier = Modifier.weight(1f),
                            verticalArrangement = Arrangement.spacedBy(7.dp)
                        ) {
                            Text(
                                text = experiment.name,
                                fontSize = 16.sp,
                                fontWeight = FontWeight.Medium,
                                color = PrimaryTextColor
                            )

                            Text(
                                text = experiment.description,
                                fontSize = 13.sp,
                                lineHeight = 19.sp,
                                color = SecondaryTextColor
                            )

                            Text(
                                text = experiment.statusLabel,
                                fontSize = 11.sp,
                                color = SecondaryTextColor
                            )
                        }

                        RadioButton(
                            selected = selected,
                            onClick = null,
                            enabled = !loading && error == null,
                            colors = RadioButtonDefaults.colors(
                                selectedColor = PrimaryGreen
                            )
                        )
                    }
                }
            }
        }

        experiments.find { it.id == selectedId }?.takeIf { !it.canStart }?.let {
            Text("This experiment is listed, but its analysis workflow has not been published by the backend yet.",
                color = SecondaryTextColor, fontSize = 13.sp)
        }

        // Continue button
        Button(
            onClick = onContinue,
            enabled = canContinue,
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 54.dp),
            shape = RoundedCornerShape(14.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = PrimaryGreen
            )
        ) {
            Text(
                text = "Continue",
                fontSize = 15.sp,
                fontWeight = FontWeight.SemiBold
            )
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun ExperimentScreenPreview() {
    GitGoodTheme {
        ExperimentScreen(
            experiments = localExperiments,
            selectedId = "ohms-law",
            onSelect = {},
            onContinue = {}
        )
    }
}

