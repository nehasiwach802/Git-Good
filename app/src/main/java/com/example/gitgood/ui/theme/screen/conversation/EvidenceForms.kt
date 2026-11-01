package com.example.gitgood.ui.theme.screen.conversation

import androidx.compose.material3.*
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.ui.Modifier
import androidx.compose.runtime.*
import com.example.gitgood.data.backend.BackendSession
import kotlinx.serialization.json.*

private fun JsonObject.text(key: String) = (get(key) as? JsonPrimitive)?.contentOrNull.orEmpty()
private fun JsonObject.rows(key: String) = (get(key) as? JsonArray)?.mapNotNull { it as? JsonObject }.orEmpty()
private fun String.finite() = toDoubleOrNull()?.takeIf { it.isFinite() }

@Composable
internal fun CandidateValues(session: BackendSession, enabled: Boolean, submit: (String, JsonObject) -> Unit) {
    val candidate = session.candidate ?: return
    candidate.rows("components").filter { it.text("part") in setOf("resistor", "capacitor") }.forEach { component ->
        var value by remember(session.candidate_revision, component.text("id")) { mutableStateOf(component.text("value_si").takeUnless { it == "null" }.orEmpty()) }
        OutlinedTextField(value, { value = it }, modifier = Modifier.fillMaxWidth(), enabled = enabled, label = { Text("${component.text("id")} · ${if (component.text("part") == "resistor") "ohms" else "farads"}") })
        TextButton(onClick = {
            val components = candidate.rows("components").map {
                if (it.text("id") == component.text("id")) JsonObject(it + ("value_si" to JsonPrimitive(value.finite()!!))) else it
            }
            submit("replace_candidate", buildJsonObject {
                put("candidate_revision", session.candidate_revision!!)
                put("candidate", JsonObject(candidate + ("components" to JsonArray(components))))
            })
        }, enabled = enabled && (value.finite()?.let { it > 0 } == true)) { Text("Save component value and review again") }
    }
}

@Composable
internal fun CorrespondenceAndSources(session: BackendSession, contract: JsonObject, enabled: Boolean, submit: (String, JsonObject) -> Unit) {
    val candidate = session.candidate ?: return
    val components = candidate.rows("components")
    val ports = candidate.rows("ports")
    val componentMap = remember(session.session_id, session.candidate_revision) { mutableStateMapOf<String, String>() }
    val portMap = remember(session.session_id, session.candidate_revision) { mutableStateMapOf<String, String>() }
    val referenceIds = contract.rows("reference_components").map { it.text("id") }
    val referencePorts = (contract["reference_ports"] as? JsonArray)?.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }.orEmpty()
    if (components.isNotEmpty() && referenceIds.isNotEmpty()) {
        Text("Match observed components to experiment labels: ${referenceIds.joinToString()}. Enter ‘extra’ only for an additional component.")
        components.forEach { component ->
            val id = component.text("id")
            OutlinedTextField(componentMap[id].orEmpty(), { componentMap[id] = it }, modifier = Modifier.fillMaxWidth(), enabled = enabled, label = { Text("$id matches") })
        }
        if (referencePorts.isNotEmpty()) {
            Text("Experiment ports: ${referencePorts.joinToString()}")
            ports.forEach { port ->
                val id = port.text("id")
                OutlinedTextField(portMap[id].orEmpty(), { portMap[id] = it }, modifier = Modifier.fillMaxWidth(), enabled = enabled, label = { Text("Port $id matches") })
            }
        }
        Button(onClick = {
            submit("set_correspondence", buildJsonObject {
                put("component_map", buildJsonObject { componentMap.forEach { (id, target) -> put(id, if (target.trim() == "extra") JsonNull else JsonPrimitive(target.trim())) } })
                put("port_map", buildJsonObject { portMap.filterValues { it.isNotBlank() }.forEach { (id, target) -> put(id, target.trim()) } })
            })
        }, enabled = enabled && components.all { componentMap[it.text("id")]?.trim() in referenceIds + "extra" } && portMap.values.all { it.isBlank() || it.trim() in referencePorts }) { Text("Save label matches") }
    }
    val sources = contract.rows("source_ports").map { it.text("component_id") }.distinct()
    if (sources.isNotEmpty()) {
        val dc = remember(session.session_id) { mutableStateMapOf<String, String>() }
        val ac = remember(session.session_id) { mutableStateMapOf<String, String>() }
        Text("Record the configured source settings. Follow your instructor’s setup instructions.")
        sources.forEach { id ->
            OutlinedTextField(dc[id].orEmpty(), { dc[id] = it }, modifier = Modifier.fillMaxWidth(), enabled = enabled, label = { Text("$id DC (V)") })
            OutlinedTextField(ac[id].orEmpty(), { ac[id] = it }, modifier = Modifier.fillMaxWidth(), enabled = enabled, label = { Text("$id AC amplitude (V)") })
        }
        Button(onClick = {
            submit("source_settings", buildJsonObject {
                put("candidate_revision", session.candidate_revision!!)
                put("sources", buildJsonObject { sources.forEach { id -> put(id, buildJsonObject { put("dc", dc[id]!!.finite()!!); put("ac", ac[id]!!.finite()!!) }) } })
            })
        }, enabled = enabled && sources.all { dc[it]?.finite() != null && ac[it]?.finite() != null }) { Text("Save source settings") }
    }
}

