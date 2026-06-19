package com.example.vinyllistenapp.data.auth

import android.content.Context

interface AuthSessionStore {
    fun loadRefreshToken(): String?

    fun saveTokenPair(tokenPair: AuthTokenPair)

    fun clear()
}

class SharedPreferencesAuthSessionStore(
    context: Context,
) : AuthSessionStore {
    private val preferences =
        context.applicationContext.getSharedPreferences(AUTH_SESSION_PREFS, Context.MODE_PRIVATE)

    override fun loadRefreshToken(): String? = preferences.getString(KEY_REFRESH_TOKEN, null)?.takeIf { it.isNotBlank() }

    override fun saveTokenPair(tokenPair: AuthTokenPair) {
        preferences
            .edit()
            .putString(KEY_REFRESH_TOKEN, tokenPair.refreshToken)
            .putString(KEY_REFRESH_EXPIRES_AT, tokenPair.refreshExpiresAt)
            .putString(KEY_SESSION_ID, tokenPair.sessionId)
            .apply()
    }

    override fun clear() {
        preferences.edit().clear().apply()
    }

    private companion object {
        const val AUTH_SESSION_PREFS = "vinyl_auth_session"
        const val KEY_REFRESH_TOKEN = "refresh_token"
        const val KEY_REFRESH_EXPIRES_AT = "refresh_expires_at"
        const val KEY_SESSION_ID = "session_id"
    }
}
