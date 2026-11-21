package com.duivesteyn.papir.core

/**
 * Which Kindle silhouette the share sheet wears.
 *
 * Amazon reports destinations by name alone ("Ben's Kindle Scribe", "Kindle
 * Paperwhite (11th Generation)"), so the mark is derived from that name — the
 * user's *selection*, not a device baked into the app. The declaration order is
 * the order of precedence: a "Kindle Scribe Colorsoft" is a Scribe first,
 * because the pen is what makes it one.
 *
 * [slug] names the icon set (`ic_share_<slug>`), [alias] the matching
 * `<activity-alias>` in the manifest.
 */
enum class DeviceKind(
    val slug: String,
    val alias: String,
    private val keywords: List<String>,
) {
    /** No single destination: nothing selected yet, "All devices", or signed out. */
    PAPIR("papir", "Papir", emptyList()),

    /** Note tablet with the pen alongside. */
    SCRIBE("scribe", "Scribe", listOf("scribe")),

    /** Paperwhite frame with a colour cover on the page. */
    COLORSOFT(
        "colorsoft",
        "Colorsoft",
        listOf("colorsoft", "coloursoft", "color soft", "colour soft"),
    ),

    /** Spine with the two page-turn buttons. */
    OASIS("oasis", "Oasis", listOf("oasis")),

    /** Flush glass front, no chin. */
    VOYAGE("voyage", "Voyage", listOf("voyage")),

    /** Keys under the page. */
    KEYBOARD("keyboard", "Keyboard", listOf("keyboard")),

    /** Landscape page over a keyboard. */
    DX("dx", "Dx", listOf("dx", "dxg")),

    /** Thin side bezels, wide chin, round home button. */
    PAPERWHITE("paperwhite", "Paperwhite", listOf("paperwhite", "paper white")),

    /** Touch ripple and a home bar. */
    TOUCH("touch", "Touch", listOf("touch")),

    /** Even bezel all round, no button. */
    BASIC("basic", "Basic", listOf("basic")),

    /** Anything unplaced — Fire tablets, reading apps, odd names. */
    GENERIC("generic", "Generic", emptyList()),
    ;

    companion object {
        private val SEPARATORS = Regex("[^a-z0-9]+")

        /** The silhouette for a device name; never null, so every name lands somewhere. */
        fun forDeviceName(name: String?): DeviceKind {
            val tokens = (name ?: "").lowercase().split(SEPARATORS).filter { it.isNotEmpty() }
            if (tokens.isEmpty()) return GENERIC
            val joined = tokens.joinToString("")

            for (kind in entries) {
                if (kind.keywords.any { kind.matches(it, tokens, joined) }) return kind
            }
            return GENERIC
        }

        private fun DeviceKind.matches(keyword: String, tokens: List<String>, joined: String): Boolean {
            val parts = keyword.split(SEPARATORS).filter { it.isNotEmpty() }
            if (parts.isEmpty()) return false
            // Whole-word match first: "Kindle DX", "… Paperwhite (11th Generation)".
            if (parts.size == 1 && parts[0] in tokens) return true
            if (parts.size > 1 && tokens.windowed(parts.size).any { it == parts }) return true
            // Then run-together spellings Amazon sometimes returns: "KindlePaperwhite".
            val squashed = parts.joinToString("")
            return squashed.length >= 4 && joined.contains(squashed)
        }
    }
}
