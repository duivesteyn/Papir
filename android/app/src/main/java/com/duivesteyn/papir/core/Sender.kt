package com.duivesteyn.papir.core

import android.content.Context
import java.io.File

/**
 * One shared path from a file in the phone's cache to Amazon's service, with
 * the same defaults the CLI and Mac app use: stored device, stored author,
 * cleaned-up title.
 */
object Sender {

    /** Serial list for a send: stored device, or every device when none is set. */
    fun resolveTargets(context: Context, info: DeviceInfo, api: KindleApi): List<String> {
        val stored = Config.defaultTarget(context)
        if (!stored.isNullOrEmpty() && stored != ALL_DEVICES) return listOf(stored)

        val devices = try {
            api.ownedDevices(info).also { Config.cacheDevices(context, it) }
        } catch (e: Exception) {
            Config.cachedDevices(context)
        }
        if (devices.isEmpty()) {
            throw PapirException("No Kindles on this account — add one in Amazon, then refresh")
        }
        return devices.map { it.serial }
    }

    /** Upload [file] and return Amazon's SKU. Blocking: call from a worker thread. */
    fun send(
        context: Context,
        file: File,
        api: KindleApi = KindleApi(),
        onProgress: (sent: Long, total: Long) -> Unit = { _, _ -> },
    ): String {
        val info = Config.device(context) ?: throw PapirException("Not signed in")
        val format = Documents.formatFor(file.name)
            ?: throw PapirException("Papir can't send .${Documents.extensionOf(file.name)} files")
        val author = Config.defaultAuthor(context) ?: info.accountName
        val title = Documents.titleFor(file.name)
        val targets = resolveTargets(context, info, api)
        return api.send(
            info = info,
            file = file,
            format = format,
            title = title,
            author = author,
            targets = targets,
            convert = Config.convertPdfs(context),
            onProgress = onProgress,
        )
    }

    fun refreshDevices(context: Context): List<OwnedDevice> {
        val info = Config.device(context) ?: throw PapirException("Not signed in")
        return KindleApi().ownedDevices(info).also { Config.cacheDevices(context, it) }
    }

    fun signOut(context: Context) {
        val info = Config.device(context)
        if (info != null) {
            runCatching { KindleApi().logout(info) }
        }
        Config.clear(context)
    }

    const val ALL_DEVICES = "all"
}
