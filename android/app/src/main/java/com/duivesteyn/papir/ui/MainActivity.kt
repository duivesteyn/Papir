package com.duivesteyn.papir.ui

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.res.ColorStateList
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.Editable
import android.text.TextWatcher
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.ProgressBar
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.Switch
import android.widget.TextView
import com.duivesteyn.papir.PapirApp
import com.duivesteyn.papir.R
import com.duivesteyn.papir.core.Config
import com.duivesteyn.papir.core.DeviceKind
import com.duivesteyn.papir.core.OwnedDevice
import com.duivesteyn.papir.core.Sender
import com.duivesteyn.papir.share.ShareTargets

/**
 * Setup and settings. Deliberately one screen: sign in, pick a Kindle, pick an
 * author, done. Everything else happens in the share sheet.
 */
class MainActivity : Activity() {

    private lateinit var statusLine: TextView
    private lateinit var signInBlock: View
    private lateinit var mainBlock: View
    private lateinit var deviceGroup: RadioGroup
    private lateinit var devicesProgress: ProgressBar
    private lateinit var devicesError: TextView
    private lateinit var authorInput: EditText
    private lateinit var convertSwitch: Switch
    private lateinit var destinationMark: ImageView
    private lateinit var versionLine: TextView
    private lateinit var signInButton: Button
    private lateinit var refreshButton: Button
    private lateinit var signOutButton: Button

    private val main = Handler(Looper.getMainLooper())
    private var authorWatcher: TextWatcher? = null
    private var loadedDevices = false
    private var loading = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        statusLine = findViewById(R.id.statusLine)
        signInBlock = findViewById(R.id.signInBlock)
        mainBlock = findViewById(R.id.mainBlock)
        deviceGroup = findViewById(R.id.deviceGroup)
        devicesProgress = findViewById(R.id.devicesProgress)
        devicesError = findViewById(R.id.devicesError)
        authorInput = findViewById(R.id.authorInput)
        convertSwitch = findViewById(R.id.convertSwitch)
        destinationMark = findViewById(R.id.destinationMark)
        versionLine = findViewById(R.id.versionLine)
        signInButton = findViewById(R.id.signInButton)
        refreshButton = findViewById(R.id.refreshButton)
        signOutButton = findViewById(R.id.signOutButton)

        signInButton.setOnClickListener { startActivityForResult(Intent(this, LoginActivity::class.java), LOGIN_REQUEST) }
        refreshButton.setOnClickListener { loadDevices(force = true) }
        signOutButton.setOnClickListener { confirmSignOut() }
        convertSwitch.setOnCheckedChangeListener { _, checked -> Config.setConvertPdfs(this, checked) }

