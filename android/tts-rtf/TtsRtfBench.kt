/*
 * edge-llm-bench tts-rtf-v1, Android leg: one synthesis in a fresh process.
 *
 * Instrumentation harness around the sample's own Qwen3TtsEngine (the file in
 * src/main is untouched; its sha256 travels in every record). It does what
 * MainActivity does when "Speak" is tapped — construct the engine over
 * filesDir, call synthesize() — with the same call shape as the Mac leg's
 * worker (scripts/tts_rtf_worker.py): fixed text, explicit language, sampling
 * with a fixed seed. It writes the 24 kHz PCM16 WAV and a timing JSON under
 * the app's external files dir so the host driver (scripts/tts_rtf_android.py)
 * can pull them and run the ASR round trip.
 *
 * Which graphs a launch ran is recorded, not assumed: an engine with the
 * fast-path auto-select (litert-samples 50fb1674) picks the folded MTP and the
 * split codec by file presence in filesDir, so the JSON carries the model graphs
 * the launch could see, the engine's own selection flags (read by reflection;
 * "absent" on an engine without the auto-select) and the graph files the
 * process mapped (/proc/self/maps), all read outside the timed regions. The
 * process's page faults and CPU time across the load and across synthesize()
 * (/proc/self/stat) ride along, so a slow launch can be told apart from one
 * that waited on the flash.
 *
 *   adb shell am instrument -w -r -e text "..." -e language english -e seed 1 \
 *       -e name <slug>_run1 com.google.ai.edge.examples.text_to_speech_lm.test/androidx.test.runner.AndroidJUnitRunner
 */
package com.google.ai.edge.examples.text_to_speech_lm

import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Test
import org.junit.runner.RunWith
import kotlin.math.abs
import kotlin.math.log10
import kotlin.math.sqrt

@RunWith(AndroidJUnit4::class)
class TtsRtfBench {
    private val tag = "Qwen3TtsRtf"

