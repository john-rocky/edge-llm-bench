import java.security.MessageDigest

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// One engine version per build (android/engine-pins.json discipline). The value flows into
// BuildConfig and, together with the resolved AAR's sha256, into every record the test writes.
val pinnedLitertlmVersion: String = (project.findProperty("litertlmVersion") as String?) ?: "0.17.0"

// Repo-root inputs the test must use byte-identically with the native Android lane (same-budget
// rule): the short-chat prompt and its output budget. The 8-question gate lives beside this project.
val repoRoot = rootDir.parentFile.parentFile
val promptsDir = File(repoRoot, "prompts/text")

android {
    namespace = "io.github.johnrocky.edgellmbench"
    compileSdk = 35
    defaultConfig {
        applicationId = "io.github.johnrocky.edgellmbench"
        // DDP catalog rows start at API 34 (akita-34 / e1q-34); 28 keeps older local phones usable.
        minSdk = 28
        targetSdk = 35
        versionCode = 1
        versionName = "0.1"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        buildConfigField("String", "LITERTLM_VERSION", "\"$pinnedLitertlmVersion\"")
    }
    buildFeatures { buildConfig = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

// Kotlin 2.4 removed `kotlinOptions { jvmTarget }`; the compilerOptions DSL is the only form.
kotlin {
    compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) }
}

dependencies {
    implementation("com.google.ai.edge.litertlm:litertlm-android:$pinnedLitertlmVersion")
    // A public coroutines release on purpose (LiteRT-LM#3334 history): the AAR's Conversation uses
    // kotlinx channels internally even on the blocking sendMessage path.
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("junit:junit:4.13.2")
}

/**
 * Generates the test's assets at build time so there is exactly one source of truth:
 *  - engine-pin.json  : {litertlmVersion, aarName, aarSha256} of the AAR actually on the classpath
 *                       (the witness; the gradle property is the request)
 *  - short-chat.txt / budgets.tsv : copied from <repo>/prompts/text (never edited here)
 *  - correctness-gate-8.jsonl     : the 8-question gate beside this project
 */
abstract class GenerateBenchAssets : DefaultTask() {
    @get:InputFiles abstract val runtimeClasspath: ConfigurableFileCollection
    @get:Input abstract val litertlmVersion: Property<String>
    @get:InputFile abstract val promptFile: RegularFileProperty
    @get:InputFile abstract val budgetsFile: RegularFileProperty
    @get:InputFile abstract val gateFile: RegularFileProperty
    @get:OutputDirectory abstract val outDir: DirectoryProperty

    @TaskAction
    fun run() {
        val out = outDir.get().asFile
        out.mkdirs()
        val version = litertlmVersion.get()
        val aar = runtimeClasspath.files.firstOrNull {
            it.name == "litertlm-android-$version.aar"
        } ?: throw GradleException(
            "litertlm-android-$version.aar not on the runtime classpath: " +
                runtimeClasspath.files.map { it.name }.filter { it.contains("litertlm") })
        val md = MessageDigest.getInstance("SHA-256")
        aar.inputStream().use { s ->
            val buf = ByteArray(1 shl 20)
            while (true) { val n = s.read(buf); if (n < 0) break; md.update(buf, 0, n) }
        }
        val sha = md.digest().joinToString("") { "%02x".format(it) }
        File(out, "engine-pin.json").writeText(
            """{"litertlmVersion": "$version", "aarName": "${aar.name}", "aarSha256": "$sha"}""" + "\n")
        promptFile.get().asFile.copyTo(File(out, "short-chat.txt"), overwrite = true)
        budgetsFile.get().asFile.copyTo(File(out, "budgets.tsv"), overwrite = true)
        gateFile.get().asFile.copyTo(File(out, "correctness-gate-8.jsonl"), overwrite = true)
    }
}

androidComponents {
    onVariants { variant ->
        val test = variant.androidTest ?: return@onVariants
        val task = tasks.register<GenerateBenchAssets>("generate${variant.name.replaceFirstChar { it.uppercase() }}BenchAssets") {
            // The AAR the test process will actually load: the tested app's runtime classpath.
            runtimeClasspath.from(configurations.named("${variant.name}RuntimeClasspath"))
            litertlmVersion.set(pinnedLitertlmVersion)
            promptFile.set(File(promptsDir, "short-chat.txt"))
            budgetsFile.set(File(promptsDir, "budgets.tsv"))
            gateFile.set(File(rootDir, "prompts/correctness-gate-8.jsonl"))
        }
        test.sources.assets?.addGeneratedSourceDirectory(task, GenerateBenchAssets::outDir)
    }
}
