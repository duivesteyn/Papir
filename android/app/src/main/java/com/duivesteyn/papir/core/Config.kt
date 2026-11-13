package com.duivesteyn.papir.core

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/** One registered Send-to-Kindle device, mirroring `client.json`'s device_info. */
data class DeviceInfo(
    val devicePrivateKey: String,
    val adpToken: String,
    val deviceType: String,
    val deviceSerialNumber: String,
    val deviceName: String,
    val accountName: String,
    val homeRegion: String,
)

/** A Kindle or reading app as Amazon reports it. */
data class OwnedDevice(val name: String, val serial: String)

/**
 * Local state: the registered device credentials, the default destination and
 * a few preferences. Stored in the app's private SharedPreferences, which is
 * this platform's equivalent of the CLI's mode-600 `client.json`.
 */
object Config {

    private const val PREFS = "papir"
    private const val KEY_CLIENT = "client"
    private const val KEY_DEVICES = "devices"
    private const val KEY_CONVERT = "convert_pdf"
    private const val KEY_ONBOARDED = "onboarded"

    private const val KEY_LOGIN_VERIFIER = "login_verifier"

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun device(context: Context): DeviceInfo? {
        val raw = prefs(context).getString(KEY_CLIENT, null) ?: return null
        return try {
            val root = JSONObject(raw)
            if (root.optInt("version", 0) != 1) return null
            val info = root.getJSONObject("device_info")
            val key = info.optString("device_private_key", "")
            val token = info.optString("adp_token", "")
            if (key.isEmpty() || token.isEmpty()) return null
            DeviceInfo(
                devicePrivateKey = key,
                adpToken = token,
                deviceType = info.optString("device_type", ""),
                deviceSerialNumber = info.optString("device_serial_number", ""),
                deviceName = info.optString("device_name", ""),
                accountName = info.optString("account_name", ""),
                homeRegion = info.optString("home_region", ""),
            )
        } catch (e: Exception) {
            null
        }
    }

    fun isSignedIn(context: Context): Boolean = device(context) != null

    /** Persist a fresh registration, keeping any existing defaults. */
    fun saveSession(context: Context, info: DeviceInfo) {
        val current = prefs(context)
        val root = JSONObject().apply {
            put("version", 1)
            put("device_info", JSONObject().apply {
                put("device_private_key", info.devicePrivateKey)
                put("adp_token", info.adpToken)
                put("device_type", info.deviceType)
                put("device_serial_number", info.deviceSerialNumber)
                put("device_name", info.deviceName)
                put("account_name", info.accountName)
                put("home_region", info.homeRegion)
            })
            put("default_target", current.getString(KEY_DEFAULT_TARGET, null) ?: JSONObject.NULL)
            put("default_author", current.getString(KEY_DEFAULT_AUTHOR, null) ?: JSONObject.NULL)
        }
        current.edit().putString(KEY_CLIENT, root.toString()).apply()
    }

    /** Serial, or null for "every device" (matching the CLI's `all`). */
    fun defaultTarget(context: Context): String? = prefs(context).getString(KEY_DEFAULT_TARGET, null)

    fun setDefaultTarget(context: Context, serial: String?) {
        val edit = prefs(context).edit()
        if (serial.isNullOrEmpty()) edit.remove(KEY_DEFAULT_TARGET) else edit.putString(KEY_DEFAULT_TARGET, serial)
        edit.apply()
        rewriteClientJson(context)
    }

    fun defaultAuthor(context: Context): String? =
        prefs(context).getString(KEY_DEFAULT_AUTHOR, null)?.takeIf { it.isNotBlank() }

    fun setDefaultAuthor(context: Context, author: String?) {
        val edit = prefs(context).edit()
        if (author.isNullOrBlank()) edit.remove(KEY_DEFAULT_AUTHOR) else edit.putString(KEY_DEFAULT_AUTHOR, author.trim())
        edit.apply()
        rewriteClientJson(context)
    }

    fun convertPdfs(context: Context): Boolean = prefs(context).getBoolean(KEY_CONVERT, false)

    fun setConvertPdfs(context: Context, convert: Boolean) =
        prefs(context).edit().putBoolean(KEY_CONVERT, convert).apply()

    fun hasOnboarded(context: Context): Boolean = prefs(context).getBoolean(KEY_ONBOARDED, false)

    fun markOnboarded(context: Context) = prefs(context).edit().putBoolean(KEY_ONBOARDED, true).apply()

    fun cachedDevices(context: Context): List<OwnedDevice> {
        val raw = prefs(context).getString(KEY_DEVICES, null) ?: return emptyList()
        return try {
            val array = JSONArray(raw)
            (0 until array.length()).mapNotNull { i ->
                val item = array.optJSONObject(i) ?: return@mapNotNull null
                val serial = item.optString("serial", "")
                if (serial.isEmpty()) null else OwnedDevice(item.optString("name", serial), serial)
            }
        } catch (e: Exception) {
            emptyList()
        }
    }

    fun cacheDevices(context: Context, devices: List<OwnedDevice>) {
        val array = JSONArray()
        devices.forEach { array.put(JSONObject().put("name", it.name).put("serial", it.serial)) }
        prefs(context).edit().putString(KEY_DEVICES, array.toString()).apply()
    }

    /** PKCE verifier kept while a browser sign-in is in flight. */
    fun loginVerifier(context: Context): String? = prefs(context).getString(KEY_LOGIN_VERIFIER, null)

    fun setLoginVerifier(context: Context, verifier: String?) {
        val edit = prefs(context).edit()
        if (verifier.isNullOrEmpty()) edit.remove(KEY_LOGIN_VERIFIER) else edit.putString(KEY_LOGIN_VERIFIER, verifier)
        edit.apply()
    }

    fun clear(context: Context) {
        prefs(context).edit().clear().apply()
    }

    /**
     * Keep `client.json`'s shape in the stored blob so a future import/export
     * with the Mac app can share exactly the same document.
     */
    private fun rewriteClientJson(context: Context) {
        val info = device(context) ?: return
        val root = JSONObject().apply {
            put("version", 1)
            put("device_info", JSONObject().apply {
                put("device_private_key", info.devicePrivateKey)
                put("adp_token", info.adpToken)
                put("device_type", info.deviceType)
                put("device_serial_number", info.deviceSerialNumber)
                put("device_name", info.deviceName)
                put("account_name", info.accountName)
                put("home_region", info.homeRegion)
            })
            put("default_target", defaultTarget(context) ?: JSONObject.NULL)
            put("default_author", defaultAuthor(context) ?: JSONObject.NULL)
        }
        prefs(context).edit().putString(KEY_CLIENT, root.toString()).apply()
    }

    private const val KEY_DEFAULT_TARGET = "default_target"
    private const val KEY_DEFAULT_AUTHOR = "default_author"
}
