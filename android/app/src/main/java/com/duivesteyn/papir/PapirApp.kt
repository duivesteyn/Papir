package com.duivesteyn.papir

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import java.io.File
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

class PapirApp : Application() {

    /** Shared worker pool: sending must outlive the activity that started it. */
    val io: ExecutorService = Executors.newCachedThreadPool()

    override fun onCreate() {
        super.onCreate()
        createChannels(this)
        sweepInbox(cacheDir)
    }

    private fun createChannels(context: Context) {
        val manager = context.getSystemService(NotificationManager::class.java) ?: return
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_SENDING,
                "Sending",
                NotificationManager.IMPORTANCE_LOW,
            ).apply {
                description = "Upload progress while a document travels to Kindle"
                setShowBadge(false)
            }
        )
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_RESULTS,
                "Send results",
                NotificationManager.IMPORTANCE_DEFAULT,
            ).apply {
                description = "Confirmation, SKU and errors for each document"
            }
        )
    }

    /** Files left behind by a crash or a cancelled share shouldn't linger. */
    private fun sweepInbox(cacheDir: File) {
        val inbox = File(cacheDir, INBOX_DIR)
        val cutoff = System.currentTimeMillis() - MAX_AGE_MS
        inbox.listFiles()?.forEach { entry ->
            if (entry.lastModified() >= cutoff) return@forEach
            if (entry.isDirectory) entry.deleteRecursively() else entry.delete()
        }
    }

    companion object {
        const val INBOX_DIR = "inbox"
        const val CHANNEL_SENDING = "sending"
        const val CHANNEL_RESULTS = "results"
        private const val MAX_AGE_MS = 24L * 60 * 60 * 1000
    }
}
