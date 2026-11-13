package com.duivesteyn.papir.core

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * The fixture digests come from `papir/signer.py`. A match means the Android
 * port signs exactly what Amazon already accepts from the CLI.
 */
class SignerTest {

    @Test
    fun `PKCS#1 key produces the Python signature`() {
        assertEquals(
            Fixtures.EXPECTED_DIGEST,
            Signer.digestHeader(
                Fixtures.PKCS1_KEY,
                Fixtures.ADP_TOKEN,
                Fixtures.METHOD,
                Fixtures.PATH,
                Fixtures.BODY,
                Fixtures.DATE,
            ),
        )
    }

    @Test
    fun `PKCS#8 key produces the same signature`() {
        assertEquals(
            Fixtures.EXPECTED_DIGEST,
            Signer.digestHeader(
                Fixtures.PKCS8_KEY,
                Fixtures.ADP_TOKEN,
                Fixtures.METHOD,
                Fixtures.PATH,
                Fixtures.BODY,
                Fixtures.DATE,
            ),
        )
    }

    @Test
    fun `signing date is UTC with whole seconds`() {
        assertEquals("1970-01-01T00:00:00Z", Signer.signingDate(0L))
    }

    @Test(expected = IllegalArgumentException::class)
    fun `a non-key PEM is rejected`() {
        Signer.digestHeader("not a key", "token", "POST", "/x", "{}", Fixtures.DATE)
    }
}