    @Test
    fun synthesizeOnce() {
        val args = InstrumentationRegistry.getArguments()
        val appContext = InstrumentationRegistry.getInstrumentation().targetContext
        val text = args.getString("text") ?: error("-e text is required")
        val language = args.getString("language") ?: "english"
        val greedy = args.getString("greedy") == "1"
        val seed = args.getString("seed")?.toLong() ?: 1L
        val name = args.getString("name") ?: "tts_rtf"
        val outDir = File(appContext.getExternalFilesDir(null), "tts-rtf").apply { mkdirs() }
        val wavFile = File(outDir, "${name}_24k.wav")
        val jsonFile = File(outDir, "$name.json")
        jsonFile.delete(); wavFile.delete()

        val out = JSONObject()
        out.put("name", name)
        out.put("pid", android.os.Process.myPid())
        out.put("text", text); out.put("language", language)
        out.put("seed", if (greedy) JSONObject.NULL else seed); out.put("doSample", !greedy)
        out.put("modelDir", appContext.filesDir.absolutePath)
        // the graph files this launch can see (the auto-select's input)
        out.put("filesDirGraphs", graphListing(appContext.filesDir))

        // ---- load (model files -> three CompiledModels + host tables), timed like the Mac worker
        val stat0 = procStat()
        val tLoad0 = System.nanoTime()
        val engine = Qwen3TtsEngine(appContext.filesDir)
        val loadS = (System.nanoTime() - tLoad0) / 1e9
        val stat1 = procStat()
        out.put("loadSeconds", round3(loadS))
        out.put("vmHwmKbAfterLoad", vmHwmKb())
        // the graphs the engine selected (its own flags) and the graph files it mapped
        val selection = engineSelection(engine)
        out.put("engineSelection", selection)
        out.put("mappedGraphs", mappedGraphs(appContext.packageName))

        // ---- the sample's own tokenizer self-test (MainActivity runs it at startup)
        out.put("tokenizerSelfTest", tokenizerSelfTest(engine, appContext))

        // ---- synthesis: the MainActivity call with explicit language + a fixed seed
        val stat2 = procStat()
        val t0 = System.nanoTime()
        val result = engine.synthesize(text, language = language, greedy = greedy, seed = if (greedy) null else seed)
        val synthS = (System.nanoTime() - t0) / 1e9
        val stat3 = procStat()
        // process-wide page faults and CPU time across the load and across synthesize()
        out.put("processCounters", JSONObject()
            .put("load", statDelta(stat0, stat1))
            .put("synthesis", statDelta(stat2, stat3))
            .put("source", "/proc/self/stat minflt / majflt / utime+stime (clock ticks of 1/100 s), all threads"))
        val audio = result.audio
        val audioS = audio.size / Qwen3TtsEngine.SAMPLE_RATE.toDouble()
        out.put("synthesisSeconds", round3(synthS))
        out.put("audioSeconds", round3(audioS))
        out.put("numFrames", result.frames)
        out.put("sampleRate", Qwen3TtsEngine.SAMPLE_RATE)
        out.put("prefillSeconds", result.prefillMs / 1000.0)
        out.put("talkerSeconds", result.talkerMs / 1000.0)
        out.put("mtpSeconds", result.mtpMs / 1000.0)
        out.put("codecSeconds", result.codecMs / 1000.0)
        val stageS = (result.prefillMs + result.talkerMs + result.mtpMs + result.codecMs) / 1000.0
        out.put("pipelineRTF", if (audioS > 0) round4(stageS / audioS) else JSONObject.NULL)
        var peak = 0f; var sumSq = 0.0
        for (s in audio) { val a = abs(s); if (a > peak) peak = a; sumSq += s.toDouble() * s.toDouble() }
        out.put("peakAbs", peak.toDouble())
        out.put("rmsDbfs", if (audio.isNotEmpty()) 20 * log10(sqrt(sumSq / audio.size) + 1e-12) else JSONObject.NULL)
        out.put("vmHwmKbAfterSynthesis", vmHwmKb())
        val folded = selection.opt("mtpFolded") == true
        val split = selection.opt("codecSplit") == true
        out.put("threadsTalkerMtpCodec",
            "talker 4, mtp " + (if (folded) "4 (mtp_folded.tflite)" else "2 (mtp_fp32.tflite)") +
                ", codec " + (if (split) "A 4 fp32 + B 4 FORCE_FP16 (codec_partA/B.tflite)" else "4 (codec_decoder_fp32.tflite)") +
                " (Qwen3TtsEngine's own values)")
        out.put("maxFrames", Qwen3TtsEngine.MAX_FRAMES)
        out.put("speakerFile", "demo_speaker.npy")

        writeWav(wavFile, audio, Qwen3TtsEngine.SAMPLE_RATE)
        out.put("wav", wavFile.absolutePath)
        engine.close()
        jsonFile.writeText(out.toString(1))
        Log.i(tag, "done $name: load=${round3(loadS)}s synth=${round3(synthS)}s audio=${round3(audioS)}s frames=${result.frames}")
    }

    private fun tokenizerSelfTest(e: Qwen3TtsEngine, ctx: android.content.Context): String {
        return try {
            val cases = JSONArray(ctx.assets.open("tokenizer_test_vectors.json").bufferedReader().readText())
            var ok = true
            for (i in 0 until cases.length()) {
                val c = cases.getJSONObject(i)
                val want = c.getJSONArray("ids")
                val got = e.encodeText(c.getString("text"))
                if (!(got.size == want.length() && got.indices.all { got[it] == want.getInt(it) })) ok = false
            }
            if (ok) "PASS (${cases.length()} cases)" else "FAIL"
        } catch (t: Throwable) {
            "error: ${t.message}"
        }
    }

