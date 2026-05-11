plugins {
    id("java")
    id("org.jetbrains.kotlin.jvm") version "1.9.22"
    id("org.jetbrains.intellij") version "1.17.3"
}

group = "com.anthropic"
version = "3.0.0"

repositories {
    mavenCentral()
}

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.8.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")
}

intellij {
    version.set("2024.1")
    type.set("IC")
    plugins.set(listOf("JavaScript"))
}

kotlin {
    jvmToolchain(17)
}

tasks {
    patchPluginXml {
        sinceBuild.set("241")
        untilBuild.set("251.*")
    }
    signPlugin {
        certificateChain.set(System.getenv("JETBRAINS_CERTIFICATE_CHAIN"))
        privateKey.set(System.getenv("JETBRAINS_PRIVATE_KEY"))
        password.set(System.getenv("JETBRAINS_PRIVATE_KEY_PASSWORD"))
    }
    publishPlugin {
        token.set(System.getenv("JETBRAINS_MARKETPLACE_TOKEN"))
    }
}
