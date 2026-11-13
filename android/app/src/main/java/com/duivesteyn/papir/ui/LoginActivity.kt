package com.duivesteyn.papir.ui

import android.app.Activity
import android.app.AlertDialog
import android.content.ActivityNotFoundException
import android.content.ClipboardManager
import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.View
import android.webkit.CookieManager
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.Toast
import com.duivesteyn.papir.PapirApp
import com.duivesteyn.papir.R
import com.duivesteyn.papir.core.Config
import com.duivesteyn.papir.core.KindleApi
import com.duivesteyn.papir.core.Pkce
import com.duivesteyn.papir.share.UploadService

/**
 * Amazon sign-in, browser first — the same shape as `papir login` on the Mac.
 *
 * Amazon's redirect lands on `amazon.com/gp/sendtokindle`, which Android cannot
 * hand to a third-party app by itself (that needs the domain owner's verified
 * App Link). So the authorization code comes back two ways:
 *
 *  - share the finished page to Papir — [com.duivesteyn.papir.share.SendActivity]
 *    spots the code URL and forwards it here, or
 *  - copy the address and return, where this screen picks it up from the
 *    clipboard after asking.
 *
 * The in-app WebView stays as a fallback, with a small script that lets the
 * password field accept paste and password-manager autofill again.
 */
class LoginActivity : Activity() {

    private lateinit var webView: WebView
    private lateinit var overlay: View
    private lateinit var awaitPanel: View
    private lateinit var switchButton: Button
    private lateinit var reopenButton: Button
    private lateinit var pasteButton: Button
    private lateinit var api: KindleApi
    private val main = Handler(Looper.getMainLooper())

