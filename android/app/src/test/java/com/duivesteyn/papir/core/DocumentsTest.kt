package com.duivesteyn.papir.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class DocumentsTest {

    @Test
    fun `titles are cleaned exactly like the CLI`() {
        Fixtures.TITLES.forEach { (stem, expected) ->
            assertEquals(stem, expected, Documents.cleanTitle(stem))
        }
    }

    @Test
    fun `format lookup ignores case and leading dot`() {
        assertEquals("PDF", Documents.formatFor("Quarterly Report.PDF"))
        assertEquals("PDF", Documents.formatFor("report.pdf"))
        assertEquals("DOCX", Documents.formatFor("notes.docx"))
        assertEquals("JPEG", Documents.formatFor("scan.jpeg"))
    }

    @Test
    fun `unknown extensions have no format`() {
        assertNull(Documents.formatFor("installer.exe"))
        assertNull(Documents.formatFor("no-extension"))
    }

    @Test
    fun `a file name becomes a shelf title`() {
        assertEquals(
            "Quarterly Report",
            Documents.titleFor("Quarterly Report 2026-03-31.pdf"),
        )
        assertEquals("Design Systems", Documents.titleFor("Design_Systems_v2.pdf"))
    }
}
