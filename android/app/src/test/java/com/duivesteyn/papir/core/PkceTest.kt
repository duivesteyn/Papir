package com.duivesteyn.papir.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PkceTest {

    @Test
    fun `challenge matches the reference implementation`() {
        assertEquals(Fixtures.EXPECTED_CHALLENGE, Pkce.challenge(Fixtures.VERIFIER))
    }

    @Test
    fun `verifier is URL-safe base64 of 32 bytes`() {
        val verifier = Pkce.verifier()
        assertEquals(43, verifier.length)
        assertTrue(verifier.matches(Regex("[A-Za-z0-9_-]+")))
        assertNotEquals(verifier, Pkce.verifier())
    }

    @Test
    fun `serial is 32 upper-case hex characters`() {
        assertTrue(Pkce.serial().matches(Regex("[0-9A-F]{32}")))
    }
}
