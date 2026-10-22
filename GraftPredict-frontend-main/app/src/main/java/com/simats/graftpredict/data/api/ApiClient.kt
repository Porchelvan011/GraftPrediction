package com.simats.graftpredict.data.api

import android.util.Log
import com.simats.graftpredict.data.local.SessionManager
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object ApiClient {
    private const val TAG = "ApiClient"

    /**
     * Remote backend server base URL.
     * Note: Retrofit requires baseUrl to end in '/'. The sanitization logic ensures
     * that even if a path or missing trailing slash is present, it is cleaned safely.
     */
    const val BASE_URL: String = "http://180.235.121.253:8063/"

    /**
     * Local emulator host loopback URL
     */
    const val LOCAL_EMULATOR_URL: String = "http://10.0.2.2:8063/"

    /**
     * Sanitizes any URL to ensure Retrofit receives a valid base URL ending in '/'
     * and strips any inadvertent health or endpoint path (e.g. /healthz).
     */
    fun sanitizeBaseUrl(url: String): String {
        var clean = url.trim()
        clean = clean.replace(Regex("/healthz/?$", RegexOption.IGNORE_CASE), "")
        if (!clean.endsWith("/")) {
            clean = "$clean/"
        }
        return clean
    }

    val isEmulator: Boolean
        get() = android.os.Build.FINGERPRINT.startsWith("generic")
                || android.os.Build.FINGERPRINT.startsWith("unknown")
                || android.os.Build.MODEL.contains("google_sdk")
                || android.os.Build.MODEL.contains("Emulator")
                || android.os.Build.MODEL.contains("Android SDK built for x86")
                || android.os.Build.HARDWARE.contains("goldfish")
                || android.os.Build.HARDWARE.contains("ranchu")
                || android.os.Build.PRODUCT.contains("sdk")

    fun getEffectiveBaseUrl(): String {
        return if (isEmulator) {
            LOCAL_EMULATOR_URL
        } else {
            sanitizeBaseUrl(BASE_URL)
        }
    }

    fun create(sessionManager: SessionManager): ApiService {
        val logging = HttpLoggingInterceptor { message ->
            Log.d(TAG, message)
        }.apply {
            level = HttpLoggingInterceptor.Level.BODY
        }

        val authInterceptor = Interceptor { chain ->
            val reqBuilder = chain.request().newBuilder()
            val token = sessionManager.getToken()
            if (!token.isNullOrEmpty()) {
                reqBuilder.addHeader("Authorization", "Bearer $token")
            }
            chain.proceed(reqBuilder.build())
        }

        val client = OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(logging)
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .build()

        val safeBaseUrl = getEffectiveBaseUrl()
        Log.i(TAG, "Initializing Retrofit with Base URL: $safeBaseUrl (isEmulator=$isEmulator)")

        val retrofit = Retrofit.Builder()
            .baseUrl(safeBaseUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()

        return retrofit.create(ApiService::class.java)
    }
}
