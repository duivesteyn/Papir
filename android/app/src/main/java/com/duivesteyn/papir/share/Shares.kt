package com.duivesteyn.papir.share

import android.content.Intent
import android.net.Uri

/** One item handed to Papir by another app: a stream, or plain text. */
data class IncomingShare(val uri: Uri?, val text: String?, val mime: String?)

/** Reads ACTION_SEND / ACTION_SEND_MULTIPLE payloads from a share sheet intent. */
object Shares {

    fun collect(intent: Intent?): List<IncomingShare> {
        if (intent == null) return emptyList()
        val mime = intent.type
        val uris = mutableListOf<Uri>()

        when (intent.action) {
            Intent.ACTION_SEND -> streamOf(intent)?.let(uris::add)
            Intent.ACTION_SEND_MULTIPLE -> uris.addAll(streamsOf(intent))
        }
        if (uris.isEmpty()) {
            intent.clipData?.let { clip ->
                for (index in 0 until clip.itemCount) {
                    clip.getItemAt(index).uri?.let(uris::add)
                }
            }
        }
        // Some senders put the stream in data rather than EXTRA_STREAM; the URI
        // grant follows data, so this path is at least as well supported.
        if (uris.isEmpty() && intent.data != null &&
            (intent.action == Intent.ACTION_SEND || intent.action == Intent.ACTION_SEND_MULTIPLE)
        ) {
            intent.data?.let(uris::add)
        }
        if (uris.isNotEmpty()) return uris.map { IncomingShare(it, null, mime) }

        val text = intent.getCharSequenceExtra(Intent.EXTRA_TEXT)?.toString()?.trim()
        if (!text.isNullOrEmpty()) return listOf(IncomingShare(null, text, mime))
        return emptyList()
    }

    /**
     * The final Amazon page after a browser sign-in carries the authorization
     * code in its URL. Sharing that page to Papir finishes the login.
     */
    fun amazonAuthUrl(intent: Intent?): String? {
        if (intent == null) return null
        val candidates = buildList {
            intent.getCharSequenceExtra(Intent.EXTRA_TEXT)?.toString()?.let(::add)
            intent.dataString?.let(::add)
        }
        for (text in candidates) {
            AMAZON_AUTH_URL.find(text)?.let { return it.value }
        }
        return null
    }

    /** A bare link isn't a document; Papir can't fetch and paginate it on the phone. */
    fun isLinkOnly(text: String): Boolean =
        Regex("^https?://\\S+$", RegexOption.IGNORE_CASE).matches(text.trim())

    private val AMAZON_AUTH_URL =
        Regex("https?://[^\\s\"']*openid\\.oa2\\.authorization_code=[^\\s\"']+")

    @Suppress("DEPRECATION")
    private fun streamOf(intent: Intent): Uri? =
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
        } else {
            intent.getParcelableExtra(Intent.EXTRA_STREAM)
        }

    @Suppress("DEPRECATION")
    private fun streamsOf(intent: Intent): List<Uri> =
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM, Uri::class.java).orEmpty()
        } else {
            intent.getParcelableArrayListExtra<Uri>(Intent.EXTRA_STREAM).orEmpty()
        }
}
