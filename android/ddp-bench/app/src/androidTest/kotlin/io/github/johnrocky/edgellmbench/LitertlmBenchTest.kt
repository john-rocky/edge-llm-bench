package io.github.johnrocky.edgellmbench

import android.content.Context
import android.os.BatteryManager
import android.os.PowerManager
import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.BenchmarkInfo
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.ExperimentalApi
import com.google.ai.edge.litertlm.ExperimentalFlags
import com.google.ai.edge.litertlm.benchmark
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.UUID
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.fail
import org.junit.Test
import org.junit.runner.RunWith

/**
 * edge-llm-bench Route B (docs/ddp-integration.md): one instrumentation test that
 *
 *  1. downloads a `.litertlm` from the Hub onto the device (or uses a pushed file),
 *  2. runs the 8-question correctness gate through the litertlm-android Kotlin API,
 *  3. measures the repo's short-chat task N times (fresh Engine each run) with the engine's own
 *     BenchmarkInfo — prefill / decode tok/s, TTFT, token counts — plus init time and resident memory,
 *  4. writes one schema/result.v1.json record per run (+ its raw log) where adb / DDP can pull it.
 *
 * The test FAILS when the gate fails or a run produced no decode rate — the records stay on disk
 * either way (failed-runs-stay).
 */
