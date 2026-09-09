package io.github.johnrocky.edgellmbench

import android.os.Bundle

/**
 * Instrumentation arguments (`adb shell am instrument -e key value ...`; on DDP
 * `--additional-test-options=key=value`). Every value is a string.
 */
class BenchArgs(private val b: Bundle) {
    private fun s(key: String, default: String? = null): String? = b.getString(key)?.trim()?.takeIf { it.isNotEmpty() } ?: default

    /** Hugging Face repo id of the model (any `.litertlm` publisher; litert-community by default). */
    val hfRepo: String = s("hf_repo", "litert-community/gemma-3-270m-it")!!
    /** Filename inside the repo. The gemma-3-270m q8 file is the smallest official ship (JIT, no AOT partition). */
    val hfFile: String = s("hf_file", "gemma3-270m-it-q8.litertlm")!!
    /** Revision to resolve; the record stamps the commit the Hub actually served. */
    val hfRevision: String = s("hf_revision", "main")!!
    /** Token for gated repos. Sent to huggingface.co only. Never baked into the APK. */
    val hfToken: String? = s("hf_token")
    /** Skip the download and use a file already on the device (adb push / --other-files-to-push). */
    val modelPath: String? = s("model_path")
    /** cpu | gpu — part of the arm identity (runtime = litert-lm-<backend>). */
    val backend: String = s("backend", "cpu")!!.lowercase()
    /** short-chat (the repo's Task A) or native-benchmark-<P>x<D> (synthetic, the Kotlin benchmark()). */
    val task: String = s("task", "short-chat")!!
    /** Measurement runs; each is a fresh Engine. */
    val runs: Int = s("runs", "3")!!.toInt()
    /** Seconds between runs 2..N (the native campaign runner uses >= 120). */
    val cooldownSeconds: Int = s("cooldown_s", "60")!!.toInt()
    /** Override the task's output budget (prompts/text/budgets.tsv). */
    val maxOutputTokens: Int? = s("max_output_tokens")?.toInt()
    /** Run the 8-question gate (default true). "false" is for pure speed probes. */
    val gate: Boolean = s("gate", "true")!!.toBoolean()
    /** Label written into provenance.campaign and the output subdirectory. */
    val campaign: String = s("campaign", "ddp-apk")!!
    /** Context size override (EngineConfig.maxNumTokens); default = bundle default. */
    val contextTokens: Int? = s("context_tokens")?.toInt()

    fun asMap(): Map<String, Any?> = linkedMapOf(
        "hf_repo" to hfRepo, "hf_file" to hfFile, "hf_revision" to hfRevision,
        "hf_token" to (if (hfToken != null) "<set>" else null), "model_path" to modelPath,
        "backend" to backend, "task" to task, "runs" to runs, "cooldown_s" to cooldownSeconds,
        "max_output_tokens" to maxOutputTokens, "gate" to gate, "campaign" to campaign,
        "context_tokens" to contextTokens,
    )
}
