package com.example.vinyllistenapp.data.auth

import android.content.Context
import android.content.SharedPreferences
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.nio.charset.StandardCharsets
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

interface AuthSessionStore {
    fun loadRefreshToken(): String?

    fun loadAccountEmail(): String?

    fun saveTokenPair(
        tokenPair: AuthTokenPair,
        accountEmail: String? = null,
    )

    fun clear()
}

class EncryptedAuthSessionStore(
    context: Context,
) : AuthSessionStore {
    private val preferences =
        context.applicationContext.getSharedPreferences(AUTH_SESSION_PREFS, Context.MODE_PRIVATE)

    override fun loadRefreshToken(): String? {
        val encryptedToken = preferences.getString(KEY_REFRESH_TOKEN_ENCRYPTED, null)
        if (encryptedToken != null) {
            return runCatching { decrypt(encryptedToken).takeIf { it.isNotBlank() } }
                .getOrElse {
                    clear()
                    null
                }
        }

        return migratePlaintextRefreshToken()
    }

    override fun loadAccountEmail(): String? =
        preferences.getString(KEY_ACCOUNT_EMAIL_ENCRYPTED, null)?.let { encryptedEmail ->
            runCatching { decrypt(encryptedEmail).takeIf { it.isNotBlank() } }
                .getOrElse {
                    clear()
                    null
                }
        }

    override fun saveTokenPair(
        tokenPair: AuthTokenPair,
        accountEmail: String?,
    ) {
        saveEncryptedSession(
            refreshToken = tokenPair.refreshToken,
            refreshExpiresAt = tokenPair.refreshExpiresAt,
            sessionId = tokenPair.sessionId,
            accountEmail = accountEmail,
        )
    }

    override fun clear() {
        preferences.edit().clear().apply()
    }

    private fun migratePlaintextRefreshToken(): String? {
        val refreshToken =
            preferences
                .getString(KEY_REFRESH_TOKEN, null)
                ?.takeIf { it.isNotBlank() }
                ?: return null

        return runCatching {
            saveEncryptedSession(
                refreshToken = refreshToken,
                refreshExpiresAt = preferences.getString(KEY_REFRESH_EXPIRES_AT, null),
                sessionId = preferences.getString(KEY_SESSION_ID, null),
            )
            refreshToken
        }.getOrElse {
            clear()
            null
        }
    }

    private fun saveEncryptedSession(
        refreshToken: String,
        refreshExpiresAt: String?,
        sessionId: String?,
        accountEmail: String? = null,
    ) {
        val editor =
            preferences
                .edit()
                .putString(KEY_REFRESH_TOKEN_ENCRYPTED, encrypt(refreshToken))
                .putEncryptedOptionalString(KEY_REFRESH_EXPIRES_AT_ENCRYPTED, refreshExpiresAt)
                .putEncryptedOptionalString(KEY_SESSION_ID_ENCRYPTED, sessionId)
                .remove(KEY_REFRESH_TOKEN)
                .remove(KEY_REFRESH_EXPIRES_AT)
                .remove(KEY_SESSION_ID)
        accountEmail?.trim()?.takeIf { it.isNotBlank() }?.let { email ->
            editor.putString(KEY_ACCOUNT_EMAIL_ENCRYPTED, encrypt(email))
        }
        editor.apply()
    }

    private fun SharedPreferences.Editor.putEncryptedOptionalString(
        key: String,
        value: String?,
    ): SharedPreferences.Editor =
        if (value.isNullOrBlank()) {
            remove(key)
        } else {
            putString(key, encrypt(value))
        }

    private fun encrypt(value: String): String {
        val cipher = Cipher.getInstance(KEY_TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateSecretKey())
        val ciphertext = cipher.doFinal(value.toByteArray(StandardCharsets.UTF_8))
        return "${cipher.iv.toBase64()}:${ciphertext.toBase64()}"
    }

    private fun decrypt(value: String): String {
        val parts = value.split(":", limit = 2)
        require(parts.size == 2) { "Invalid encrypted auth value." }
        val iv = Base64.decode(parts[0], Base64.NO_WRAP)
        val ciphertext = Base64.decode(parts[1], Base64.NO_WRAP)
        val cipher = Cipher.getInstance(KEY_TRANSFORMATION)
        cipher.init(Cipher.DECRYPT_MODE, getOrCreateSecretKey(), GCMParameterSpec(GCM_TAG_BITS, iv))
        return String(cipher.doFinal(ciphertext), StandardCharsets.UTF_8)
    }

    private fun getOrCreateSecretKey(): SecretKey {
        val keyStore =
            KeyStore.getInstance(ANDROID_KEYSTORE).apply {
                load(null)
            }
        (keyStore.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }

        val keyGenerator =
            KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE)
        val keySpec =
            KeyGenParameterSpec
                .Builder(KEY_ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(KEY_SIZE_BITS)
                .setRandomizedEncryptionRequired(true)
                .build()
        keyGenerator.init(keySpec)
        return keyGenerator.generateKey()
    }

    private fun ByteArray.toBase64(): String = Base64.encodeToString(this, Base64.NO_WRAP)

    private companion object {
        const val ANDROID_KEYSTORE = "AndroidKeyStore"
        const val AUTH_SESSION_PREFS = "vinyl_auth_session"
        const val GCM_TAG_BITS = 128
        const val KEY_ALIAS = "vinyl_listen_auth_session_key"
        const val KEY_SIZE_BITS = 256
        const val KEY_TRANSFORMATION = "AES/GCM/NoPadding"
        const val KEY_REFRESH_TOKEN_ENCRYPTED = "refresh_token_encrypted"
        const val KEY_REFRESH_EXPIRES_AT_ENCRYPTED = "refresh_expires_at_encrypted"
        const val KEY_SESSION_ID_ENCRYPTED = "session_id_encrypted"
        const val KEY_ACCOUNT_EMAIL_ENCRYPTED = "account_email_encrypted"
        const val KEY_REFRESH_TOKEN = "refresh_token"
        const val KEY_REFRESH_EXPIRES_AT = "refresh_expires_at"
        const val KEY_SESSION_ID = "session_id"
    }
}
