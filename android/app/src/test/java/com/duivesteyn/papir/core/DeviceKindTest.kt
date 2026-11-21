package com.duivesteyn.papir.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

/**
 * The share sheet's mark comes from the device *name* Amazon reports, so these
 * are the names the algorithm has to cope with in the wild: the account's
 * display names, product names with generation suffixes, and app devices that
 * are not Kindles at all.
 */
class DeviceKindTest {

    @Test
    fun `reported device names pick the matching silhouette`() {
        val cases = linkedMapOf(
            "Ben's Kindle Scribe" to DeviceKind.SCRIBE,
            "Kindle Scribe" to DeviceKind.SCRIBE,
            "Ben's Kindle Colorsoft Signature Edition" to DeviceKind.COLORSOFT,
            "Ben's Kindle Paperwhite (11th Generation)" to DeviceKind.PAPERWHITE,
            "Ben's Kindle Oasis (9th Generation)" to DeviceKind.OASIS,
            "Kindle Voyage" to DeviceKind.VOYAGE,
            "Ben's Kindle Keyboard (3rd Generation)" to DeviceKind.KEYBOARD,
            "Kindle DX" to DeviceKind.DX,
            "Kindle DXG" to DeviceKind.DX,
            "Ben's Kindle Touch" to DeviceKind.TOUCH,
            "Ben's Basic Kindle" to DeviceKind.BASIC,
        )
        cases.forEach { (name, expected) ->
            assertEquals(name, expected, DeviceKind.forDeviceName(name))
        }
    }

    @Test
    fun `a Scribe with colour is still a Scribe`() {
        assertEquals(DeviceKind.SCRIBE, DeviceKind.forDeviceName("Kindle Scribe Colorsoft"))
    }

    @Test
    fun `run-together and oddly punctuated spellings still match`() {
        assertEquals(DeviceKind.PAPERWHITE, DeviceKind.forDeviceName("KindlePaperwhite"))
        assertEquals(DeviceKind.PAPERWHITE, DeviceKind.forDeviceName("kindle paper-white"))
        assertEquals(DeviceKind.COLORSOFT, DeviceKind.forDeviceName("kindle colour soft"))
    }

    @Test
    fun `devices Papir cannot place get the generic slab`() {
        listOf(
            "Ben's Kindle (2019)",
            "Ben's 2nd Kindle",
            "Fire HD 10",
            "Kindle for iPad",
            "iPhone",
            "",
            "   ",
        ).forEach { name ->
            assertEquals(name, DeviceKind.GENERIC, DeviceKind.forDeviceName(name))
        }
        assertEquals(DeviceKind.GENERIC, DeviceKind.forDeviceName(null))
    }

    @Test
    fun `no device name ever asks for the papir default`() {
        listOf("Ben's Kindle Scribe", "Kindle", "", "iPad").forEach { name ->
            assertNotEquals(name, DeviceKind.PAPIR, DeviceKind.forDeviceName(name))
        }
    }

    @Test
    fun `every silhouette has a distinct resource slug and alias`() {
        val slugs = DeviceKind.entries.map { it.slug }
        val aliases = DeviceKind.entries.map { it.alias }
        assertEquals(slugs.size, slugs.toSet().size)
        assertEquals(aliases.size, aliases.toSet().size)
    }
}
