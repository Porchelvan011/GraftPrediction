package com.simats.graftpredict.data.api

import com.simats.graftpredict.data.local.SessionManager
import okhttp3.ConnectionPool
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Response
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.io.IOException
import java.util.concurrent.TimeUnit

object ApiClient {
    private val isEmulator: Boolean
        get() = android.os.Build.FINGERPRINT.startsWith("generic")
                || android.os.Build.FINGERPRINT.startsWith("unknown")
                || android.os.Build.MODEL.contains("google_sdk")
                || android.os.Build.MODEL.contains("Emulator")
                || android.os.Build.MODEL.contains("Android SDK built for x86")
                || android.os.Build.HARDWARE.contains("goldfish")
                || android.os.Build.HARDWARE.contains("ranchu")
                || android.os.Build.PRODUCT.contains("sdk")

    // 10.0.2.2 points to host PC from Android Emulator; 127.0.0.1 works on physical device with adb reverse
    val BASE_URL: String
        get() = if (isEmulator) "http://180.235.121.253:8063/" else "http://180.235.121.253:8063/"

    fun create(sessionManager: SessionManager): ApiService {
        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        }

        val authInterceptor = Interceptor { chain ->
            val reqBuilder = chain.request().newBuilder()
            val token = sessionManager.getToken()
            if (!token.isNullOrEmpty()) {
                reqBuilder.addHeader("Authorization", "Bearer $token")
            }
            reqBuilder.header("Connection", "close")
            chain.proceed(reqBuilder.build())
        }

        val retryInterceptor = Interceptor { chain ->
            val request = chain.request()
            var response: Response? = null
            var lastException: IOException? = null
            var tryCount = 0
            val maxLimit = 3

            while (tryCount < maxLimit) {
                try {
                    tryCount++
                    response = chain.proceed(request)
                    if (response.isSuccessful || response.code in 400..499) {
                        return@Interceptor response
                    }
                    if (tryCount < maxLimit && (response.code in 502..504)) {
                        response.close()
                        Thread.sleep(300)
                        continue
                    }
                    return@Interceptor response
                } catch (e: IOException) {
                    lastException = e
                    if (tryCount >= maxLimit) {
                        throw e
                    }
                    try {
                        Thread.sleep(300)
                    } catch (_: InterruptedException) {
                        Thread.currentThread().interrupt()
                        throw e
                    }
                }
            }
            response ?: throw (lastException ?: IOException("Request failed after $maxLimit attempts"))
        }

        val client = OkHttpClient.Builder()
            .retryOnConnectionFailure(true)
            .addInterceptor(authInterceptor)
            .addInterceptor(retryInterceptor)
            .addInterceptor(logging)
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .connectionPool(ConnectionPool(0, 1, TimeUnit.NANOSECONDS))
            .build()

        val retrofit = Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()

        return retrofit.create(ApiService::class.java)
    }
}
