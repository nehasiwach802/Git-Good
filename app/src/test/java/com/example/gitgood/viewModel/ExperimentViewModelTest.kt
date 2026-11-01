package com.example.gitgood.viewModel

import androidx.lifecycle.SavedStateHandle
import com.example.gitgood.data.backend.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ExperimentViewModelTest {
    private val dispatcher = StandardTestDispatcher()
    private val api = CatalogApi()
    @Before fun setup() { Dispatchers.setMain(dispatcher) }
    @After fun cleanup() { Dispatchers.resetMain() }

    @Test fun rejectedTokenOffersSignInRecoveryAndClearsCatalog() = runTest(dispatcher) {
        val vm = ExperimentViewModel(SavedStateHandle(), api)
        vm.refresh(); runCurrent()
        vm.select("rc-low-pass-filter")
        api.failure = BackendException(401, "Valid Firebase ID token required")
        vm.refresh(); runCurrent()
        assertTrue(vm.requiresSignIn.value)
        assertNull(vm.selectedId.value)
        assertEquals(5, vm.experiments.value.size)
        assertTrue(vm.experiments.value.none { it.canStart })
        assertTrue(vm.error.value!!.contains("after refreshing"))
    }
    @Test fun successfulRetryClearsAuthenticationFailure() = runTest(dispatcher) {
        api.failure = BackendException(401, "Rejected")
        val vm = ExperimentViewModel(SavedStateHandle(), api)
        vm.refresh(); runCurrent()
        api.failure = null
        vm.refresh(); runCurrent()
        assertFalse(vm.requiresSignIn.value)
        assertNull(vm.error.value)
        assertEquals(5, vm.experiments.value.size)
        assertTrue(vm.experiments.value.single { it.id == "rc-low-pass-filter" }.canStart)
    }
    @Test fun networkFailureDoesNotAskUserToSignOut() = runTest(dispatcher) {
        api.failure = java.io.IOException("No connection")
        val vm = ExperimentViewModel(SavedStateHandle(), api)
        vm.refresh(); runCurrent()
        assertFalse(vm.requiresSignIn.value)
        assertEquals("No connection", vm.error.value)
    }
    private class CatalogApi : SessionApi {
        var failure: Exception? = null
        override suspend fun experiments(): List<BackendExperiment> {
            failure?.let { throw it }
            return listOf(BackendExperiment("rc-low-pass-filter", "1", "RC", workflow_approved = true))
        }
        override suspend fun create(request: CreateSession, key: String): BackendSession = error("Unused")
        override suspend fun get(id: String): BackendSession = error("Unused")
        override suspend fun event(id: String, event: BackendEvent): BackendSession = error("Unused")
        override suspend fun upload(id: String, version: Int, bytes: ByteArray, mime: String, key: String): BackendSession = error("Unused")
    }
}
