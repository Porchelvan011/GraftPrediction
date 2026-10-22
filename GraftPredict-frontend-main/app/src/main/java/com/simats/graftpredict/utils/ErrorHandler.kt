package com.simats.graftpredict.utils

import retrofit2.HttpException
import org.json.JSONObject

/**
 * Sanitizes error messages to hide sensitive information like IP addresses and ports
 * while presenting accurate, helpful feedback to users.
 */
object ErrorHandler {
    /**
     * Sanitizes exception messages to remove sensitive backend information
     * @param exception The exception to sanitize
     * @param defaultMessage The default message to show if unable to sanitize
     * @return A user-friendly error message
     */
    fun sanitizeError(exception: Exception?, defaultMessage: String): String {
        if (exception == null) return defaultMessage

        if (exception is HttpException) {
            val code = exception.code()
            val errorBody = try {
                exception.response()?.errorBody()?.string()
            } catch (e: Exception) {
                null
            }

            val jsonMsg = if (!errorBody.isNullOrEmpty() && errorBody.trim().startsWith("{")) {
                try {
                    val msg = JSONObject(errorBody).optString("error", "")
                    if (msg.isNotEmpty()) msg else null
                } catch (e: Exception) {
                    null
                }
            } else null

            return when {
                !jsonMsg.isNullOrEmpty() -> jsonMsg
                code == 401 -> "Invalid email or password"
                code == 403 -> "Access denied"
                code == 404 -> "Service endpoint not found (404)"
                code == 429 -> "Too many attempts. Please wait a moment."
                code in 500..599 -> "Server Error ($code): Database or service is offline on server."
                else -> "$defaultMessage (HTTP $code)"
            }
        }

        val message = exception.message ?: return defaultMessage
        
        // Check if this is a network error containing IP/port information
        if (isNetworkError(message)) {
            return "Unable to connect to the server. Please check your internet connection and try again."
        }

        // For other exceptions, return the default message
        return defaultMessage
    }

    /**
     * Checks if an error message contains sensitive network information
     */
    private fun isNetworkError(message: String): Boolean {
        // Check for common patterns in connection errors
        return message.contains(Regex("""\d+\.\d+\.\d+\.\d+""")) || // IP address
                message.contains(Regex(""":\d{4,5}""")) || // Port number
                message.contains("Failed to connect", ignoreCase = true) ||
                message.contains("Connection refused", ignoreCase = true) ||
                message.contains("Connection timeout", ignoreCase = true) ||
                message.contains("Unknown host", ignoreCase = true) ||
                message.contains("Network unreachable", ignoreCase = true)
    }
}
