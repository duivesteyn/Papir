package com.duivesteyn.papir.core

import java.security.MessageDigest
import java.security.SecureRandom
import java.util.Base64

/**
 * PKCE helpers and per-install identifiers, matching papir's Python core.
 *
 * The verifier is 32 random bytes, base64url without padding — the same shape
 * the desktop app uses, so Amazon sees nothing unusual about the phone.
 */
object Pkce {

    private val random = SecureRandom()

    fun verifier(): String = b64url(ByteArray(32).also(random::nextBytes))

    fun challenge(verifier: String): String = b64url(
        MessageDigest.getInstance("SHA-256").digest(verifier.toByteArray(Charsets.US_ASCII))
    )

    /** 32 upper-hex characters, stored for the life of the install. */
    fun serial(): String {
        val bytes = ByteArray(16).also(random::nextBytes)
        return bytes.joinToString("") { "%02X".format(it.toInt() and 0xFF) }
    }

    private fun b64url(bytes: ByteArray): String =
        Base64.getUrlEncoder().withoutPadding().encodeToString(bytes)
}