    /** Name and size of every model graph file in [dir] (parked copies included). */
    private fun graphListing(dir: File): JSONArray {
        val arr = JSONArray()
        dir.listFiles()
            ?.filter { it.name.endsWith(".tflite") || it.name.endsWith(".tflite.parked") }
            ?.sortedBy { it.name }
            ?.forEach { arr.put(JSONObject().put("name", it.name).put("bytes", it.length())) }
        return arr
    }

    /** The engine's own graph selection: its private mtpFolded / codecSplit flags. */
    private fun engineSelection(e: Qwen3TtsEngine): JSONObject {
        val o = JSONObject()
        for (name in listOf("mtpFolded", "codecSplit")) {
            try {
                val f = e.javaClass.getDeclaredField(name)
                f.isAccessible = true
                o.put(name, f.getBoolean(e))
            } catch (t: NoSuchFieldException) {
                o.put(name, "absent (engine without the auto-select)")
            } catch (t: Throwable) {
                o.put(name, "error: ${t.javaClass.simpleName}: ${t.message}")
            }
        }
        return o
    }

    /** The .tflite files of this app that the process has mapped, from /proc/self/maps. */
    private fun mappedGraphs(pkg: String): JSONArray {
        val arr = JSONArray()
        try {
            File("/proc/self/maps").readLines()
                .mapNotNull { it.trim().split(Regex("\\s+"), limit = 6).getOrNull(5) }
                .filter { it.contains(pkg) && it.endsWith(".tflite") }
                .distinct().sorted()
                .forEach { arr.put(it) }
        } catch (t: Throwable) {
            arr.put("error: ${t.message}")
        }
        return arr
    }

    /** [minflt, majflt, utime + stime ticks] of this process, from /proc/self/stat (all threads). */
    private fun procStat(): LongArray {
        return try {
            val s = File("/proc/self/stat").readText()
            val f = s.substring(s.lastIndexOf(')') + 2).trim().split(" ")
            // after "(comm) ": state=0 … minflt=7, majflt=9, utime=11, stime=12
            longArrayOf(f[7].toLong(), f[9].toLong(), f[11].toLong() + f[12].toLong())
        } catch (t: Throwable) {
            longArrayOf(-1L, -1L, -1L)
        }
    }

    private fun statDelta(a: LongArray, b: LongArray): JSONObject =
        if (a[0] < 0 || b[0] < 0) JSONObject().put("error", "unreadable /proc/self/stat")
        else JSONObject().put("minorFaults", b[0] - a[0]).put("majorFaults", b[1] - a[1])
            .put("cpuSeconds", (b[2] - a[2]) / 100.0)

    /** Peak resident set of this process so far (kB), from /proc/self/status. */
    private fun vmHwmKb(): Long {
        return try {
            File("/proc/self/status").readLines().firstOrNull { it.startsWith("VmHWM:") }
                ?.split(Regex("\\s+"))?.getOrNull(1)?.toLong() ?: -1L
        } catch (t: Throwable) { -1L }
    }

    private fun writeWav(f: File, audio: FloatArray, rate: Int) {
        val dataBytes = audio.size * 2
        val buf = ByteBuffer.allocate(44 + dataBytes).order(ByteOrder.LITTLE_ENDIAN)
        buf.put("RIFF".toByteArray()); buf.putInt(36 + dataBytes); buf.put("WAVE".toByteArray())
        buf.put("fmt ".toByteArray()); buf.putInt(16); buf.putShort(1); buf.putShort(1)
        buf.putInt(rate); buf.putInt(rate * 2); buf.putShort(2); buf.putShort(16)
        buf.put("data".toByteArray()); buf.putInt(dataBytes)
        for (s in audio) {
            val v = (s.coerceIn(-1f, 1f) * 32767f).toInt()
            buf.putShort(v.toShort())
        }
        RandomAccessFile(f, "rw").use { it.write(buf.array()) }
    }

    private fun round3(x: Double) = Math.round(x * 1000.0) / 1000.0
    private fun round4(x: Double) = Math.round(x * 10000.0) / 10000.0
}
