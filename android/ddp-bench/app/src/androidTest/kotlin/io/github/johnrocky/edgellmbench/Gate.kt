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
 * Eight trivially easy, deterministic-checkable questions (prompts/correctness-gate-8.jsonl), each
 * in a fresh conversation, greedy sampling, a short output cap. A question passes when the reply
 * matches its `accept` regex (case-insensitive). The gate is a garbage detector, not a quality
 * score: the threshold is fixed BEFORE any model is run and never tuned to a model.
 */
object Gate {
    private const val TAG = "EDGE_LLM_BENCH"
    const val THRESHOLD = 6           // of 8; a broken tokenizer / bundle scores ~0
    const val MAX_OUTPUT_TOKENS = 32
    val SAMPLER = SamplerConfig(topK = 1, topP = 1.0, temperature = 0.0)
    const val SAMPLER_LABEL = "greedy (topK=1, topP=1.0, temperature=0.0)"

    data class Question(val id: String, val prompt: String, val accept: Regex)

    fun load(jsonl: String): List<Question> = jsonl.lineSequence()
        .map { it.trim() }.filter { it.isNotEmpty() }
        .map { JSONObject(it) }
        .map { Question(it.getString("id"), it.getString("prompt"), Regex(it.getString("accept"), RegexOption.IGNORE_CASE)) }
        .toList()

    data class Outcome(val results: JSONArray, val passed: Int, val total: Int, val verdict: String, val elapsedMs: Long)

    /** Runs every question on an already-initialized engine. Never throws for a wrong answer. */
    fun run(engine: Engine, questions: List<Question>): Outcome {
        val t0 = System.nanoTime()
        val results = JSONArray()
        var passed = 0
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
            val ok = error == null && q.accept.containsMatchIn(answer)
            if (ok) passed++
            Log.i(TAG, "gate ${q.id}: ${if (ok) "PASS" else "FAIL"} answer=${answer.replace('\n', ' ').take(120)}${error?.let { " error=$it" } ?: ""}")
            results.put(JSONObject().apply {
                put("id", q.id)
                put("prompt", q.prompt)
                put("accept", q.accept.pattern)
                put("answer", answer)
                put("pass", ok)
                put("elapsedMs", (System.nanoTime() - tq) / 1_000_000)
                if (error != null) put("error", error)
            })
        }
        val verdict = if (passed >= THRESHOLD) "PASS" else "FAIL"
        return Outcome(results, passed, questions.size, verdict, (System.nanoTime() - t0) / 1_000_000)
    }

    fun toJson(o: Outcome): JSONObject = JSONObject().apply {
        put("name", "correctness-gate-8")
        put("verdict", o.verdict)
        put("passed", o.passed)
        put("total", o.total)
        put("threshold", THRESHOLD)
        put("sampler", SAMPLER_LABEL)
        put("maxOutputTokens", MAX_OUTPUT_TOKENS)
        put("elapsedMs", o.elapsedMs)
        put("questions", o.results)
    }
}
