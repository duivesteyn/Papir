package com.duivesteyn.papir.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory

/**
 * The share-sheet icon only works if the manifest keeps its promise: one
 * `<activity-alias>` per [DeviceKind], all carrying the same intent filter, all
 * over the same activity, and exactly one enabled out of the box.
 *
 * The alias blocks are long and hand-maintained, so this test is the thing that
 * notices when a MIME type is added to one of them and forgotten in the other
 * ten, or when a new silhouette is added to the enum without its alias.
 */
class ManifestTest {

    private val manifest = manifestFile()

    @Test
    fun `there is one alias per device kind`() {
        val aliases = aliases()
        val names = aliases.map { it.attribute("android:name") }.toSet()
        DeviceKind.entries.forEach { kind ->
            val expected = ".share.ShareTarget${kind.alias}"
            assertTrue("missing alias $expected", expected in names)
        }
        assertEquals(DeviceKind.entries.size, aliases.size)
    }

    @Test
    fun `every alias carries the same intent filter`() {
        val filters = aliases().map { it.filterSignature() }.toSet()
        assertEquals("aliases disagree on their intent filters", 1, filters.size)

        val signature = filters.single()
        assertTrue("SEND missing", "android.intent.action.SEND" in signature.actions)
        assertTrue("SEND_MULTIPLE missing", "android.intent.action.SEND_MULTIPLE" in signature.actions)
        assertTrue("DEFAULT category missing", "android.intent.category.DEFAULT" in signature.categories)
        assertTrue("PDF is not shareable", "application/pdf" in signature.mimeTypes)
        assertTrue("EPUB is not shareable", "application/epub+zip" in signature.mimeTypes)
        assertTrue("shareable types went missing", signature.mimeTypes.size >= 15)
    }

    @Test
    fun `the share activity itself exposes no filter`() {
        val activity = elements("activity").firstOrNull {
            it.attribute("android:name") == ".share.SendActivity"
        }
        assertNotNull("SendActivity is not declared", activity)
        assertEquals("SendActivity must not be a share target itself",
            0, activity!!.getElementsByTagName("intent-filter").length)
        // Exported so the aliases can start it; harmless without a filter.
        assertEquals("true", activity.attribute("android:exported"))
    }

    @Test
    fun `only the papir alias starts enabled and it wears the app icon`() {
        val enabled = aliases().filter { it.attribute("android:enabled") == "true" }
        assertEquals(1, enabled.size)
        assertEquals(".share.ShareTargetPapir", enabled.single().attribute("android:name"))
        assertEquals("@mipmap/ic_launcher", enabled.single().attribute("android:icon"))
    }

    @Test
    fun `every alias points at the share activity with its own icon`() {
        aliases().forEach { alias ->
            assertEquals(alias.attribute("android:name"),
                ".share.SendActivity", alias.attribute("android:targetActivity"))
            assertEquals("true", alias.attribute("android:exported"))
            assertEquals(alias.attribute("android:name"),
                "@string/share_target_label", alias.attribute("android:label"))
        }
    }

    @Test
    fun `every alias points at an icon that exists`() {
        aliases().forEach { alias ->
            val icon = alias.attribute("android:icon")
            assertTrue("${alias.attribute("android:name")} icon: $icon", icon.startsWith("@mipmap/"))
            val xml = File(resDir(), "mipmap-anydpi-v26/${icon.removePrefix("@mipmap/")}.xml")
            assertTrue("missing ${xml.name} (run make-icons.py)", xml.isFile)
        }
    }

    @Test
    fun `every silhouette has the drawables behind it`() {
        val res = resDir()
        DeviceKind.entries.forEach { kind ->
            val foreground = if (kind == DeviceKind.PAPIR) "ic_launcher_foreground" else "ic_share_${kind.slug}_foreground"
            val files = listOf(
                File(res, "drawable-nodpi/$foreground.png"),
                File(res, "drawable-nodpi/ic_mark_${kind.slug}.png"),
            )
            files.forEach { file ->
                assertTrue("missing ${file.name} (run make-icons.py)", file.isFile)
            }
        }
    }

    // ------------------------------------------------------------------ helpers

    private data class Filter(
        val actions: Set<String>,
        val categories: Set<String>,
        val mimeTypes: Set<String>,
    )

    private class Element(private val node: org.w3c.dom.Element) {
        fun attribute(name: String): String = node.getAttribute(name)
        fun getElementsByTagName(name: String) = node.getElementsByTagName(name)

        fun filterSignature(): Filter {
            val filters = node.getElementsByTagName("intent-filter")
            assertEquals("alias carries ${filters.length} filters", 1, filters.length)
            val filter = filters.item(0) as org.w3c.dom.Element
            fun values(tag: String, attribute: String) = buildSet {
                val nodes = filter.getElementsByTagName(tag)
                for (index in 0 until nodes.length) {
                    add((nodes.item(index) as org.w3c.dom.Element).getAttribute(attribute))
                }
            }
            return Filter(
                actions = values("action", "android:name"),
                categories = values("category", "android:name"),
                mimeTypes = values("data", "android:mimeType"),
            )
        }
    }

    private fun aliases(): List<Element> = elements("activity-alias")

    private fun elements(tag: String): List<Element> {
        val nodes = document().getElementsByTagName(tag)
        return (0 until nodes.length).map { Element(nodes.item(it) as org.w3c.dom.Element) }
    }

    private fun document() = DocumentBuilderFactory.newInstance()
        .newDocumentBuilder()
        .parse(manifest)
}

/** Locates the Android sources from the JVM tests, which run from the repo root. */
private fun androidRoot(): File {
    System.getProperty("papir.android")?.let { return File(it) }
    var directory: File? = File(System.getProperty("user.dir")).absoluteFile
    while (directory != null) {
        val candidate = File(directory, "android/app/src/main")
        if (candidate.isDirectory) return File(directory, "android")
        directory = directory.parentFile
    }
    error("could not locate android/ from ${System.getProperty("user.dir")}")
}

private fun manifestFile() = File(androidRoot(), "app/src/main/AndroidManifest.xml")

private fun resDir() = File(androidRoot(), "app/src/main/res")
