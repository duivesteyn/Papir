package com.duivesteyn.papir.core

/**
 * File-name handling — Amazon format names and the same title clean-up the
 * CLI applies, so a shared PDF arrives titled like a document, not a filename.
 */
object Documents {

    private val FORMATS = mapOf(
        "pdf" to "PDF",
        "epub" to "EPUB",
        "doc" to "DOC",
        "docx" to "DOCX",
        "rtf" to "RTF",
        "txt" to "TXT",
        "htm" to "HTM",
        "html" to "HTML",
        "mobi" to "MOBI",
        "azw" to "AZW",
        "jpg" to "JPEG",
        "jpeg" to "JPEG",
        "gif" to "GIF",
        "png" to "PNG",
        "bmp" to "BMP",
    )

    private val TRAILING_DATE = Regex("\\s+\\d{4}[-_ ]\\d{2}[-_ ]\\d{2}\\s*$")
    private val TRAILING_VERSION = Regex("\\s+v\\d+(\\.\\d+)*\\s*$", RegexOption.IGNORE_CASE)
    private val WHITESPACE = Regex("\\s+")

    fun extensionOf(fileName: String): String =
        fileName.substringAfterLast('.', "").lowercase()

    fun formatFor(fileName: String): String? = FORMATS[extensionOf(fileName)]

    fun titleFor(fileName: String): String {
        val stem = fileName.substringBeforeLast('.', fileName)
        return cleanTitle(stem)
    }

    /**
     * Light_and_Wonder_LNW_Investment_Report_v1.2_2026-10-06
     *   -> Light and Wonder LNW Investment Report
     */
    fun cleanTitle(stem: String): String {
        var title = stem.replace('_', ' ')
        title = TRAILING_DATE.replace(title, "")
        title = TRAILING_VERSION.replace(title, "")
        title = WHITESPACE.replace(title, " ").trim()
        return title.ifEmpty { stem }
    }
}
