package com.duivesteyn.papir.core

import android.net.Uri
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLDecoder
import java.net.URLEncoder
import java.util.Locale
import javax.net.ssl.HttpsURLConnection
import javax.xml.parsers.DocumentBuilderFactory
import org.w3c.dom.Element

/** Amazon refused or could not be reached. [detail] is the server body, already truncated. */
class PapirException(message: String, val detail: String? = null) : IOException(message)

/**
 * The Send-to-Kindle private protocol, ported from papir's Python `api.py`.
 *
 * Deliberately no third-party HTTP library: HttpURLConnection keeps the APK
 * small and the request bytes exactly what the signer signed.
 */
class KindleApi(
    private val connectTimeoutMs: Int = 30_000,
    private val readTimeoutMs: Int = 90_000,
) {

    fun signInUrl(verifier: String): String {
        val params = linkedMapOf(
            "openid.claimed_id" to "http://specs.openid.net/auth/2.0/identifier_select",
            "openid.ns.oa2" to "http://www.amazon.com/ap/ext/oauth/2",
            "openid.ns" to "http://specs.openid.net/auth/2.0",
            "openid.identity" to "http://specs.openid.net/auth/2.0/identifier_select",
            "openid.oa2.client_id" to "device:$CLIENT_ID",
            "openid.mode" to "checkid_setup",
            "openid.oa2.scope" to "device_auth_access",
            "openid.oa2.response_type" to "code",
            "openid.oa2.code_challenge" to Pkce.challenge(verifier),
            "openid.oa2.code_challenge_method" to "S256",
            "openid.return_to" to "https://www.amazon.com/gp/sendtokindle",
            "openid.ns.pape" to "http://specs.openid.net/extensions/pape/1.0",
            "openid.pape.max_auth_age" to "0",
            "accountStatusPolicy" to "P1",
            "openid.assoc_handle" to "amzn_device_na",
            "pageId" to "amzn_device_common_dark",
            "disableLoginPrepopulate" to "1",
        )
        val query = params.entries.joinToString("&") { (key, value) ->
            "${URLEncoder.encode(key, "UTF-8")}=${URLEncoder.encode(value, "UTF-8")}"
        }
        return "https://www.amazon.com/ap/signin?$query"
    }

    /**
     * Pull `openid.oa2.authorization_code` out of the final redirect, or accept
     * a bare code pasted from the browser (the CLI does the same).
     */
    fun parseAuthorizationCode(input: String): String? {
        val text = input.trim().trim('\'', '"').trim()
        if (text.isEmpty()) return null
        if (!text.contains("://") && !text.contains('?') && !text.contains('=') &&
            !text.contains(' ') && text.length < 200
        ) {
            return text
        }
        Uri.parse(text).getQueryParameter("openid.oa2.authorization_code")?.let { return it }
        val match = CODE_IN_URL.find(text) ?: return null
        return try {
            URLDecoder.decode(match.groupValues[1], "UTF-8")
        } catch (e: IllegalArgumentException) {
            match.groupValues[1]
        }
    }

    fun exchangeToken(authorizationCode: String, codeVerifier: String): String {
        val body = buildString {
            append("{\"app_name\":\"Unknown\",")
            append("\"client_domain\":\"DeviceLegacy\",")
            append("\"client_id\":").append(q(CLIENT_ID)).append(',')
            append("\"code_algorithm\":\"SHA-256\",")
            append("\"code_verifier\":").append(q(codeVerifier)).append(',')
            append("\"requested_token_type\":\"access_token\",")
            append("\"source_token\":").append(q(authorizationCode)).append(',')
            append("\"source_token_type\":\"authorization_code\"}")
        }
        val text = post(
            "https://$TOKEN_HOST/auth/token",
            body,
            mapOf(
                "Content-Type" to "application/json",
                "Accept-Language" to "en-US",
                "x-amzn-identity-auth-domain" to TOKEN_HOST,
                "User-Agent" to USER_AGENT,
            ),
        )
        val token = JSONObject(text).optString("access_token", "")
        if (token.isEmpty()) throw PapirException("Amazon did not return an access token", text.take(500))
        return token
    }

    fun registerDevice(accessToken: String, serial: String, deviceName: String): DeviceInfo {
        val xml = buildString {
            append("<?xml version='1.0' encoding='UTF-8'?><request><parameters>")
            append("<deviceType>").append(xmlEscape(DEVICE_TYPE)).append("</deviceType>")
            append("<deviceSerialNumber>").append(xmlEscape(serial)).append("</deviceSerialNumber>")
            append("<pid>").append(xmlEscape(PID)).append("</pid>")
            append("<authToken>").append(xmlEscape(accessToken)).append("</authToken>")
            append("<authTokenType>AccessToken</authTokenType>")
            append("<softwareVersion>").append(xmlEscape(SOFTWARE_VERSION)).append("</softwareVersion>")
            append("<os_version>").append(xmlEscape(OS_VERSION)).append("</os_version>")
            append("<device_model>").append(xmlEscape(deviceName)).append("</device_model>")
            append("</parameters></request>")
        }
        val root = postXml("https://$FIRS_HOST/FirsProxy/registerDeviceWithToken", xml)
        val fields = HashMap<String, String>()
        val nodes = root.childNodes
        for (i in 0 until nodes.length) {
            val node = nodes.item(i)
            if (node.nodeType == org.w3c.dom.Node.ELEMENT_NODE) {
                fields[node.nodeName] = node.textContent ?: ""
            }
        }
        val privateKey = fields["device_private_key"].orEmpty()
        val adpToken = fields["adp_token"].orEmpty()
        if (privateKey.isEmpty() || adpToken.isEmpty()) {
            throw PapirException("Registration response was incomplete")
        }
        return DeviceInfo(
            devicePrivateKey = privateKey,
            adpToken = adpToken,
            deviceType = fields["device_type"] ?: DEVICE_TYPE,
            deviceSerialNumber = serial,
            deviceName = deviceName,
            accountName = fields["name"].orEmpty(),
            homeRegion = fields["home_region"].orEmpty(),
        )
    }

    fun ownedDevices(info: DeviceInfo): List<OwnedDevice> {
        val text = signedPost("/GetListOfOwnedDevices", info, withClientInfo(""))
        val array = JSONObject(text).optJSONArray("ownedDevices") ?: return emptyList()
        return (0 until array.length()).mapNotNull { index ->
            val item = array.optJSONObject(index) ?: return@mapNotNull null
            val serial = item.optString("deviceSerialNumber", "")
            if (serial.isEmpty()) null else OwnedDevice(item.optString("deviceName", serial), serial)
        }
    }

    /**
     * Upload one prepared file and hand it to Amazon. Returns the SKU.
     */
    fun send(
        info: DeviceInfo,
        file: File,
        format: String,
        title: String,
        author: String,
        targets: List<String>,
        convert: Boolean,
        onProgress: (sent: Long, total: Long) -> Unit = { _, _ -> },
    ): String {
        val size = file.length()
        if (size <= 0L) throw PapirException("That file is empty")

        val uploadInfo = JSONObject(
            signedPost("/GetUploadUrl", info, withClientInfo("\"fileSize\":$size"))
        )
        val uploadUrl = uploadInfo.optString("uploadUrl", "")
        val stkToken = uploadInfo.optString("stkToken", "")
        if (uploadUrl.isEmpty() || stkToken.isEmpty()) {
            throw PapirException("Amazon did not return an upload slot")
        }

        upload(uploadUrl, file, size, onProgress)

        val body = buildString {
            append('{')
            append("\"ClientInfo\":").append(CLIENT_INFO_JSON)
            append(",\"DocumentMetadata\":{")
            append("\"author\":").append(q(author))
            append(",\"crc32\":0")
            append(",\"inputFormat\":").append(q(format))
            append(",\"title\":").append(q(title))
            append("},\"archive\":true")
            append(",\"forceConvert\":").append(convert)
            append(",\"stkToken\":").append(q(stkToken))
            append(",\"targetDevices\":[").append(targets.joinToString(",") { q(it) }).append("]")
            append('}')
        }
        val text = signedPost("/SendToKindle", info, body)
        return JSONObject(text).optString("sku", "")
    }

    /** Best-effort server-side unregistration; local credentials are dropped regardless. */
    fun logout(info: DeviceInfo) {
        val path = "/FirsProxy/disownFiona?contentDeleted=false"
        val digest = Signer.digestHeader(info.devicePrivateKey, info.adpToken, "GET", path, "")
        val connection = (URL("https://$FIRS_HOST$path").openConnection() as HttpsURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = connectTimeoutMs
            readTimeout = readTimeoutMs
            setRequestProperty("X-ADP-Request-Digest", digest)
            setRequestProperty("X-ADP-Authentication-Token", info.adpToken)
            setRequestProperty("Accept-Language", "en-US,*")
            setRequestProperty("User-Agent", USER_AGENT)
        }
        try {
            connection.responseCode
            connection.inputStream?.close()
        } catch (ignored: IOException) {
            // Signing out locally matters more than telling Amazon.
        } finally {
            connection.disconnect()
        }
    }

    // ---------------------------------------------------------------- internals

    private fun upload(url: String, file: File, size: Long, onProgress: (Long, Long) -> Unit) {
        val connection = (URL(url).openConnection() as HttpsURLConnection).apply {
            requestMethod = "PUT"
            connectTimeout = connectTimeoutMs
            readTimeout = readTimeoutMs
            doOutput = true
            setFixedLengthStreamingMode(size)
            setRequestProperty("Content-Type", "application/octet-stream")
            setRequestProperty("Accept-Language", "en-US,*")
            setRequestProperty("User-Agent", USER_AGENT)
        }
        try {
            connection.outputStream.use { out ->
                file.inputStream().use { input ->
                    val buffer = ByteArray(64 * 1024)
                    var sent = 0L
                    while (true) {
                        val read = input.read(buffer)
                        if (read < 0) break
                        out.write(buffer, 0, read)
                        sent += read
                        onProgress(sent, size)
                    }
                    out.flush()
                }
            }
            val code = connection.responseCode
            if (code != HttpURLConnection.HTTP_OK) {
                throw PapirException(
                    "Upload failed (HTTP $code)",
                    connection.errorStream?.bufferedReader()?.use { it.readText() }?.take(500),
                )
            }
        } finally {
            connection.disconnect()
        }
    }

    /** Prefix an API body with the ClientInfo block the desktop app always sends. */
    private fun withClientInfo(extraJson: String): String =
        if (extraJson.isEmpty()) {
            "{\"ClientInfo\":$CLIENT_INFO_JSON}"
        } else {
            "{\"ClientInfo\":$CLIENT_INFO_JSON,$extraJson}"
        }

    /** Sign the exact body string that goes on the wire. */
    private fun signedPost(path: String, info: DeviceInfo, body: String): String {
        val signingDate = Signer.signingDate()
        val digest = Signer.digestHeader(
            info.devicePrivateKey, info.adpToken, "POST", path, body, signingDate,
        )
        val headers = mapOf(
            "Content-Type" to "application/json",
            "Accept" to "application/json",
            "X-ADP-Request-Digest" to digest,
            "X-ADP-Authentication-Token" to info.adpToken,
            "Accept-Language" to "en-US,*",
            "User-Agent" to USER_AGENT,
        )
        return post("https://$STK_HOST$path", body, headers)
    }

    private fun post(url: String, body: String, headers: Map<String, String>): String {
        val connection = (URL(url).openConnection() as HttpsURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = connectTimeoutMs
            readTimeout = readTimeoutMs
            doOutput = true
            headers.forEach { (name, value) -> setRequestProperty(name, value) }
        }
        try {
            connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
            if (code !in 200..299) {
                throw PapirException(httpMessage(code), text.take(2000))
            }
            return text
        } finally {
            connection.disconnect()
        }
    }

    private fun postXml(url: String, body: String): Element {
        val text = post(
            url,
            body,
            mapOf(
                "Content-Type" to "text/xml",
                "Accept-Language" to "en-US,*",
                "User-Agent" to USER_AGENT,
            ),
        )
        val factory = DocumentBuilderFactory.newInstance()
        factory.isNamespaceAware = false
        try {
            factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true)
        } catch (ignored: Exception) {
            // Not every platform parser exposes the feature; the body is Amazon's.
        }
        return factory.newDocumentBuilder()
            .parse(ByteArrayInputStream(text.toByteArray(Charsets.UTF_8)))
            .documentElement
    }

    private fun httpMessage(code: Int): String = when (code) {
        401, 403 -> "Amazon rejected the request — try signing in again"
        429 -> "Amazon is rate-limiting; try again in a minute"
        in 500..599 -> "Amazon had a server error ($code)"
        else -> "Amazon returned HTTP $code"
    }

    private fun q(value: String): String = buildString {
        append('"')
        for (ch in value) {
            when (ch) {
                '"' -> append("\\\"")
                '\\' -> append("\\\\")
                '\n' -> append("\\n")
                '\r' -> append("\\r")
                '\t' -> append("\\t")
                else -> if (ch < ' ') {
                    append(String.format(Locale.ROOT, "\\u%04x", ch.code))
                } else {
                    append(ch)
                }
            }
        }
        append('"')
    }

    private fun xmlEscape(value: String): String = value
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")

    private companion object {
        const val CLIENT_ID = "658490dfb190e494030082836775981fa23be0c2425441860352ba0f55915b43002d"
        const val DEVICE_TYPE = "A1K6D1WRW0MALS"
        const val PID = "D21NN3GG"
        const val SOFTWARE_VERSION = "253"
        const val OS_VERSION = "MacOSX_10.14.6_x64"
        const val TOKEN_HOST = "api.amazon.com"
        const val FIRS_HOST = "firs-ta-g7g.amazon.com"
        const val STK_HOST = "stkservice.amazon.com"
        const val USER_AGENT = "Mozilla/5.0"
        const val CLIENT_INFO_JSON =
            "{\"appName\":\"ShellExtension\",\"appVersion\":\"1.1.1.253\"," +
                "\"os\":\"$OS_VERSION\",\"osArchitecture\":\"x64\"}"
        val CODE_IN_URL = Regex("[?&#]openid\\.oa2\\.authorization_code=([^&]+)")
    }
}
