package com.example.gitgood.di

import com.example.gitgood.data.backend.*
import com.google.firebase.auth.FirebaseAuth
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import kotlinx.coroutines.tasks.await
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object BackendModule {
    @Provides @Singleton
    fun tokens(auth: FirebaseAuth): IdTokenProvider = object : IdTokenProvider {
        override val userId get() = auth.currentUser?.uid
        override suspend fun token(forceRefresh: Boolean): String =
            auth.currentUser?.getIdToken(forceRefresh)?.await()?.token
                ?: error("Please sign in again.")
    }

    @Provides @Singleton
    fun client(tokens: IdTokenProvider): BackendHttpClient = BackendHttpClient(tokens)

    @Provides @Singleton
    fun sessions(repository: LiveSessionRepository): SessionApi = repository

    @Provides @Singleton
    fun videos(store: AndroidSessionVideoStore): SessionVideoStore = store
}
