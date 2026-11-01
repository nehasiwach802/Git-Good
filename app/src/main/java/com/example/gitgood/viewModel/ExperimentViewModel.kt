package com.example.gitgood.viewModel

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.gitgood.data.backend.SessionApi
import com.example.gitgood.data.backend.BackendException
import com.example.gitgood.data.model.Experiment
import com.example.gitgood.data.model.localExperiments
import com.example.gitgood.data.model.resolveExperiments
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class ExperimentViewModel @Inject constructor(private val savedState: SavedStateHandle, private val repository: SessionApi) : ViewModel() {
    val experiments = MutableStateFlow(localExperiments)
    val loading = MutableStateFlow(false)
    val error = MutableStateFlow<String?>(null)
    val requiresSignIn = MutableStateFlow(false)
    val selectedId = savedState.getStateFlow<String?>("experimentId", null)
    val selectedExperiment get() = experiments.value.find { it.id == selectedId.value }
    private var generation = 0

    fun refresh() {
        if (loading.value) return
        val requestGeneration = generation
        loading.value = true
        viewModelScope.launch {
            try {
                val catalog = resolveExperiments(repository.experiments())
                if (generation == requestGeneration) {
                    experiments.value = catalog
                    requiresSignIn.value = false
                    error.value = null
                }
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) {
                if (generation == requestGeneration) {
                    requiresSignIn.value = e is BackendException && e.status == 401
                    if (requiresSignIn.value) {
                        experiments.value = localExperiments
                        savedState["experimentId"] = null
                        error.value = "The server rejected your Firebase sign-in after refreshing it. Sign in again. If this continues, the server’s Firebase configuration needs checking."
                    } else error.value = e.message ?: "Could not load experiments."
                }
            } finally { if (generation == requestGeneration) loading.value = false }
        }
    }
    fun select(id: String) { if (experiments.value.any { it.id == id }) savedState["experimentId"] = id }
    fun clear() { generation++; savedState["experimentId"] = null; experiments.value = localExperiments; loading.value = false; error.value = null; requiresSignIn.value = false }
}
