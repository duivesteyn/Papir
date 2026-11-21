package com.duivesteyn.papir.share

import android.content.ComponentName
import android.content.Context
import android.content.pm.PackageManager
import com.duivesteyn.papir.core.Config
import com.duivesteyn.papir.core.DeviceKind

/**
 * Keeps the share-sheet entry wearing the mark of the Kindle the user picked.
 *
 * Android takes a share target's icon from the manifest while the chooser is
 * being built, and there is no API to change it afterwards. The manifest
 * therefore declares one `<activity-alias>` per silhouette — all of them over
 * [SendActivity], each with the same intent filter — and this object leaves
 * exactly one enabled. The state survives reboots and needs no notification
 * hack or overlay.
 */
object ShareTargets {

    private const val SUBPACKAGE = "share"
    private const val PREFIX = "ShareTarget"

    /** The mark the current destination asks for. */
    fun desired(context: Context): DeviceKind {
        // Config returns null for "all devices", which is also the signed-out
        // and first-run state: no single Kindle, so Papir wears its own mark.
        val target = Config.defaultTarget(context) ?: return DeviceKind.PAPIR
        val name = Config.defaultTargetName(context) ?: return DeviceKind.GENERIC
        return DeviceKind.forDeviceName(name)
    }

    fun component(context: Context, kind: DeviceKind): ComponentName =
        ComponentName(context, "${context.packageName}.$SUBPACKAGE.$PREFIX${kind.alias}")

    /**
     * Reconcile only when the choice changed. Called from settings and on resume,
     * so the common path is two preference reads.
     */
    fun sync(context: Context) {
        if (Config.shareKind(context) == desired(context).slug) return
        reconcile(context)
    }

    /**
     * Apply the choice unconditionally. Run once per process start: a sideloaded
     * upgrade resets every alias to its manifest default, and a stale memo must
     * not be allowed to hide the user's Kindle.
     */
    fun reconcile(context: Context) {
        val wanted = desired(context)
        val manager = context.packageManager
        // Enable before disabling, so the sheet never briefly has no Papir entry.
        setState(manager, context, wanted, PackageManager.COMPONENT_ENABLED_STATE_ENABLED)
        DeviceKind.entries.forEach { kind ->
            if (kind != wanted) {
                setState(manager, context, kind, PackageManager.COMPONENT_ENABLED_STATE_DISABLED)
            }
        }
        Config.setShareKind(context, wanted.slug)
    }

    private fun setState(manager: PackageManager, context: Context, kind: DeviceKind, state: Int) {
        val name = component(context, kind)
        val current = runCatching { manager.getComponentEnabledSetting(name) }.getOrNull()
        if (current == state) return
        // DONT_KILL_APP: the choice is a cosmetic change to one component, not a
        // reason to restart the process mid-send.
        runCatching { manager.setComponentEnabledSetting(name, state, PackageManager.DONT_KILL_APP) }
    }
}
