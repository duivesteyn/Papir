package com.duivesteyn.papir.share

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.OpenableColumns
import android.util.Log
import android.view.View
import android.webkit.MimeTypeMap
import android.widget.Button
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import com.duivesteyn.papir.PapirApp
import com.duivesteyn.papir.R
import com.duivesteyn.papir.core.Config
import com.duivesteyn.papir.core.Documents
import com.duivesteyn.papir.ui.LoginActivity
import java.io.ByteArrayInputStream
import java.io.File
import java.util.UUID

/**
 * The share-sheet entry, and its confirmation card.
 *
 * It copies the incoming document into Papir's cache while the sender's read
 * grant is still valid, then starts [UploadService] and shows a small card with
 * live progress. The card reports the outcome ("Sent to Kindle", or the error
 * with Retry) and disappears on its own; dismissing it early leaves the upload
 * running, with notifications taking over.
 */
class SendActivity : Activity() {

    private lateinit var cardTitle: TextView
    private lateinit var cardDetail: TextView
    private lateinit var cardMeta: TextView
    private lateinit var cardIcon: View
    private lateinit var cardProgress: ProgressBar
    private lateinit var primaryButton: Button
    private lateinit var secondaryButton: Button

    private val handler = Handler(Looper.getMainLooper())
    private val statusListener: (SendStatus.Snapshot) -> Unit = { snapshot ->
        handler.post { render(snapshot) }
    }

    private var paths: List<String> = emptyList()
    private var observing = false
    private var dismissRunnable: Runnable? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // A recreated activity (rotation, low memory) must not send twice.
        if (savedInstanceState != null) {
            finish()
            return
        }

        // A browser sign-in comes back as a shared Amazon page URL.
        val authUrl = Shares.amazonAuthUrl(intent)
        if (authUrl != null) {
            startActivity(
                Intent(applicationContext, LoginActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    .putExtra(LoginActivity.EXTRA_AUTH_URL, authUrl)
            )
            finish()
            return
        }

        val incoming = Shares.collect(intent)
        if (incoming.isEmpty()) {
            toast(getString(R.string.nothing_to_send))
            finish()
            return
        }
        if (incoming.all { it.uri == null && Shares.isLinkOnly(it.text.orEmpty()) }) {
            toast(getString(R.string.links_not_supported))
            finish()
            return
        }

        setContentView(R.layout.dialog_send)
        setFinishOnTouchOutside(true)
        cardTitle = findViewById(R.id.cardTitle)
        cardDetail = findViewById(R.id.cardDetail)
        cardMeta = findViewById(R.id.cardMeta)
        cardIcon = findViewById(R.id.cardIcon)
        cardProgress = findViewById(R.id.cardProgress)
        primaryButton = findViewById(R.id.primaryButton)
        secondaryButton = findViewById(R.id.secondaryButton)
        showPreparing()

        val app = application as PapirApp
        app.io.execute {
            val directory = File(cacheDir, "${PapirApp.INBOX_DIR}/${UUID.randomUUID()}")
            val copied = copyInto(directory, incoming)
            handler.post { onCopied(copied) }
        }
    }

    override fun onStart() {
        super.onStart()
        if (observing) {
            SendStatus.addListener(statusListener)
            render(SendStatus.current)
        }
    }

    override fun onStop() {
        SendStatus.removeListener(statusListener)
        super.onStop()
    }

    override fun onDestroy() {
        dismissRunnable?.let(handler::removeCallbacks)
        SendStatus.removeListener(statusListener)
        super.onDestroy()
    }

    // ------------------------------------------------------------------ flow

    private fun onCopied(copied: List<String>) {
        if (isFinishing || isDestroyed) return
        if (copied.isEmpty()) {
            showFailure(getString(R.string.send_unreadable), retryable = false)
            return
        }
        paths = copied
        if (Config.device(this) == null) {
            showSignIn()
            return
        }
        startSending()
    }

    private fun startSending() {
        observing = true
        SendStatus.addListener(statusListener)
        showSending(SendStatus.Snapshot(SendStatus.Phase.SENDING, title = firstTitle(), count = paths.size))
        UploadService.start(applicationContext, paths)
    }

