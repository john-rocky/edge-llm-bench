plugins {
    id("com.android.application") version "8.7.3" apply false
    // The consumer Kotlin floor follows the AAR's Kotlin metadata version: litertlm-android 0.17.0
    // ships metadata 2.4.0, which a 2.2.x/2.3.x Kotlin compiler refuses ("can read versions up to
    // 2.3.0"; measured in the sibling litertlm-release-gate harness, 2026-09-06).
    id("org.jetbrains.kotlin.android") version "2.4.0" apply false
}