        versionLine.text = "Papir $versionName · Android"
        watchAuthor()
        requestNotificationPermissionIfNeeded()
    }

    override fun onResume() {
        super.onResume()
        render()
        // The destination may have been picked on another screen, or the Kindle
        // renamed in Amazon: keep the share sheet's mark in step either way.
        ShareTargets.sync(this)
        if (Config.isSignedIn(this) && !loadedDevices) loadDevices(force = false)
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == LOGIN_REQUEST) {
            render()
            if (resultCode == RESULT_OK) loadDevices(force = true)
        }
    }

    // ------------------------------------------------------------------ render

    private fun render() {
        val info = Config.device(this)
        // Safe to draw before the sign-in check: with no destination chosen the
        // desired mark is Papir's own.
        showDestinationMark()
        if (info == null) {
            signInBlock.visibility = View.VISIBLE
            mainBlock.visibility = View.GONE
            statusLine.text = getString(R.string.status_signed_out)
            loadedDevices = false
            return
        }

        signInBlock.visibility = View.GONE
        mainBlock.visibility = View.VISIBLE
        statusLine.text = if (info.accountName.isNotBlank()) {
            getString(R.string.connected_as, info.accountName)
        } else {
            getString(R.string.connected_as, info.deviceName.ifBlank { "Amazon" })
        }

        val cached = Config.cachedDevices(this)
        if (cached.isNotEmpty()) renderDevices(cached)

        val author = Config.defaultAuthor(this).orEmpty()
        if (authorInput.text.toString() != author) {
            authorInput.setText(author)
            authorInput.setSelection(authorInput.text.length)
        }
        authorInput.hint = info.accountName.ifBlank { getString(R.string.author_hint) }

        convertSwitch.isChecked = Config.convertPdfs(this)
    }

    private fun watchAuthor() {
        if (authorWatcher != null) return
        authorWatcher = object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) = Unit
            override fun afterTextChanged(s: Editable?) {
                Config.setDefaultAuthor(this@MainActivity, s?.toString())
            }
        }
        authorInput.addTextChangedListener(authorWatcher)
    }

    private fun renderDevices(devices: List<OwnedDevice>) {
        val selected = Config.defaultTarget(this)
        deviceGroup.removeAllViews()
        val allRow = deviceRow(getString(R.string.all_devices), serial = null)
        deviceGroup.addView(allRow)
        val rows = devices.map { device -> deviceRow(device.name, device.serial) }
        rows.forEach(deviceGroup::addView)

        val checkedId = devices.firstOrNull { it.serial == selected }
            ?.let { device -> rows[devices.indexOf(device)].id }
            ?: allRow.id
        deviceGroup.check(checkedId)
        if (devices.isEmpty()) {
            devicesError.visibility = View.VISIBLE
            devicesError.text = getString(R.string.devices_empty)
        } else {
            devicesError.visibility = View.GONE
        }
        // A refresh can rename the Kindle ("Ben's 2nd Scribe"), which is the only
        // input the share-sheet mark has.
        ShareTargets.sync(this)
    }

    private fun deviceRow(label: String, serial: String?): RadioButton {
        val row = RadioButton(this)
        row.id = View.generateViewId()
        row.text = label
        row.textSize = 15f
        row.setTextColor(getColor(R.color.papir_ivory))
        row.buttonTintList = ColorStateList.valueOf(getColor(R.color.papir_ivory))
        row.contentDescription = serial ?: getString(R.string.all_devices_hint)
        val padding = dp(8)
        row.setPadding(padding, padding, padding, padding)
        row.layoutParams = RadioGroup.LayoutParams(
            RadioGroup.LayoutParams.MATCH_PARENT,
            RadioGroup.LayoutParams.WRAP_CONTENT,
        )
        row.setOnClickListener {
            // The sender resolves "all" lazily; no network needed here. The name
            // is kept so the share-sheet mark can follow the pick immediately.
            Config.setDefaultTarget(this, serial, label)
            ShareTargets.sync(this)
            showDestinationMark()
        }
        return row
    }

    /** The mark the share sheet is wearing right now, beside "Destination". */
    private fun showDestinationMark() {
        destinationMark.setImageResource(markFor(ShareTargets.desired(this)))
    }

    private fun markFor(kind: DeviceKind): Int = when (kind) {
        DeviceKind.PAPIR -> R.drawable.ic_mark_papir
        DeviceKind.SCRIBE -> R.drawable.ic_mark_scribe
        DeviceKind.COLORSOFT -> R.drawable.ic_mark_colorsoft
        DeviceKind.OASIS -> R.drawable.ic_mark_oasis
        DeviceKind.VOYAGE -> R.drawable.ic_mark_voyage
        DeviceKind.KEYBOARD -> R.drawable.ic_mark_keyboard
        DeviceKind.DX -> R.drawable.ic_mark_dx
        DeviceKind.PAPERWHITE -> R.drawable.ic_mark_paperwhite
        DeviceKind.TOUCH -> R.drawable.ic_mark_touch
        DeviceKind.BASIC -> R.drawable.ic_mark_basic
        DeviceKind.GENERIC -> R.drawable.ic_mark_generic
    }

    // ----------------------------------------------------------------- devices

    private fun loadDevices(force: Boolean) {
        if (loading) return
        if (loadedDevices && !force) return
        loading = true
        devicesProgress.visibility = View.VISIBLE
        devicesError.visibility = View.GONE

        val app = application as PapirApp
        app.io.execute {
            val result = runCatching { Sender.refreshDevices(this) }
            main.post {
                if (isFinishing || isDestroyed) return@post
                loading = false
                devicesProgress.visibility = View.GONE
                result.onSuccess {
                    loadedDevices = true
                    renderDevices(it)
                }
                    .onFailure { error ->
                        devicesError.visibility = View.VISIBLE
                        devicesError.text = getString(
                            R.string.devices_failed,
                            error.message ?: "network",
                        )
                    }
            }
        }
    }

    // ------------------------------------------------------------------ actions

    private fun confirmSignOut() {
        AlertDialog.Builder(this)
            .setTitle(R.string.sign_out_title)
            .setMessage(R.string.sign_out_body)
            .setPositiveButton(R.string.sign_out) { _, _ -> signOut() }
            .setNegativeButton(R.string.cancel, null)
            .show()
    }

    private fun signOut() {
        val app = application as PapirApp
        app.io.execute {
            Sender.signOut(this)
            main.post {
                if (isFinishing || isDestroyed) return@post
                deviceGroup.removeAllViews()
                loadedDevices = false
                render()
                ShareTargets.sync(this)
            }
        }
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT < 33) return
        if (checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) ==
            android.content.pm.PackageManager.PERMISSION_GRANTED
        ) {
            return
        }
        requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), NOTIFICATION_REQUEST)
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private val versionName: String
        get() = runCatching {
            packageManager.getPackageInfo(packageName, 0).versionName
        }.getOrNull().orEmpty()

    private companion object {
        const val LOGIN_REQUEST = 41
        const val NOTIFICATION_REQUEST = 42
    }
}
