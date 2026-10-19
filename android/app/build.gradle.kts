plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "io.github.davepomerlo.tokyocinema"
    compileSdk = 34

    defaultConfig {
        applicationId = "io.github.davepomerlo.tokyocinema"
        minSdk = 26
        targetSdk = 34
        // Set by the GitHub Actions build; local builds get 1 / "1.0".
        versionCode = (System.getenv("VERSION_CODE") ?: "1").toInt()
        versionName = System.getenv("VERSION_NAME") ?: "1.0"
        buildConfigField("String", "START_URL", "\"https://davepomerlo.github.io/tokyo-cinema/?source=android\"")
        buildConfigField("String", "APP_PREFIX", "\"https://davepomerlo.github.io/tokyo-cinema/\"")
    }

    signingConfigs {
        create("release") {
            storeFile = file(System.getenv("KEYSTORE_PATH") ?: "release.p12")
            storePassword = System.getenv("KEYSTORE_PASSWORD")
            keyAlias = System.getenv("KEY_ALIAS") ?: "tokyocinema"
            keyPassword = System.getenv("KEYSTORE_PASSWORD")
            storeType = "pkcs12"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        buildConfig = true
    }
    lint {
        checkReleaseBuilds = false
        abortOnError = false
    }
}

dependencies {
    implementation("androidx.swiperefreshlayout:swiperefreshlayout:1.1.0")
}
