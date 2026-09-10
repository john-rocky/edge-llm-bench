package io.github.johnrocky.edgellmbench

import android.util.Log
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.SamplerConfig
import org.json.JSONArray
import org.json.JSONObject

/**
 * The 8-question correctness gate: a model that emits garbage at 40 tok/s must FAIL, not rank.
 *
 * Eight trivially easy questions (prompts/correctness-gate-8.jsonl), each in a fresh conversation,
 * greedy sampling, a short output cap. Every answer is scored twice: FORM (non-empty, no leaked
 * control tokens, not a token loop — what a broken tokenizer / template / quantization produces)
 * and CORRECTNESS (the `accept` regex). The bar depends on the model's size class, because a
 * 270M-class model legitimately misses arithmetic and facts that a billion-class model does not
 * (owner decision 2026-09-10, after gemma-3-270m-it q8 scored 5/8 with the same answers as the
 * reference CLI):
 *
 *  - sub-1B  : form must pass on every question AND at least 3/8 correct (a coherence bar)
 *  - 1B and up, or size unknown : at least 6/8 correct (the original bar; form is recorded)
 */
object Gate {
    private const val TAG = "EDGE_LLM_BENCH"
    const val MAX_OUTPUT_TOKENS = 32
    val SAMPLER = SamplerConfig(topK = 1, topP = 1.0, temperature = 0.0)
    const val SAMPLER_LABEL = "greedy (topK=1, topP=1.0, temperature=0.0)"

    enum class SizeClass(val label: String, val correctThreshold: Int, val formRequired: Boolean) {
        SUB_BILLION("sub-1B", 3, true),
        BILLION_PLUS("1B+", 6, false),
    }

    /** Parameter count from names like "gemma3-270m-it-q8", "Qwen3-0.6B", "gemma-4-E2B-it", "1.5B". */
    fun parseParams(vararg names: String?): Long? {
        val rx = Regex("(\\d+(?:\\.\\d+)?)([bBmM])(?![0-9A-Za-z])")
        for (n in names) {
            val m = rx.find(n ?: continue) ?: continue
            val v = m.groupValues[1].toDouble()
            return if (m.groupValues[2].lowercase() == "b") (v * 1e9).toLong() else (v * 1e6).toLong()
        }
        return null
    }

    fun sizeClassOf(params: Long?): SizeClass =
        if (params != null && params < 1_000_000_000L) SizeClass.SUB_BILLION else SizeClass.BILLION_PLUS

    data class Question(val id: String, val prompt: String, val accept: Regex)

    fun load(jsonl: String): List<Question> = jsonl.lineSequence()
        .map { it.trim() }.filter { it.isNotEmpty() }
        .map { JSONObject(it) }
        .map { Question(it.getString("id"), it.getString("prompt"), Regex(it.getString("accept"), RegexOption.IGNORE_CASE)) }
        .toList()

    private val CONTROL_TOKENS = listOf("<start_of_turn>", "<end_of_turn>", "<bos>", "<eos>", "<pad>", "<|", "|>", "<unk>")

    /** Form check: what garbage looks like, independent of the question. Returns null when fine. */
    fun formProblem(answer: String): String? {
        val a = answer.trim()
        if (a.isEmpty()) return "empty"
        CONTROL_TOKENS.firstOrNull { a.contains(it) }?.let { return "control token leaked: $it" }
        if (!a.any { it.isLetterOrDigit() }) return "no letter or digit"
        if (Regex("(\\S+)(\\s+\\1){2,}").containsMatchIn(a)) return "token repeated 3+ times in a row"
        val words = a.split(Regex("\\s+")).filter { it.isNotEmpty() }
        if (words.size >= 6 && words.toSet().size.toDouble() / words.size < 0.4) return "repetition loop (unique words < 40%)"
        return null
    }

    data class Outcome(val results: JSONArray, val correct: Int, val formPassed: Int, val total: Int,
                       val sizeClass: SizeClass, val params: Long?, val verdict: String, val elapsedMs: Long)

    /** Runs every question on an already-initialized engine. Never throws for a wrong answer. */
    fun run(engine: Engine, questions: List<Question>, sizeClass: SizeClass, params: Long?): Outcome {
        val t0 = System.nanoTime()
        val results = JSONArray()
        var correct = 0
        var formPassed = 0
        for (q in questions) {
            val cfg = ConversationConfig(samplerConfig = SAMPLER, maxOutputToken = MAX_OUTPUT_TOKENS)
            var answer = ""
            var error: String? = null
            val tq = System.nanoTime()
            try {
                engine.createConversation(cfg).use { conv ->
                    answer = conv.sendMessage(q.prompt).toString()
                }
            } catch (e: Throwable) {
                error = "${e.javaClass.simpleName}: ${e.message}"
            }
            val form = if (error != null) "error: $error" else formProblem(answer)
            val ok = error == null && q.accept.containsMatchIn(answer)
            if (ok) correct++
            if (form == null) formPassed++
            Log.i(TAG, "gate ${q.id}: ${if (ok) "correct" else "wrong"} form=${form ?: "ok"} answer=${answer.replace('\n', ' ').take(120)}")
            results.put(JSONObject().apply {
                put("id", q.id)
                put("prompt", q.prompt)
                put("accept", q.accept.pattern)
                put("answer", answer)
                put("pass", ok)
                put("formOk", form == null)
                if (form != null) put("formProblem", form)
                put("elapsedMs", (System.nanoTime() - tq) / 1_000_000)
                if (error != null) put("error", error)
            })
        }
        val formOk = !sizeClass.formRequired || formPassed == questions.size
        val verdict = if (formOk && correct >= sizeClass.correctThreshold) "PASS" else "FAIL"
        return Outcome(results, correct, formPassed, questions.size, sizeClass, params, verdict, (System.nanoTime() - t0) / 1_000_000)
    }

    fun toJson(o: Outcome): JSONObject = JSONObject().apply {
        put("name", "correctness-gate-8")
        put("verdict", o.verdict)
        put("passed", o.correct)
        put("total", o.total)
        put("formPassed", o.formPassed)
        put("sizeClass", o.sizeClass.label)
        put("modelParams", o.params ?: JSONObject.NULL)
        put("threshold", o.sizeClass.correctThreshold)
        put("formRequired", o.sizeClass.formRequired)
        put("rule", if (o.sizeClass.formRequired) "form ok on every question AND correct >= ${o.sizeClass.correctThreshold}/${o.total}"
                    else "correct >= ${o.sizeClass.correctThreshold}/${o.total}")
        put("sampler", SAMPLER_LABEL)
        put("maxOutputTokens", MAX_OUTPUT_TOKENS)
        put("elapsedMs", o.elapsedMs)
        put("questions", o.results)
    }
}
