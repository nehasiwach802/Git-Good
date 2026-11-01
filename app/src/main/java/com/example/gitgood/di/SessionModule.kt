package com.example.gitgood.di

import com.example.gitgood.data.repository.FakeSessionRepository
import com.example.gitgood.data.repository.SessionRepository
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object SessionModule {
    /** Legacy demo contract only. Android screens inject LiveSessionRepository for the deployed v1.1 API. */
    @Provides @Singleton
    fun provideSessionRepository(): SessionRepository = FakeSessionRepository()
}
