package com.example.gitgood.data.model

import com.example.gitgood.data.backend.BackendExperiment
import kotlinx.serialization.json.JsonObject

enum class ExperimentAvailability { AVAILABLE, DEMO, UNAVAILABLE }

data class Experiment(
    val id: String,
    val name: String,
    val version: String,
    val description: String,
    val backendId: String = id,
    val reviewContract: JsonObject = JsonObject(emptyMap()),
    val availability: ExperimentAvailability = ExperimentAvailability.AVAILABLE
) {
    val canStart get() = availability != ExperimentAvailability.UNAVAILABLE
    val statusLabel get() = when (availability) {
        ExperimentAvailability.AVAILABLE -> "Available"
        ExperimentAvailability.DEMO -> "Demo workflow · synthetic results"
        ExperimentAvailability.UNAVAILABLE -> "Awaiting backend support"
    }
}

val localExperiments = listOf(
    Experiment("not-gate-7400", "NOT Gate Using IC 7400 NAND Gates", "1", "Review the circuit for a NOT gate built using IC 7400 NAND gates."),
    Experiment("ohms-law", "Verification of Ohm’s Law", "1", "Review the relationship between voltage, current, and resistance."),
    Experiment("rc-low-pass-filter", "RC Low-Pass Filter", "1", "Review a resistor-capacitor low-pass filter circuit."),
    Experiment("inverting-op-amp", "Inverting Op-Amp Amplifier", "1", "Review an operational amplifier configured as an inverting amplifier."),
    Experiment("half-wave-rectifier", "Half-Wave Rectifier", "1", "Review a half-wave rectifier circuit."),
    Experiment("simple-wire", "Simple Wire", "1", "Review simple wire connections on a breadboard.")
).map { it.copy(availability = ExperimentAvailability.UNAVAILABLE) }

/** Stable six-item product catalog, with explicit backend availability and provenance. */
fun resolveExperiments(server: List<BackendExperiment>): List<Experiment> = localExperiments.map { item ->
    val matches = server.filter {
        it.experiment_id == item.id || it.name.trim().equals(item.name, ignoreCase = true) ||
            (item.id == "simple-wire" && (
                it.experiment_id == "wire-hole-practice-v1" ||
                    it.name.trim().equals("Wire Connections", ignoreCase = true) ||
                    it.name.trim().equals("Breadboard Wire Connections", ignoreCase = true)
                ))
    }
    // These are explicit demo bindings, never represented as approved real experiments.
    val demoId = when (item.id) {
        "not-gate-7400" -> "nand-not-example"
        "rc-low-pass-filter" -> "rc-lowpass-example"
        else -> null
    }
    val remote = matches.sortedByDescending { it.version.toIntOrNull() ?: 0 }
        .firstOrNull { it.workflow_approved && !it.simulated }
        ?: matches.firstOrNull()
        ?: server.firstOrNull { it.simulated && it.experiment_id == demoId }
    if (remote == null) item else item.copy(
        version = remote.version, backendId = remote.experiment_id,
        reviewContract = remote.review_contract,
        availability = when {
            remote.simulated -> ExperimentAvailability.DEMO
            remote.workflow_approved -> ExperimentAvailability.AVAILABLE
            else -> ExperimentAvailability.UNAVAILABLE
        }
    )
}