    private fun retry() {
        val remaining = paths.filter { File(it).isFile }
        if (remaining.isEmpty()) {
            showFailure(getString(R.string.send_unreadable), retryable = false)
            return
        }
        paths = remaining
        startSending()
    }

    private fun firstTitle(): String =
        paths.firstOrNull()?.let { Documents.titleFor(File(it).name) }.orEmpty()

    // ------------------------------------------------------------------ render

    private fun render(snapshot: SendStatus.Snapshot) {
        when (snapshot.phase) {
            SendStatus.Phase.SENDING -> showSending(snapshot)
            SendStatus.Phase.SENT -> showSent(snapshot)
            SendStatus.Phase.FAILED -> showFailure(
                snapshot.error.ifBlank { getString(R.string.send_failed) },
                retryable = true,
            )
            SendStatus.Phase.IDLE -> Unit
        }
    }

    private fun showPreparing() {
        cancelDismiss()
        cardIcon.visibility = View.GONE
        cardTitle.text = getString(R.string.send_preparing)
        cardDetail.visibility = View.GONE
        cardProgress.visibility = View.VISIBLE
        cardProgress.isIndeterminate = true
        cardMeta.visibility = View.GONE
        primaryButton.visibility = View.GONE
        secondaryButton.visibility = View.GONE
    }

    private fun showSending(snapshot: SendStatus.Snapshot) {
        cancelDismiss()
        cardIcon.visibility = View.GONE
        cardTitle.text = getString(R.string.send_sending)
        cardDetail.visibility = View.VISIBLE
        val counter = if (snapshot.count > 1) {
            getString(R.string.send_counter, snapshot.index + 1, snapshot.count) + " · "
        } else {
            ""
        }
        cardDetail.text = counter + snapshot.title
        cardProgress.visibility = View.VISIBLE
        cardProgress.isIndeterminate = false
        cardProgress.progress = snapshot.percent
        cardMeta.visibility = View.VISIBLE
        cardMeta.text = getString(R.string.send_percent, snapshot.percent)
        primaryButton.visibility = View.VISIBLE
        primaryButton.text = getString(R.string.send_hide)
        primaryButton.setOnClickListener { finish() }
        secondaryButton.visibility = View.GONE
    }

    private fun showSent(snapshot: SendStatus.Snapshot) {
        cardIcon.visibility = View.VISIBLE
        cardTitle.text = getString(R.string.send_sent)
        cardDetail.visibility = View.VISIBLE
        cardDetail.text = if (snapshot.count > 1) {
            getString(R.string.send_documents, snapshot.count)
        } else {
            snapshot.title
        }
        cardProgress.visibility = View.GONE
        cardMeta.visibility = if (snapshot.sku.isNotBlank()) View.VISIBLE else View.GONE
        cardMeta.text = getString(R.string.send_sku, snapshot.sku)
        primaryButton.visibility = View.VISIBLE
        primaryButton.text = getString(R.string.send_done)
        primaryButton.setOnClickListener { finish() }
        secondaryButton.visibility = View.GONE
        scheduleDismiss()
    }

    private fun showFailure(message: String, retryable: Boolean) {
        cancelDismiss()
        cardIcon.visibility = View.GONE
        cardTitle.text = getString(R.string.send_failed)
        cardDetail.visibility = View.VISIBLE
        cardDetail.text = message
        cardProgress.visibility = View.GONE
        cardMeta.visibility = View.GONE
        primaryButton.visibility = View.VISIBLE

        if (retryable) {
            primaryButton.text = getString(R.string.send_retry)
            primaryButton.setOnClickListener { retry() }
            secondaryButton.visibility = View.VISIBLE
            secondaryButton.text = getString(R.string.send_close)
            secondaryButton.setOnClickListener { finish() }
        } else {
            primaryButton.text = getString(R.string.send_close)
            primaryButton.setOnClickListener { finish() }
            secondaryButton.visibility = View.GONE
        }
    }

