package io.github.johnrocky.edgellmbench

import android.util.Log
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/**
 * Downloads one file from a Hugging Face repo onto the device.
 *
 * - The token (gated repos) is sent only to huggingface.co, never to the CDN host the resolve
 *   endpoint redirects to; redirects are followed by hand for that reason.
 * - The first response's X-Repo-Commit header is the revision the file was resolved at; it is
 *   returned so the record can stamp model.hfRevision with the real commit, not "main".
 * - A previous verified download (sha256 sidecar present) is reused: the sidecar is written only
 *   after the whole file was read and hashed.
 */
object HubDownload {
    private const val TAG = "EDGE_LLM_BENCH"

    data class Result(val file: File, val sha256: String, val revision: String?, val downloaded: Boolean)

    fun fetch(repo: String, filename: String, revision: String, token: String?, dest: File): Result {
        val sidecar = File(dest.path + ".sha256")
        if (dest.isFile && sidecar.isFile) {
            val recorded = sidecar.readText().trim().split(Regex("\\s+"))
            if (recorded.size >= 1 && recorded[0].length == 64 && dest.length() > 0) {
                Log.i(TAG, "reusing verified ${dest.name} (${dest.length()} bytes)")
                return Result(dest, recorded[0], recorded.getOrNull(1), downloaded = false)
            }
        }
        dest.parentFile?.mkdirs()
        val tmp = File(dest.path + ".part")
        var url = URL("https://huggingface.co/$repo/resolve/$revision/$filename")
        var repoCommit: String? = null
        var hops = 0
        while (true) {
            val conn = url.openConnection() as HttpURLConnection
            conn.instanceFollowRedirects = false
            conn.connectTimeout = 30_000
            conn.readTimeout = 120_000
            conn.setRequestProperty("User-Agent", "edge-llm-bench-ddp/0.1")
            if (!token.isNullOrBlank() && url.host == "huggingface.co") {
                conn.setRequestProperty("Authorization", "Bearer $token")
            }
            val code = conn.responseCode
            conn.getHeaderField("X-Repo-Commit")?.let { repoCommit = it }
            if (code in listOf(301, 302, 303, 307, 308)) {
                val loc = conn.getHeaderField("Location") ?: throw IllegalStateException("redirect without Location from $url")
                conn.disconnect()
                url = URL(url, loc)
                if (++hops > 8) throw IllegalStateException("too many redirects fetching $filename")
                continue
            }
            if (code != 200) {
                val body = try { conn.errorStream?.bufferedReader()?.readText()?.take(300) } catch (e: Exception) { null }
                conn.disconnect()
                throw IllegalStateException("HTTP $code fetching $url${if (body != null) ": $body" else ""}" +
                    (if (code == 401 || code == 403) " (gated repo? pass -e hf_token <token> or use model_path)" else ""))
            }
            val expected = conn.contentLengthLong
            Log.i(TAG, "downloading $filename ($expected bytes) from ${url.host}")
            val md = MessageDigest.getInstance("SHA-256")
            var total = 0L
            var lastLog = 0L
            conn.inputStream.use { input ->
                tmp.outputStream().buffered(1 shl 20).use { out ->
                    val buf = ByteArray(1 shl 18)
                    while (true) {
                        val n = input.read(buf)
                        if (n < 0) break
                        out.write(buf, 0, n)
                        md.update(buf, 0, n)
                        total += n
                        if (total - lastLog >= (64L shl 20)) { Log.i(TAG, "  $total / $expected bytes"); lastLog = total }
                    }
                }
            }
            conn.disconnect()
            if (expected > 0 && total != expected) {
                tmp.delete()
                throw IllegalStateException("short read: $total of $expected bytes for $filename")
            }
            val sha = md.digest().joinToString("") { "%02x".format(it) }
            if (!tmp.renameTo(dest)) throw IllegalStateException("cannot move ${tmp.path} to ${dest.path}")
            sidecar.writeText("$sha ${repoCommit ?: ""}\n")
            Log.i(TAG, "downloaded $filename sha256=$sha revision=$repoCommit")
            return Result(dest, sha, repoCommit, downloaded = true)
        }
    }

    fun sha256(file: File): String {
        val md = MessageDigest.getInstance("SHA-256")
        file.inputStream().buffered(1 shl 20).use { s ->
            val buf = ByteArray(1 shl 18)
            while (true) { val n = s.read(buf); if (n < 0) break; md.update(buf, 0, n) }
        }
        return md.digest().joinToString("") { "%02x".format(it) }
    }
}
