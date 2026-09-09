package io.github.johnrocky.edgellmbench

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Build
import android.os.PowerManager
import java.io.File
import java.util.concurrent.atomic.AtomicBoolean

/**
 * The same device facts the native lane records (android/bench/device_probe.py), read from inside
 * the process instead of over adb. Field names and value conventions are kept identical so
 * scripts/build_summary.py sees one Android shape.
 */
object DeviceProbe {
    /** dumpsys thermalservice's status int uses the same scale as PowerManager's thermal status. */
    private val THERMAL_NAMES = mapOf(
        0 to "nominal", 1 to "light", 2 to "moderate", 3 to "severe",
        4 to "critical", 5 to "emergency", 6 to "shutdown",
    )

    data class Thermal(val raw: Int?, val name: String)

    fun thermal(context: Context): Thermal {
        val pm = context.getSystemService(Context.POWER_SERVICE) as? PowerManager
        val raw = if (Build.VERSION.SDK_INT >= 29 && pm != null) pm.currentThermalStatus else null
        return Thermal(raw, raw?.let { THERMAL_NAMES[it] ?: "unknown($it)" } ?: "unavailable")
    }

    data class Battery(val level: Double?, val state: String, val rawStatus: Int?)

    fun battery(context: Context): Battery {
        val intent: Intent? = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val level = intent?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = intent?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
        val plugged = intent?.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) ?: 0
        val status = intent?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
        return Battery(
            level = if (level >= 0 && scale > 0) level.toDouble() / scale else null,
            // native lane: "charging" when any power source is present, else "unplugged"
            state = if (plugged != 0) "charging" else "unplugged",
            rawStatus = if (status >= 0) status else null,
        )
    }

    fun deviceInfo(): Map<String, Any?> = linkedMapOf(
        "modelIdentifier" to Build.MODEL,
        "systemName" to "Android",
        "systemVersion" to Build.VERSION.RELEASE,
        "securityPatch" to Build.VERSION.SECURITY_PATCH,
        "soc" to (if (Build.VERSION.SDK_INT >= 31) Build.SOC_MODEL else null),
        "product" to Build.DEVICE,
        "manufacturer" to Build.MANUFACTURER,
        "buildId" to Build.DISPLAY,
    )

    /** /proc/self/status VmRSS in kB, or null when unreadable. Same basis as the native sampler. */
    fun vmRssKb(): Long? = procStatusKb("VmRSS")

    /** /proc/self/status VmHWM (the process's resident high-water mark) in kB. */
    fun vmHwmKb(): Long? = procStatusKb("VmHWM")

    private fun procStatusKb(key: String): Long? = try {
        File("/proc/self/status").useLines { lines ->
            lines.firstOrNull { it.startsWith("$key:") }
                ?.substringAfter(':')?.trim()?.split(Regex("\\s+"))?.firstOrNull()?.toLongOrNull()
        }
    } catch (e: Exception) {
        null
    }

    /**
     * Samples VmRSS of THIS process every [periodMs] until stopped. The native lane samples the
     * engine process from outside; here the engine lives inside the instrumentation process, so the
     * series includes the ART runtime and test framework (disclosed in conditions.memoryBasis).
     */
    class RssSampler(private val periodMs: Long = 500) {
        val samplesKb = ArrayList<Long>()
        private val stop = AtomicBoolean(false)
        private var thread: Thread? = null

        fun start(): RssSampler {
            stop.set(false)
            thread = Thread {
                while (!stop.get()) {
                    vmRssKb()?.let { synchronized(samplesKb) { samplesKb.add(it) } }
                    try { Thread.sleep(periodMs) } catch (e: InterruptedException) { break }
                }
            }.apply { isDaemon = true; name = "rss-sampler"; start() }
            return this
        }

        fun stop(): List<Long> {
            stop.set(true)
            thread?.interrupt()
            thread?.join(2000)
            return synchronized(samplesKb) { samplesKb.toList() }
        }
    }

    fun medianMb(samplesKb: List<Long>): Double? {
        if (samplesKb.isEmpty()) return null
        val s = samplesKb.sorted()
        val mid = s.size / 2
        val med = if (s.size % 2 == 1) s[mid].toDouble() else (s[mid - 1] + s[mid]) / 2.0
        return med / 1024.0
    }
}
