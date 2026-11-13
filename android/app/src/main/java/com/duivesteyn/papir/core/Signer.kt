package com.duivesteyn.papir.core

import java.math.BigInteger
import java.security.MessageDigest
import java.time.Instant
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Arrays
import java.util.Base64

/**
 * Amazon ADP request signing — the exact scheme papir's Python signer uses:
 * PKCS#1 v1.5 over a BARE SHA-256 digest (no ASN.1 DigestInfo prefix).
 *
 * A standard "SHA256withRSA" signature gets an opaque 403 from Amazon, so the
 * padding block is assembled by hand, as in `papir/signer.py`.
 */
object Signer {

    private val DATE_FORMAT: DateTimeFormatter =
        DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss'Z'").withZone(ZoneOffset.UTC)

    fun signingDate(epochMillis: Long = System.currentTimeMillis()): String =
        DATE_FORMAT.format(Instant.ofEpochMilli(epochMillis))

    /**
     * Build the `X-ADP-Request-Digest` value: base64(signature) + ":" + signing date.
     */
    fun digestHeader(
        pemPrivateKey: String,
        adpToken: String,
        method: String,
        path: String,
        postData: String,
        signingDate: String = signingDate(),
    ): String {
        val signed = "$method\n$path\n$signingDate\n$postData\n$adpToken"
        val digest = MessageDigest.getInstance("SHA-256").digest(signed.toByteArray(Charsets.UTF_8))
        val key = RsaPrivateKey.fromPem(pemPrivateKey)
        val size = (key.modulus.bitLength() + 7) / 8
        val paddingLength = size - 3 - digest.size
        require(paddingLength >= 8) { "RSA key too small for a SHA-256 signature" }

        // EM = 0x00 0x01 0xFF..FF 0x00 || digest
        val encoded = ByteArray(size)
        encoded[0] = 0
        encoded[1] = 1
        Arrays.fill(encoded, 2, 2 + paddingLength, 0xFF.toByte())
        encoded[2 + paddingLength] = 0
        System.arraycopy(digest, 0, encoded, 3 + paddingLength, digest.size)

        val signature = BigInteger(1, encoded).modPow(key.privateExponent, key.modulus).toByteArray()
        val fixed = ByteArray(size)
        if (signature.size > size) {
            System.arraycopy(signature, signature.size - size, fixed, 0, size)
        } else {
            System.arraycopy(signature, 0, fixed, size - signature.size, signature.size)
        }
        return Base64.getEncoder().encodeToString(fixed) + ":" + signingDate
    }
}

/** Minimal DER reader: enough for PKCS#1 and PKCS#8 RSA private keys. */
private class RsaPrivateKey(val modulus: BigInteger, val privateExponent: BigInteger) {

    companion object {
        fun fromPem(pem: String): RsaPrivateKey {
            val body = pem.lineSequence()
                .filterNot { it.contains("-----") }
                .joinToString("")
                .trim()
            val der = try {
                Base64.getDecoder().decode(body)
            } catch (e: IllegalArgumentException) {
                throw IllegalArgumentException("not a base64 PEM private key", e)
            }
            val integers = if (isPkcs8(der)) parsePkcs1Inner(der) else parseIntegers(der)
            require(integers.size >= 4) { "truncated RSA private key" }
            return RsaPrivateKey(integers[1], integers[3])
        }

        private fun isPkcs8(der: ByteArray): Boolean {
            val outer = readTlv(der, 0)
            if (outer.tag != 0x30) return false
            val first = readTlv(outer.value, 0)
            if (first.tag != 0x02) return false
            if (first.end >= outer.value.size) return false
            return readTlv(outer.value, first.end).tag == 0x30 // AlgorithmIdentifier
        }

        private fun parsePkcs1Inner(der: ByteArray): List<BigInteger> {
            val outer = readTlv(der, 0)
            var pos = 0
            while (pos < outer.value.size) {
                val tlv = readTlv(outer.value, pos)
                if (tlv.tag == 0x04) return parseIntegers(tlv.value)
                pos = tlv.end
            }
            throw IllegalArgumentException("could not find inner PKCS#1 key in PKCS#8")
        }

        private fun parseIntegers(der: ByteArray): List<BigInteger> {
            val outer = readTlv(der, 0)
            require(outer.tag == 0x30) { "not a PKCS#1 SEQUENCE" }
            val integers = ArrayList<BigInteger>()
            var pos = 0
            while (pos < outer.value.size) {
                val tlv = readTlv(outer.value, pos)
                require(tlv.tag == 0x02) { "expected INTEGER in private key" }
                integers.add(BigInteger(1, tlv.value))
                pos = tlv.end
            }
            return integers
        }

        private class Tlv(val tag: Int, val value: ByteArray, val end: Int)

        private fun readTlv(buf: ByteArray, offset: Int): Tlv {
            var pos = offset
            val tag = buf[pos++].toInt() and 0xFF
            var length = buf[pos++].toInt() and 0xFF
            if (length and 0x80 != 0) {
                val count = length and 0x7F
                require(count in 1..3) { "unsupported DER length" }
                length = 0
                repeat(count) { length = (length shl 8) or (buf[pos++].toInt() and 0xFF) }
            }
            require(length >= 0 && pos + length <= buf.size) { "truncated DER" }
            return Tlv(tag, buf.copyOfRange(pos, pos + length), pos + length)
        }
    }
}