    private var verifier = ""
    private var working = false
    private var awaitingBrowser = false
    private var warnedIncomplete = false
    private var pausedOnce = false
    private var lastClipboardLink: String? = null
    private var fromSharedLink = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_login)

        webView = findViewById(R.id.webView)
        overlay = findViewById(R.id.workingOverlay)
        awaitPanel = findViewById(R.id.awaitPanel)
        switchButton = findViewById(R.id.switchButton)
        reopenButton = findViewById(R.id.reopenButton)
        pasteButton = findViewById(R.id.pasteButton)

        api = KindleApi()
        verifier = Config.loginVerifier(this)
            ?: Pkce.verifier().also { Config.setLoginVerifier(this, it) }

        findViewById<Button>(R.id.closeButton).setOnClickListener { finish() }
        pasteButton.setOnClickListener { showPasteDialog() }
        reopenButton.setOnClickListener { openBrowser() }
        switchButton.setOnClickListener {
            if (awaitingBrowser) startWebSignIn() else openBrowser()
        }
        configureWebView()

        val authUrl = intent.getStringExtra(EXTRA_AUTH_URL)
        when {
            // A stale share after signing in must not register a second device.
            Config.isSignedIn(this) && authUrl != null -> {
                setResult(RESULT_OK)
                finish()
            }
            authUrl != null -> handleAuthUrl(authUrl)
            // Don't bounce to the browser again after a rotation or a kill.
            savedInstanceState != null -> showAwaitingBrowser()
            else -> openBrowser()
        }
    }

    override fun onResume() {
        super.onResume()
        if (working) return
        if (Config.isSignedIn(this)) {
            setResult(RESULT_OK)
            finish()
            return
        }
        if (awaitingBrowser && pausedOnce) checkClipboard()
    }

    override fun onPause() {
        super.onPause()
        pausedOnce = true
    }

    override fun onDestroy() {
        webView.stopLoading()
        webView.destroy()
        super.onDestroy()
    }

    // ------------------------------------------------------------------ browser

    private fun openBrowser() {
        val url = api.signInUrl(verifier)
        try {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        } catch (e: ActivityNotFoundException) {
            toast(getString(R.string.login_no_browser))
            startWebSignIn()
            return
        }
        showAwaitingBrowser()
    }

    private fun showAwaitingBrowser() {
        if (working) return
        awaitingBrowser = true
        overlay.visibility = View.GONE
        awaitPanel.visibility = View.VISIBLE
        webView.visibility = View.GONE
        switchButton.setText(R.string.login_switch_to_web)
    }

    /**
     * After a browser round-trip the address bar is the easiest thing to copy.
     * The clipboard is only read while this screen is waiting, and the link is
     * never used without asking.
     */
    private fun checkClipboard() {
        val link = clipboardLink() ?: return
        if (link == lastClipboardLink) return
        lastClipboardLink = link

        AlertDialog.Builder(this)
            .setTitle(R.string.login_clipboard_title)
            .setMessage(R.string.login_clipboard_body)
            .setPositiveButton(R.string.login_clipboard_use) { _, _ -> handleAuthUrl(link) }
            .setNegativeButton(R.string.login_not_now, null)
            .show()
    }

    // --------------------------------------------------------------------- web

    private fun startWebSignIn() {
        awaitingBrowser = false
        warnedIncomplete = false
        working = false
        overlay.visibility = View.GONE
        awaitPanel.visibility = View.GONE
        webView.visibility = View.VISIBLE
        switchButton.setText(R.string.login_switch_to_browser)
        webView.loadUrl(api.signInUrl(verifier))
    }

    private fun configureWebView() {
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            loadWithOverviewMode = true
            useWideViewPort = true
            setSupportZoom(true)
            builtInZoomControls = false
            displayZoomControls = false
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            userAgentString = DESKTOP_USER_AGENT
        }
        CookieManager.getInstance().apply {
            setAcceptCookie(true)
            setAcceptThirdPartyCookies(webView, true)
        }
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(
                view: WebView,
                request: WebResourceRequest,
            ): Boolean = handleReturn(request.url.toString())

            override fun onPageStarted(view: WebView, url: String?, favicon: Bitmap?) {
                if (url != null && handleReturn(url)) view.stopLoading()
            }

            override fun onPageFinished(view: WebView, url: String?) {
                view.evaluateJavascript(UNLOCK_FORM_JS, null)
            }

            override fun onReceivedError(
                view: WebView,
                request: WebResourceRequest,
                error: WebResourceError,
            ) {
                Log.w(TAG, "load error ${error.errorCode} on ${request.url}: ${error.description}")
                if (request.isForMainFrame && !working) {
                    toast(getString(R.string.login_failed, error.description.toString()))
                }
            }
        }
    }

    /** Returns true when this URL is the end of the OAuth dance. */
    private fun handleReturn(url: String): Boolean {
        if (working) return true
        val isReturn = url.contains("openid.oa2.authorization_code=") ||
            url.startsWith("https://www.amazon.com/gp/sendtokindle")
        if (!isReturn) return false

        val code = api.parseAuthorizationCode(url)
        if (code.isNullOrEmpty()) {
            if (!warnedIncomplete) {
                warnedIncomplete = true
                toast(getString(R.string.login_code_missing))
            }
            return false
        }
        completeSignIn(code)
        return true
    }

    // ------------------------------------------------------------------ finish

    private fun handleAuthUrl(url: String) {
        fromSharedLink = true
        val code = api.parseAuthorizationCode(url)
        if (code.isNullOrEmpty()) {
            toast(getString(R.string.login_code_missing))
            showAwaitingBrowser()
            return
        }
        completeSignIn(code)
    }

    private fun completeSignIn(code: String) {
        if (working) return
        working = true
        overlay.visibility = View.VISIBLE
        webView.stopLoading()

        val pending = intent.getStringArrayListExtra(EXTRA_PENDING_PATHS).orEmpty()
        val app = application as PapirApp
        app.io.execute {
            try {
                val token = api.exchangeToken(code, verifier)
                val info = api.registerDevice(token, Pkce.serial(), deviceName())
                Config.saveSession(this, info)
                Config.setLoginVerifier(this, null)
                main.post { finishSuccess(pending) }
            } catch (e: Exception) {
                main.post { finishFailure(e) }
            }
        }
    }

    private fun finishSuccess(pending: List<String>) {
        CookieManager.getInstance().flush()
        setResult(RESULT_OK)
        toast(getString(R.string.login_success))
        if (pending.isNotEmpty()) UploadService.start(this, pending)
        finish()
    }

    private fun finishFailure(error: Exception) {
        working = false
        overlay.visibility = View.GONE
        if (awaitingBrowser || fromSharedLink) showAwaitingBrowser()
        AlertDialog.Builder(this)
            .setTitle(R.string.sign_in_title)
            .setMessage(getString(R.string.login_failed, error.message ?: "Amazon"))
            .setPositiveButton(R.string.login_retry) { _, _ -> openBrowser() }
            .setNegativeButton(R.string.cancel, null)
            .show()
    }

    // ------------------------------------------------------------------ paste

    private fun showPasteDialog() {
        val input = EditText(this).apply {
            hint = getString(R.string.login_paste_hint)
            setTextColor(getColor(R.color.papir_ivory))
            setHintTextColor(getColor(R.color.papir_ivory_dim))
            setPadding(dp(20), dp(12), dp(20), dp(12))
            maxLines = 3
        }
        clipboardLink()?.let { input.setText(it) }

        AlertDialog.Builder(this)
            .setTitle(R.string.login_paste_title)
            .setView(input)
            .setPositiveButton(android.R.string.ok) { _, _ ->
                val code = api.parseAuthorizationCode(input.text.toString())
                if (code.isNullOrEmpty()) {
                    toast(getString(R.string.login_paste_invalid))
                } else {
                    completeSignIn(code)
                }
            }
            .setNegativeButton(R.string.cancel, null)
            .show()
    }

    private fun clipboardLink(): String? {
        val clipboard = getSystemService(ClipboardManager::class.java) ?: return null
        val clip = clipboard.primaryClip ?: return null
        return (0 until clip.itemCount)
            .mapNotNull { clip.getItemAt(it).text?.toString() }
            .firstOrNull { it.contains("openid.oa2.authorization_code") }
    }

    // ---------------------------------------------------------------- helpers

    private fun deviceName(): String {
        val model = Build.MODEL.orEmpty().trim()
        val name = if (model.isEmpty() || model.equals("unknown", true)) {
            "Papir Android"
        } else {
            "Papir $model"
        }
        return name.take(40)
    }

    private fun toast(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_LONG).show()
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    companion object {
        private const val TAG = "PapirLogin"
        const val EXTRA_AUTH_URL = "com.duivesteyn.papir.extra.AUTH_URL"
        const val EXTRA_PENDING_PATHS = "com.duivesteyn.papir.extra.PENDING_PATHS"

        private const val DESKTOP_USER_AGENT =
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

        /**
         * Re-allow paste, copy, cut and the long-press menu on the sign-in form.
         * The capture-phase listeners run before the page's own handlers, so a
         * site that cancels these events never sees them; the browser's default
         * behaviour — the actual paste — is unaffected.
         */
        private const val UNLOCK_FORM_JS = """
            (function () {
              try {
                if (window.__papirFormUnlock) return;
                window.__papirFormUnlock = true;
                ['paste', 'copy', 'cut', 'contextmenu'].forEach(function (type) {
                  window.addEventListener(type, function (event) {
                    event.stopPropagation();
                  }, true);
                });
                var style = document.createElement('style');
                style.textContent =
                  'input,textarea{-webkit-user-select:text!important;user-select:text!important;}';
                (document.head || document.documentElement).appendChild(style);
                var unlock = function () {
                  var fields = document.querySelectorAll('input, textarea');
                  for (var i = 0; i < fields.length; i++) {
                    var field = fields[i];
                    field.onpaste = null; field.oncopy = null; field.oncut = null;
                    field.removeAttribute('onpaste');
                    field.removeAttribute('oncopy');
                    field.removeAttribute('spellcheck');
                    field.removeAttribute('autocomplete');
                  }
                };
                unlock();
                new MutationObserver(unlock).observe(document.documentElement,
                  { childList: true, subtree: true });
              } catch (e) {}
            })();
        """
    }
}
