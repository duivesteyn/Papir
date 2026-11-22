package com.duivesteyn.papir.share

import android.app.Notification
import android.graphics.drawable.Icon
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import com.duivesteyn.papir.PapirApp
import com.duivesteyn.papir.R
import com.duivesteyn.papir.core.Documents
import com.duivesteyn.papir.core.Sender
import com.duivesteyn.papir.ui.MainActivity
import java.io.File

/**
 * Uploads one or more cached documents while the user is already back in their
 * reading app. Progress and the outcome live in notifications; there is no in-app
 * screen to return to.
 */
class UploadService : Service() {

    private val app: PapirApp by lazy { application as PapirApp }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val paths = intent?.getStringArrayListExtra(EXTRA_PATHS).orEmpty().filter { it.isNotBlank() }
        if (paths.isEmpty()) {
            stopSelf(startId)
            return START_NOT_STICKY
        }
        startForegroundCompat(
            progressNotification(
                index = 0,
                count = paths.size,
                title = Documents.titleFor(File(paths.first()).name),
                percent = null,
            )
        )
        SendStatus.reset()
        SendStatus.update(
            SendStatus.Snapshot(
                phase = SendStatus.Phase.SENDING,
                title = Documents.titleFor(File(paths.first()).name),
                count = paths.size,
            )
        )
        app.io.execute {
            try {
                sendAll(paths, startId)
            } finally {
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf(startId)
            }
        }
        return START_NOT_STICKY
    }

    private fun sendAll(paths: List<String>, startId: Int) {
        var delivered = 0
        val failures = mutableListOf<String>()
        val skus = mutableListOf<String>()

        paths.forEachIndexed { index, path ->
            val file = File(path)
            if (!file.isFile) {
                failures += "${file.name} — file is no longer available"
                return@forEachIndexed
            }
            val title = Documents.titleFor(file.name)
            notifyProgress(index, paths.size, title, 0)
            SendStatus.update(
                SendStatus.Snapshot(
                    phase = SendStatus.Phase.SENDING,
                    title = title,
                    index = index,
                    count = paths.size,
                )
            )

            var lastPercent = 0
            try {
                val sku = Sender.send(this, file) { sent, total ->
                    val percent = if (total <= 0L) 0 else ((sent * 100) / total).toInt()
                    if (percent >= lastPercent + 4 || percent == 100) {
                        lastPercent = percent
                        notifyProgress(index, paths.size, title, percent)
                        SendStatus.update(
                            SendStatus.Snapshot(
                                phase = SendStatus.Phase.SENDING,
                                title = title,
                                index = index,
                                count = paths.size,
                                percent = percent,
                            )
                        )
                    }
                }
                delivered++
                if (sku.isNotEmpty()) skus += sku
                file.delete()
            } catch (e: Exception) {
                failures += "$title — ${e.message ?: "couldn't send"}"
            }
        }
        val lastTitle = paths.lastOrNull()
            ?.let { Documents.titleFor(File(it).name) }
            .orEmpty()
        SendStatus.update(
            if (failures.isEmpty()) {
                SendStatus.Snapshot(
                    phase = SendStatus.Phase.SENT,
                    title = lastTitle,
                    count = paths.size,
                    sku = skus.lastOrNull().orEmpty(),
                )
            } else {
                SendStatus.Snapshot(
                    phase = SendStatus.Phase.FAILED,
                    title = lastTitle,
                    count = paths.size,
                    error = failures.first(),
                )
            }
        )
        postResult(paths, delivered, failures, skus)
    }

    // ------------------------------------------------------------ notifications

    private fun progressNotification(
        index: Int,
        count: Int,
        title: String,
        percent: Int?,
    ): Notification {
        val counter = if (count > 1) "${index + 1} of $count · " else ""
        val detail = when (percent) {
            null -> "Preparing…"
            100 -> "Finishing…"
            else -> "$percent%"
        }
        return Notification.Builder(this, PapirApp.CHANNEL_SENDING)
            .setSmallIcon(R.drawable.ic_stat_papir)
            .setColor(getColor(R.color.papir_ink_dim))
            .setContentTitle("Sending to Kindle")
            .setContentText("$counter$title · $detail")
            .setProgress(100, percent ?: 0, percent == null)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setCategory(Notification.CATEGORY_PROGRESS)
            .setContentIntent(openAppIntent())
            .build()
    }

    private fun notifyProgress(index: Int, count: Int, title: String, percent: Int?) {
        manager.notify(
            NOTIFICATION_PROGRESS,
            progressNotification(index, count, title, percent),
        )
    }

    private fun postResult(
        paths: List<String>,
        delivered: Int,
        failures: List<String>,
        skus: List<String>,
    ) {
        val builder = Notification.Builder(this, PapirApp.CHANNEL_RESULTS)
            .setSmallIcon(R.drawable.ic_stat_papir)
            .setColor(getColor(R.color.papir_ink_dim))
            .setAutoCancel(true)
            .setCategory(Notification.CATEGORY_STATUS)
            .setContentIntent(openAppIntent())

        when {
            failures.isEmpty() -> {
                builder.setContentTitle(
                    if (delivered == 1) "Sent to Kindle" else "Sent $delivered documents"
                )
                val lines = buildList {
                    if (delivered == 1) add("Amazon accepted the document.")
                    if (skus.isNotEmpty()) add("SKU ${skus.first()}")
                    if (skus.size > 1) skus.drop(1).forEach { add("SKU $it") }
                }
                builder.setContentText(lines.firstOrNull().orEmpty())
                builder.setStyle(Notification.BigTextStyle().bigText(lines.joinToString("\n")))
            }
            delivered > 0 -> {
                builder.setContentTitle("Sent $delivered, ${
                    if (failures.size == 1) "1 failed" else "${failures.size} failed"
                }")
                builder.setContentText(failures.first())
                builder.setStyle(Notification.BigTextStyle().bigText(failures.joinToString("\n")))
                attachRetry(builder, paths)
            }
            else -> {
                builder.setContentTitle("Couldn't send to Kindle")
                builder.setContentText(failures.firstOrNull() ?: "Try again")
                builder.setStyle(Notification.BigTextStyle().bigText(failures.joinToString("\n")))
                attachRetry(builder, paths)
            }
        }
        manager.notify(NOTIFICATION_RESULT, builder.build())
    }

    private fun attachRetry(builder: Notification.Builder, paths: List<String>) {
        val remaining = paths.filter { File(it).isFile }
        if (remaining.isEmpty()) return
        val retry = Intent(this, UploadService::class.java).apply {
            putStringArrayListExtra(EXTRA_PATHS, ArrayList(remaining))
        }
        val pending = PendingIntent.getService(
            this,
            remaining.joinToString().hashCode(),
            retry,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        builder.addAction(
            Notification.Action.Builder(
                Icon.createWithResource(this, R.drawable.ic_stat_papir),
                "Retry",
                pending,
            ).build()
        )
    }

    private fun openAppIntent(): PendingIntent {
        val intent = Intent(this, MainActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        }
        return PendingIntent.getActivity(
            this,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    private fun startForegroundCompat(notification: Notification) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(
                NOTIFICATION_PROGRESS,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC,
            )
        } else {
            startForeground(NOTIFICATION_PROGRESS, notification)
        }
    }

    private val manager: NotificationManager
        get() = getSystemService(NotificationManager::class.java)

    companion object {
        const val EXTRA_PATHS = "com.duivesteyn.papir.extra.PATHS"
        private const val NOTIFICATION_PROGRESS = 4100
        private const val NOTIFICATION_RESULT = 4101

        fun start(context: Context, paths: List<String>) {
            if (paths.isEmpty()) return
            val intent = Intent(context, UploadService::class.java).apply {
                putStringArrayListExtra(EXTRA_PATHS, ArrayList(paths))
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }
    }
}