@Composable
internal fun EvidenceForms(session: BackendSession, contract: JsonObject, enabled: Boolean, submit: (String, JsonObject) -> Unit) {
    val analysis = contract["analysis"] as? JsonObject ?: return
    val revision = session.candidate_revision ?: return
    when (analysis.text("engine")) {
        "analog_ac" -> {
            val probes = analysis.rows("probes")
            val readings = remember(session.candidate_revision) { mutableStateMapOf<String, String>() }
            if (probes.isEmpty()) return
            Text("Enter measured AC magnitudes in volts for the specified probes and frequencies. Only take measurements approved by your instructor.")
            probes.forEach { probe ->
                val id = probe.text("id")
                Text("$id: ${probe.text("positive_port")} to ${probe.text("negative_port")}, ${probe.text("frequency_hz")} Hz")
                OutlinedTextField(readings[id].orEmpty(), { readings[id] = it }, modifier = Modifier.fillMaxWidth(), enabled = enabled, label = { Text("$id magnitude (V)") })
            }
            val populated = readings.filterValues { it.isNotBlank() }
            Button(onClick = {
                submit("measurements", buildJsonObject {
                    put("candidate_revision", revision)
                    put("measurements", buildJsonArray { populated.forEach { (id, value) -> add(buildJsonObject { put("probe_id", id); put("value", value.finite()!!); put("unit", "V"); put("convention", "ac_magnitude") }) } })
                })
            }, enabled = enabled && populated.isNotEmpty() && populated.values.all { it.finite()?.let { n -> n >= 0 } == true }) { Text("Submit measurements") }
        }
        "7400_as_not" -> {
            var input by remember(session.candidate_revision) { mutableStateOf("") }
            var output by remember(session.candidate_revision) { mutableStateOf("") }
            OutlinedTextField(input, { input = it }, modifier = Modifier.fillMaxWidth(), enabled = enabled, label = { Text("Observed input (0 or 1)") })
            OutlinedTextField(output, { output = it }, modifier = Modifier.fillMaxWidth(), enabled = enabled, label = { Text("Observed output (0 or 1)") })
            Button(onClick = {
                submit("measurements", buildJsonObject { put("candidate_revision", revision); put("measurements", buildJsonArray { add(buildJsonObject { put("input", input.toInt()); put("output", output.toInt()) }) }) })
            }, enabled = enabled && input in listOf("0", "1") && output in listOf("0", "1")) { Text("Submit observed logic levels") }
        }
    }
}
