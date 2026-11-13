package com.duivesteyn.papir.share

import java.util.concurrent.CopyOnWriteArrayList

/**
 * In-process send state shared by [UploadService] and the share confirmation
 * card. The service outlives the activity, so the activity follows a snapshot
 * stream instead of owning the upload.
 */
object SendStatus {

    enum class Phase { IDLE, SENDING, SENT, FAILED }

    data class Snapshot(
        val phase: Phase = Phase.IDLE,
        val title: String = "",
        val index: Int = 0,
        val count: Int = 0,
        val percent: Int = 0,
        val sku: String = "",
        val error: String = "",
    )

    private val listeners = CopyOnWriteArrayList<(Snapshot) -> Unit>()

    @Volatile
    var current: Snapshot = Snapshot()
        private set

    fun update(snapshot: Snapshot) {
        current = snapshot
        listeners.forEach { listener -> runCatching { listener(snapshot) } }
    }

    fun reset() = update(Snapshot())

    fun addListener(listener: (Snapshot) -> Unit) {
        listeners.addIfAbsent(listener)
    }

    fun removeListener(listener: (Snapshot) -> Unit) {
        listeners.remove(listener)
    }
}
