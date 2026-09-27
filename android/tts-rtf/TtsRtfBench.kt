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

        // ---- load (model files -> three CompiledModels + host tables), timed like the Mac worker
        val tLoad0 = System.nanoTime()
        val engine = Qwen3TtsEngine(appContext.filesDir)
        val loadS = (System.nanoTime() - tLoad0) / 1e9
        out.put("loadSeconds", round3(loadS))
        out.put("vmHwmKbAfterLoad", vmHwmKb())

        // ---- the sample's own tokenizer self-test (MainActivity runs it at startup)
        out.put("tokenizerSelfTest", tokenizerSelfTest(engine, appContext))

        // ---- synthesis: the MainActivity call with explicit language + a fixed seed
        val t0 = System.nanoTime()
        val result = engine.synthesize(text, language = language, greedy = greedy, seed = if (greedy) null else seed)
        val synthS = (System.nanoTime() - t0) / 1e9
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
        out.put("threadsTalkerMtpCodec", "4/2/4 (Qwen3TtsEngine.load(): talker 4, mtp 2, codec 4)")
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
