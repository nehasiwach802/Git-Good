package com.example.gitgood.data.model

import com.example.gitgood.data.backend.BackendExperiment
import org.junit.Assert.*
import org.junit.Test

class ExperimentCatalogTest {
    @Test fun allFiveRemainVisibleWithoutPublishedWorkflows() {
        val catalog = resolveExperiments(emptyList())
        assertEquals(listOf("not-gate-7400", "ohms-law", "rc-low-pass-filter", "inverting-op-amp", "half-wave-rectifier"), catalog.map { it.id })
        assertTrue(catalog.none { it.canStart })
    }
    @Test fun twoKnownDemosRetainExactServerIdsAndVersions() {
        val catalog = resolveExperiments(listOf(
            BackendExperiment("nand-not-example", "3", "NAND example", simulated = true),
            BackendExperiment("rc-lowpass-example", "2", "RC example", simulated = true)
        ))
        val demos = catalog.filter { it.canStart }
        assertEquals(2, demos.size)
        assertTrue(demos.all { it.availability == ExperimentAvailability.DEMO })
        assertEquals("nand-not-example", demos[0].backendId)
        assertEquals("3", demos[0].version)
        assertEquals("rc-lowpass-example", demos[1].backendId)
        assertEquals("RC Low-Pass Filter", demos[1].name)
    }
    @Test fun publishedRealWorkflowTakesPrecedenceOverDemo() {
        val rc = resolveExperiments(listOf(
            BackendExperiment("rc-lowpass-example", "2", "RC example", simulated = true),
            BackendExperiment("rc-low-pass-filter", "7", "RC Low-Pass Filter", workflow_approved = true)
        )).single { it.id == "rc-low-pass-filter" }
        assertEquals(ExperimentAvailability.AVAILABLE, rc.availability)
        assertEquals("rc-low-pass-filter", rc.backendId)
        assertEquals("7", rc.version)
    }
    @Test fun unrelatedSyntheticWorkflowIsNotAliasedToMissingExperiment() {
        val catalog = resolveExperiments(listOf(BackendExperiment("random-demo", "1", "Unknown", simulated = true)))
        assertTrue(catalog.none { it.canStart })
    }
    @Test fun unapprovedRealWorkflowRemainsUnavailable() {
        val ohms = resolveExperiments(listOf(BackendExperiment("ohms-law", "1", "Verification of Ohm’s Law")))
            .single { it.id == "ohms-law" }
        assertFalse(ohms.canStart)
    }
}
