pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositories {
        // litertlm-android is published on Google Maven (dl.google.com), not Maven Central.
        google()
        mavenCentral()
    }
}
rootProject.name = "edge-llm-bench-ddp"
include(":app")