    private fun showSignIn() {
        cancelDismiss()
        cardIcon.visibility = View.GONE
        cardTitle.text = getString(R.string.send_sign_in_title)
        cardDetail.visibility = View.VISIBLE
        cardDetail.text = getString(R.string.send_sign_in_body)
        cardProgress.visibility = View.GONE
        cardMeta.visibility = View.GONE
        primaryButton.visibility = View.VISIBLE
        primaryButton.text = getString(R.string.send_sign_in)
        primaryButton.setOnClickListener {
            startActivity(
                Intent(this, LoginActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    .putStringArrayListExtra(LoginActivity.EXTRA_PENDING_PATHS, ArrayList(paths))
            )
            finish()
        }
        secondaryButton.visibility = View.VISIBLE
        secondaryButton.text = getString(R.string.send_not_now)
        secondaryButton.setOnClickListener { finish() }
    }

    private fun scheduleDismiss() {
        cancelDismiss()
        val runnable = Runnable { if (!isFinishing) finish() }
        dismissRunnable = runnable
        handler.postDelayed(runnable, 2600)
    }

    private fun cancelDismiss() {
        dismissRunnable?.let(handler::removeCallbacks)
        dismissRunnable = null
    }

    // ------------------------------------------------------------------- copy

    /** Copy every share into one directory, keeping the original file name. */
    private fun copyInto(directory: File, incoming: List<IncomingShare>): List<String> {
        if (!directory.exists() && !directory.mkdirs()) {
            Log.w(TAG, "could not create ${directory.absolutePath}")
            return emptyList()
        }
        val paths = ArrayList<String>(incoming.size)
        incoming.forEachIndexed { index, share ->
            try {
                val target = File(directory, uniqueName(directory, fileNameFor(share, index)))
                val source = if (share.uri != null) {
                    contentResolver.openInputStream(share.uri)
                } else {
                    ByteArrayInputStream(share.text.orEmpty().toByteArray(Charsets.UTF_8))
                }
                if (source == null) return@forEachIndexed
                source.use { input -> target.outputStream().use { input.copyTo(it) } }
                if (target.length() > 0L) paths.add(target.absolutePath)
            } catch (e: Exception) {
                Log.w(TAG, "could not read shared item", e)
            }
        }
        if (paths.isEmpty()) directory.deleteRecursively()
        return paths
    }

    private fun fileNameFor(share: IncomingShare, index: Int): String {
        if (share.uri == null) return "Shared note.txt"
        val raw = displayName(share.uri) ?: "document${index + 1}"
        var name = sanitize(raw)
        if (Documents.extensionOf(name).isEmpty()) {
            val extension = share.mime?.let { MimeTypeMap.getSingleton().getExtensionFromMimeType(it) }
            if (!extension.isNullOrEmpty()) name = "$name.$extension"
        }
        if (name.isEmpty() || name == ".") name = "document${index + 1}.pdf"
        return name
    }

    @Suppress("DEPRECATION")
    private fun displayName(uri: Uri): String? {
        if (uri.scheme == "file") return uri.lastPathSegment
        return try {
            contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
                ?.use { cursor -> if (cursor.moveToFirst()) cursor.getString(0) else null }
        } catch (e: Exception) {
            uri.lastPathSegment
        }
    }

    private fun sanitize(name: String): String =
        name.substringAfterLast('/')
            .replace(Regex("[^A-Za-z0-9._ ()-]"), "_")
            .trim()
            .take(80)

    private fun uniqueName(directory: File, name: String): String {
        if (!File(directory, name).exists()) return name
        val stem = name.substringBeforeLast('.', name)
        val extension = name.substringAfterLast('.', "")
        var counter = 2
        while (true) {
            val candidate = if (extension.isEmpty()) "$stem-$counter" else "$stem-$counter.$extension"
            if (!File(directory, candidate).exists()) return candidate
            counter++
        }
    }

    private fun toast(message: String) {
        Toast.makeText(applicationContext, message, Toast.LENGTH_LONG).show()
    }

    private companion object {
        const val TAG = "PapirShare"
    }
}