@RunWith(AndroidJUnit4::class)
class LitertlmBenchTest {
    companion object {
        private const val TAG = "EDGE_LLM_BENCH"
        const val HARNESS_STAMP = "2026-09-android-ddp-apk-v1"
        private val ISO = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }
        private val FILE_STAMP = SimpleDateFormat("yyyy-MM-dd'T'HH-mm-ss.SSS", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }
    }

    private lateinit var appContext: Context
    private lateinit var testContext: Context

    private fun asset(name: String): String = testContext.assets.open(name).bufferedReader().use { it.readText() }

    @OptIn(ExperimentalApi::class)
    @Test
    fun measure() {
        val inst = InstrumentationRegistry.getInstrumentation()
        appContext = inst.targetContext
        testContext = inst.context
        val args = BenchArgs(InstrumentationRegistry.getArguments())
        Log.i(TAG, "args: ${JSONObject(args.asMap())}")

        // ---- build-time assets: the engine witness and the byte-identical task inputs
        val pin = JSONObject(asset("engine-pin.json"))
        val engineVersion = "litertlm-android:${pin.getString("litertlmVersion")}"
        val engineArtifact = pin.getString("aarSha256")
        val budgets = asset("budgets.tsv").lineSequence().filter { it.contains('\t') }
            .associate { val (t, b) = it.split('\t'); t.trim() to b.trim().toInt() }
        val prompt = if (args.task == "short-chat") asset("short-chat.txt") else null
        val budget = args.maxOutputTokens ?: budgets[args.task]
        val synthetic = Regex("native-benchmark-(\\d+)x(\\d+)").matchEntire(args.task)
        if (prompt == null && synthetic == null) fail("unknown task ${args.task}: short-chat or native-benchmark-<P>x<D>")
        if (prompt != null && budget == null) fail("no output budget for task ${args.task} (prompts/text/budgets.tsv)")

        val backend = when (args.backend) {
            "cpu" -> Backend.CPU()
            "gpu" -> Backend.GPU()
            else -> { fail("backend must be cpu or gpu, got ${args.backend}"); return }
        }
        val arm = "litert-lm-${args.backend}"

        // ---- output: <external files>/edge-llm-bench/<campaign>/app-path-android (adb pull / --paths-to-pull)
        val outDir = File(appContext.getExternalFilesDir(null), "edge-llm-bench/${args.campaign}/app-path-android")
        outDir.mkdirs()
        Log.i(TAG, "output dir: ${outDir.absolutePath}")

        // ---- model: download (Hub) or pushed file; sha256 either way (rows link by artifact hash)
        val modelFile: File
        val modelSha: String
        val hfRevision: String?
        if (args.modelPath != null) {
            modelFile = File(args.modelPath)
            if (!modelFile.isFile) fail("model_path ${args.modelPath} is not a readable file")
            modelSha = HubDownload.sha256(modelFile)
            hfRevision = null
        } else {
            val dest = File(appContext.filesDir, "models/${args.hfRepo.replace('/', '_')}/${args.hfFile}")
            val r = HubDownload.fetch(args.hfRepo, args.hfFile, args.hfRevision, args.hfToken, dest)
            modelFile = r.file; modelSha = r.sha256; hfRevision = r.revision
        }
        Log.i(TAG, "model ${modelFile.name} ${modelFile.length()} bytes sha256=$modelSha revision=$hfRevision")

        // Engine caches live beside neither the model nor the APK: one dir per (artifact, backend),
        // and the native lane's marker scheme decides firstEver (written after the first clean exit).
        val cacheDir = File(appContext.filesDir, "litertlm-cache/${modelSha.take(16)}-${args.backend}").apply { mkdirs() }
        val marker = File(cacheDir, ".cachebuilt")

        ExperimentalFlags.enableBenchmark = true
        val deviceInfo = DeviceProbe.deviceInfo()
        Log.i(TAG, "device: ${JSONObject(deviceInfo)}")

        // ---- 8-question gate (its engine also builds the on-disk caches; not a speed measurement)
        var gateJson: JSONObject? = null
        if (args.gate) {
            val questions = Gate.load(asset("correctness-gate-8.jsonl"))
            val params = Gate.parseParams(args.modelParams, args.hfFile, modelFile.name, args.hfRepo)
            val sizeClass = Gate.sizeClassOf(params)
            Log.i(TAG, "gate size class: ${sizeClass.label} (params=${params ?: "unknown -> strict bar"})")
            val t0 = System.nanoTime()
            var initMs = -1L
            val outcome = try {
                Engine(EngineConfig(modelPath = modelFile.absolutePath, backend = backend,
                    maxNumTokens = args.contextTokens, cacheDir = cacheDir.absolutePath)).use { engine ->
                    engine.initialize()
                    initMs = (System.nanoTime() - t0) / 1_000_000
                    val o = Gate.run(engine, questions, sizeClass, params)
                    marker.writeText("gate ${ISO.format(Date())}\n")
                    o
                }
            } catch (e: Throwable) {
                Log.e(TAG, "gate engine failed", e)
                Gate.Outcome(JSONArray(), 0, 0, questions.size, sizeClass, params, "FAIL", (System.nanoTime() - t0) / 1_000_000)
                    .also { gateJson = Gate.toJson(it).put("error", "${e.javaClass.simpleName}: ${e.message}") }
            }
            gateJson = (gateJson ?: Gate.toJson(outcome)).put("engineInitMS", initMs)
            File(outDir, "gate_${arm}_${args.hfRepo.replace('/', '_')}_${FILE_STAMP.format(Date())}.json")
                .writeText(gateJson.toString(2) + "\n")
            Log.i(TAG, "GATE_JSON " + gateJson.toString())
            Log.i(TAG, "GATE ${outcome.verdict} correct ${outcome.correct}/${outcome.total} form ${outcome.formPassed}/${outcome.total} (${sizeClass.label}: ${gateJson?.optString("rule")})")
        }

        // ---- measurement runs
        var okRuns = 0
        val decodeRates = ArrayList<Double>()
        for (i in 1..args.runs) {
            if (i > 1 && args.cooldownSeconds > 0) Thread.sleep(args.cooldownSeconds * 1000L)
            val firstEver = !marker.exists()
            val thermal0 = DeviceProbe.thermal(appContext)
            val batt = DeviceProbe.battery(appContext)
            val pm = appContext.getSystemService(Context.POWER_SERVICE) as PowerManager
            val screen = if (pm.isInteractive) "on" else "off"
            val sampler = DeviceProbe.RssSampler().start()
            val log = StringBuilder()
            log.append("harness=$HARNESS_STAMP engine=$engineVersion aar=$engineArtifact\n")
            log.append("args=${JSONObject(args.asMap())}\nmodel=${modelFile.absolutePath} sha256=$modelSha\n")
            log.append("run=$i/${args.runs} firstEver=$firstEver thermal0=${thermal0.raw}(${thermal0.name}) battery=${batt.level} ${batt.state}\n")
            val started = Date()
            val t0 = System.nanoTime()
            var info: BenchmarkInfo? = null
            var initMs: Long? = null
            var genWallMs: Long? = null
            var reply: String? = null
            var failure: String? = null
            try {
                if (synthetic != null) {
                    val (p, d) = synthetic.destructured
                    info = benchmark(modelPath = modelFile.absolutePath, backend = backend,
                        prefillTokens = p.toInt(), decodeTokens = d.toInt(), cacheDir = cacheDir.absolutePath)
                    genWallMs = (System.nanoTime() - t0) / 1_000_000
                } else {
                    Engine(EngineConfig(modelPath = modelFile.absolutePath, backend = backend,
                        maxNumTokens = args.contextTokens, cacheDir = cacheDir.absolutePath)).use { engine ->
                        engine.initialize()
                        initMs = (System.nanoTime() - t0) / 1_000_000
                        // sampler = null -> engine default, the same regime as the native lane's
                        // litert_lm_main (no sampler flags exist there); disclosed in conditions.sampler
                        engine.createConversation(ConversationConfig(maxOutputToken = budget)).use { conv ->
                            val t1 = System.nanoTime()
                            reply = conv.sendMessage(prompt!!).toString()
                            genWallMs = (System.nanoTime() - t1) / 1_000_000
                            info = conv.getBenchmarkInfo()
                        }
                    }
                }
                if (!marker.exists()) marker.writeText("run$i ${ISO.format(Date())}\n")
            } catch (e: Throwable) {
                failure = "${e.javaClass.simpleName}: ${e.message}"
                Log.e(TAG, "run $i failed", e)
                log.append("EXCEPTION ${Log.getStackTraceString(e)}\n")
            }
            val elapsedS = (System.nanoTime() - t0) / 1e9
            val samples = sampler.stop()
            val thermal1 = DeviceProbe.thermal(appContext)
            val hwmKb = DeviceProbe.vmHwmKb()

            log.append("engineInitMS=$initMs generateWallMS=$genWallMs elapsedS=${"%.1f".format(elapsedS)}\n")
            log.append("BenchmarkInfo=$info\n")
            log.append("thermal1=${thermal1.raw}(${thermal1.name}) VmHWM_kB=$hwmKb\n")
            log.append("VmRSS_kB samples (${samples.size} @0.5s): ${samples.joinToString(" ")}\n")
            if (reply != null) log.append("=== reply ===\n$reply\n=== end reply ===\n")

            val metrics = JSONObject()
            info?.let { bi ->
                metrics.put("firstTokenLatencyMS", bi.timeToFirstTokenInSecond * 1000.0)
                metrics.put("promptTokensPerSecond", bi.lastPrefillTokensPerSecond)
                metrics.put("decodeTokensPerSecond", bi.lastDecodeTokensPerSecond)
                metrics.put("promptTokenCount", bi.lastPrefillTokenCount)
                metrics.put("generatedTokenCount", bi.lastDecodeTokenCount)
                metrics.put("engineInitMS", bi.initTimeInSecond * 1000.0)
                val wall = genWallMs
                if (wall != null && bi.lastDecodeTokenCount > 0) {
                    val decodeWallS = wall / 1000.0 - bi.timeToFirstTokenInSecond
                    if (decodeWallS > 0) metrics.put("decodeTokensPerSecondWallClock", bi.lastDecodeTokenCount / decodeWallS)
                }
            }
            metrics.put("coldRun", true)
            if (firstEver) metrics.put("firstEver", true)
            metrics.put("harnessStamp", HARNESS_STAMP)
            metrics.put("initialThermalState", thermal0.name)
            metrics.put("finalThermalState", thermal1.name)
            DeviceProbe.medianMb(samples)?.let { metrics.put("memoryMedianResidentMB", it) }
            hwmKb?.let { metrics.put("memoryPeakResidentMB", it / 1024.0) }

            val record = JSONObject()
            record.put("schemaVersion", 1)
            record.put("id", UUID.randomUUID().toString())
            record.put("runtime", arm)
            record.put("engineVersion", engineVersion)
            record.put("engineArtifact", engineArtifact)
            record.put("model", JSONObject().apply {
                put("id", if (args.modelPath != null) "local-file:${modelFile.name}" else args.hfRepo)
                hfRevision?.let { put("hfRevision", it) }
                put("quantization", quantLabel(modelFile.name))
                put("file", modelFile.name)
                put("sha256", modelSha)
                put("bytes", modelFile.length())
                if (args.modelPath == null) put("sourceUrl", "https://huggingface.co/${args.hfRepo}/resolve/${hfRevision ?: args.hfRevision}/${args.hfFile}")
            })
            record.put("task", args.task)
            record.put("timestamp", ISO.format(started))
            record.put("device", JSONObject(deviceInfo).apply {
                put("batteryLevel", batt.level ?: JSONObject.NULL)
                put("batteryState", batt.state)
            })
            record.put("conditions", JSONObject().apply {
                put("sampler", if (synthetic != null) "n/a (Kotlin benchmark(); prefill/decode token counts fixed)" else "engine-default")
                if (budget != null && synthetic == null) put("maxOutputTokens", budget)
                put("contextTokens", args.contextTokens ?: "bundle-default")
                put("cpuAffinity", "none (in-process instrumentation; taskset is not available to an app)")
                put("engineLifecycle", "fresh Engine per run inside ONE instrumentation process (on-disk caches kept; the gate's engine builds them first)")
                put("memoryBasis", "resident-vmrss of the instrumentation process (engine + ART runtime + test framework), 0.5 s samples")
                put("thermalRawStatus", thermal0.raw ?: JSONObject.NULL)
                put("thermalRawStatusFinal", thermal1.raw ?: JSONObject.NULL)
                put("screen", screen)
                put("powerSource", powerSourceLabel(appContext))
                put("elapsedSeconds", Math.round(elapsedS * 10) / 10.0)
                put("exitCode", if (failure == null) 0 else 1)
                if (failure != null) put("failureDetail", failure)
                initMs?.let { put("engineInitWallMS", it) }
                genWallMs?.let { put("generateWallMS", it) }
                put("instrumentationArgs", JSONObject(args.asMap()))
            })
            record.put("metrics", metrics)
            gateJson?.let { record.put("quality", JSONObject().put("gate", it)) }
            val stamp = FILE_STAMP.format(started)
            val base = "${arm}_${args.hfRepo.replace('/', '_')}_${args.task}_${stamp}_run$i"
            record.put("provenance", JSONObject().apply {
                put("rawLog", "$base.log")
                put("harness", "android/ddp-bench (LitertlmBenchTest)")
                put("campaign", args.campaign)
                put("engineAar", pin.getString("aarName"))
            })
            File(outDir, "$base.log").writeText(log.toString())
            File(outDir, "$base.json").writeText(record.toString(2) + "\n")
            Log.i(TAG, "RECORD $base.json")
            // insurance for a platform that collects logcat but not the pulled files: the record
            // without the (separately logged) gate block fits one logcat line (~4 KB payload cap)
            Log.i(TAG, "RECORD_JSON " + JSONObject(record.toString()).apply { remove("quality") }.toString())
            val d = metrics.optDouble("decodeTokensPerSecond", Double.NaN)
            val ok = failure == null && !d.isNaN() && d > 0
            if (ok) { okRuns++; decodeRates.add(d) }
            Log.i(TAG, "run $i/${args.runs} ${if (ok) "OK" else "FAIL"} decode=${if (d.isNaN()) "-" else "%.2f".format(d)} tok/s " +
                "prefill=${info?.lastPrefillTokensPerSecond} ttft_ms=${info?.let { it.timeToFirstTokenInSecond * 1000 }} " +
                "gen=${info?.lastDecodeTokenCount} thermal=${thermal0.name}->${thermal1.name} firstEver=$firstEver${failure?.let { " error=$it" } ?: ""}")
        }

        val summary = "gate=${gateJson?.optString("verdict") ?: "skipped"} runs_ok=$okRuns/${args.runs} " +
            "decode_tok_s=${decodeRates.joinToString(",") { "%.2f".format(it) }} out=${outDir.absolutePath}"
        Log.i(TAG, "SUMMARY $summary")
        val g = gateJson
        if (g != null && g.optString("verdict") == "FAIL") {
            fail("correctness gate FAIL: correct ${g.optInt("passed")}/${g.optInt("total")}, form ${g.optInt("formPassed")}/${g.optInt("total")} " +
                "(${g.optString("sizeClass")}: ${g.optString("rule")}) - the model does not rank. $summary")
        }
        if (okRuns != args.runs) fail("$okRuns of ${args.runs} runs produced a decode rate. $summary")
    }

    /** Quant label from the artifact name only (quant-label-rule: a bare "int4" is not a spec). */
    private fun quantLabel(name: String): String {
        val low = name.lowercase()
        for (pat in listOf("wna8o8", "q4_0", "q8_0", "q4_k_m", "wi4b32", "int8", "int4", "q8", "q4", "fp16", "f16", "bf16", "fp32")) {
            if (Regex("(^|[-_.])${Regex.escape(pat)}([-_.]|$)").containsMatchIn(low))
                return "$pat (litert-community filename descriptor)"
        }
        return "unrecorded (artifact name carries no quant label)"
    }

    private fun powerSourceLabel(context: Context): String {
        val intent = context.registerReceiver(null, android.content.IntentFilter(android.content.Intent.ACTION_BATTERY_CHANGED))
        return when (intent?.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) ?: 0) {
            BatteryManager.BATTERY_PLUGGED_USB -> "usb"
            BatteryManager.BATTERY_PLUGGED_AC -> "ac"
            BatteryManager.BATTERY_PLUGGED_WIRELESS -> "wireless"
            0 -> "battery"
            else -> "other"
        }
    }
}
