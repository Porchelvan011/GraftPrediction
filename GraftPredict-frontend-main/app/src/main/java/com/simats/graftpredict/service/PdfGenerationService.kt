package com.simats.graftpredict.service

import android.content.Context
import android.graphics.*
import android.graphics.pdf.PdfDocument
import android.os.Environment
import com.simats.graftpredict.data.models.ReportData
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.*

/**
 * High-performance, memory-safe native PDF generation service for GraftPredict reports.
 * Uses Android's native PdfDocument API to create crisp, vector-grade A4 clinical reports
 * without relying on external CDNs or blocking WebView print spoolers.
 */
class PdfGenerationService(private val context: Context) {

    interface PdfGenerationCallback {
        fun onPdfGenerated(file: File)
        fun onPdfGenerationFailed(error: String)
    }

    suspend fun generatePdfReportAsync(
        reportData: ReportData,
        fileName: String = "GraftReport_${System.currentTimeMillis()}.pdf"
    ): Result<File> = withContext(Dispatchers.IO) {
        try {
            // Target output directory (Documents in external files dir, fallback to filesDir)
            val baseDir = context.getExternalFilesDir(Environment.DIRECTORY_DOCUMENTS)
                ?: File(context.filesDir, "Documents")
            if (!baseDir.exists()) {
                baseDir.mkdirs()
            }

            val outputFile = File(baseDir, fileName)
            if (outputFile.exists()) {
                outputFile.delete()
            }

            // Create A4 PDF Document (595 x 842 points at 72 DPI)
            val document = PdfDocument()
            val pageInfo = PdfDocument.PageInfo.Builder(595, 842, 1).create()
            val page = document.startPage(pageInfo)
            val canvas = page.canvas

            renderReportToCanvas(canvas, reportData)

            document.finishPage(page)

            // Write to destination file
            FileOutputStream(outputFile).use { fos ->
                document.writeTo(fos)
                fos.flush()
            }
            document.close()

            if (outputFile.exists() && outputFile.length() > 0) {
                Result.success(outputFile)
            } else {
                Result.failure(Exception("PDF file was created but has 0 bytes"))
            }
        } catch (e: Exception) {
            e.printStackTrace()
            Result.failure(Exception("Failed to generate PDF: ${e.message}"))
        }
    }

    private fun renderReportToCanvas(canvas: Canvas, reportData: ReportData) {
        val dateFormat = SimpleDateFormat("MMM dd, yyyy", Locale.getDefault())
        val currentDate = dateFormat.format(Date())

        // Colors
        val primaryBlue = Color.rgb(19, 127, 236)
        val primaryDark = Color.rgb(15, 23, 42)
        val textSecondary = Color.rgb(100, 116, 139)
        val cardBg = Color.rgb(248, 250, 252)
        val cardBorder = Color.rgb(226, 232, 240)
        val successGreen = Color.rgb(16, 185, 129)
        val warningAmber = Color.rgb(245, 158, 11)
        val infoBlueBg = Color.rgb(239, 246, 255)
        val infoBlueBorder = Color.rgb(191, 219, 254)
        val infoBlueText = Color.rgb(30, 64, 175)

        // Paints
        val fillPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.FILL }
        val strokePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.STROKE
            strokeWidth = 1f
        }
        val textPaint = Paint(Paint.ANTI_ALIAS_FLAG)

        // 1. Top Decorative Header Stripe
        fillPaint.color = primaryBlue
        canvas.drawRect(0f, 0f, 595f, 8f, fillPaint)

        // 2. Main Header
        val left = 36f
        val right = 559f
        var currentY = 42f

        // App Logo Badge
        fillPaint.color = primaryBlue
        val logoRect = RectF(left, currentY, left + 34f, currentY + 34f)
        canvas.drawRoundRect(logoRect, 8f, 8f, fillPaint)

        textPaint.color = Color.WHITE
        textPaint.textSize = 15f
        textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        textPaint.textAlign = Paint.Align.CENTER
        canvas.drawText("GP", left + 17f, currentY + 23f, textPaint)

        // Title and Subtitle
        textPaint.color = primaryDark
        textPaint.textSize = 20f
        textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        textPaint.textAlign = Paint.Align.LEFT
        canvas.drawText("GraftPredict", left + 44f, currentY + 18f, textPaint)

        textPaint.color = primaryBlue
        textPaint.textSize = 8.5f
        textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        canvas.drawText("ACL GRAFT SIZE PREDICTION & CLINICAL REPORT", left + 44f, currentY + 30f, textPaint)

        // Right Header Metadata
        textPaint.color = textSecondary
        textPaint.textSize = 8.5f
        textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.NORMAL)
        textPaint.textAlign = Paint.Align.RIGHT
        canvas.drawText("Report ID: GP-${reportData.report_id}", right, currentY + 16f, textPaint)
        canvas.drawText("Generated: $currentDate", right, currentY + 28f, textPaint)

        // Divider
        currentY += 46f
        strokePaint.color = cardBorder
        strokePaint.strokeWidth = 1f
        canvas.drawLine(left, currentY, right, currentY, strokePaint)

        // 3. Patient Information Card
        currentY += 12f
        val patientCardHeight = 90f
        val patientCardRect = RectF(left, currentY, right, currentY + patientCardHeight)

        fillPaint.color = cardBg
        canvas.drawRoundRect(patientCardRect, 8f, 8f, fillPaint)
        strokePaint.color = cardBorder
        canvas.drawRoundRect(patientCardRect, 8f, 8f, strokePaint)

        // Section Title
        textPaint.color = primaryBlue
        textPaint.textSize = 9f
        textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        textPaint.textAlign = Paint.Align.LEFT
        canvas.drawText("PATIENT INFORMATION", left + 14f, currentY + 18f, textPaint)

        // Row 1: Name, Age, Gender, Affected Side
        val colWidth = (right - left - 28f) / 4f
        val row1Y = currentY + 40f
        drawMetaItem(canvas, left + 14f, row1Y, "PATIENT NAME", reportData.name, textPaint)
        drawMetaItem(canvas, left + 14f + colWidth, row1Y, "AGE", "${reportData.age} yrs", textPaint)
        drawMetaItem(canvas, left + 14f + colWidth * 2, row1Y, "GENDER", reportData.gender, textPaint)
        drawMetaItem(canvas, left + 14f + colWidth * 3, row1Y, "AFFECTED SIDE", reportData.affected_side, textPaint)

        // Row 2: Height, Weight, BMI, Injury Date
        val row2Y = currentY + 70f
        drawMetaItem(canvas, left + 14f, row2Y, "HEIGHT", "${reportData.height} cm", textPaint)
        drawMetaItem(canvas, left + 14f + colWidth, row2Y, "WEIGHT", "${reportData.weight} kg", textPaint)
        drawMetaItem(canvas, left + 14f + colWidth * 2, row2Y, "BMI", "${String.format(Locale.US, "%.1f", safeToDouble(reportData.bmi))} kg/m²", textPaint)
        drawMetaItem(canvas, left + 14f + colWidth * 3, row2Y, "INJURY DATE", reportData.affected_date ?: "N/A", textPaint)

        // 4. Primary Predicted Measurements Section
        currentY += patientCardHeight + 16f
        textPaint.color = primaryDark
        textPaint.textSize = 12f
        textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        canvas.drawText("Predicted Graft Diameters", left, currentY, textPaint)

        textPaint.color = textSecondary
        textPaint.textSize = 8.5f
        textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.NORMAL)
        canvas.drawText("Exact clinical formulas derived from anthropometric and MRI measurements", left, currentY + 12f, textPaint)

        currentY += 20f
        val cardSpacing = 10f
        val predBoxWidth = (right - left - (cardSpacing * 3)) / 4f
        val predBoxHeight = 85f

        val graftD1 = safeToDouble(reportData.graft_diameter_1)
        val graftD2 = safeToDouble(reportData.graft_diameter_2)
        val hamstring = safeToDouble(reportData.hamstring_autograft)
        val quad = safeToDouble(reportData.quadriceps_tendon_diameter)

        drawPredictionBox(canvas, left, currentY, predBoxWidth, predBoxHeight, "Graft Diameter 1", "MRI-based Model", graftD1, graftD1 >= 8.0, textPaint, fillPaint, strokePaint)
        drawPredictionBox(canvas, left + (predBoxWidth + cardSpacing), currentY, predBoxWidth, predBoxHeight, "Graft Diameter 2", "Anthropometric", graftD2, graftD2 >= 8.0, textPaint, fillPaint, strokePaint)
        drawPredictionBox(canvas, left + (predBoxWidth + cardSpacing) * 2, currentY, predBoxWidth, predBoxHeight, "Hamstring Graft", "4-Strand ST-G", hamstring, hamstring >= 8.0, textPaint, fillPaint, strokePaint)
        drawPredictionBox(canvas, left + (predBoxWidth + cardSpacing) * 3, currentY, predBoxWidth, predBoxHeight, "Quad Tendon", "Estimated Diameter", quad, quad >= 8.0, textPaint, fillPaint, strokePaint)

        // 5. Anatomical Tendon Lengths & Limb Metrics
        currentY += predBoxHeight + 16f
        textPaint.color = primaryDark
        textPaint.textSize = 12f
        textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        canvas.drawText("Anatomical Tendon Lengths & Limb Metrics", left, currentY, textPaint)

        currentY += 14f
        val secCardWidth = (right - left - (cardSpacing * 2)) / 3f
        val secCardHeight = 52f

        val minST = safeToDouble(reportData.minimum_st_length)
        val predST = safeToDouble(reportData.predicted_st_value)
        val gracilis = safeToDouble(reportData.gracilis_length)

        drawSecondaryBox(canvas, left, currentY, secCardWidth, secCardHeight, "MINIMUM ST LENGTH", "${String.format(Locale.US, "%.1f", minST)} mm", textPaint, fillPaint, strokePaint)
        drawSecondaryBox(canvas, left + secCardWidth + cardSpacing, currentY, secCardWidth, secCardHeight, "PREDICTED ST VALUE", "${String.format(Locale.US, "%.1f", predST)} mm", textPaint, fillPaint, strokePaint)
        drawSecondaryBox(canvas, left + (secCardWidth + cardSpacing) * 2, currentY, secCardWidth, secCardHeight, "GRACILIS LENGTH", "${String.format(Locale.US, "%.1f", gracilis)} mm", textPaint, fillPaint, strokePaint)

        // 6. Visual Comparison Bar Chart
        currentY += secCardHeight + 18f
        textPaint.color = primaryDark
        textPaint.textSize = 12f
        textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        canvas.drawText("Graft Sizing Visual Comparison", left, currentY, textPaint)

        currentY += 12f
        val chartHeight = 120f
        val chartRect = RectF(left, currentY, right, currentY + chartHeight)
        fillPaint.color = cardBg
        canvas.drawRoundRect(chartRect, 8f, 8f, fillPaint)
        strokePaint.color = cardBorder
        canvas.drawRoundRect(chartRect, 8f, 8f, strokePaint)

        // Draw 4 bars inside chart
        val barNames = listOf("Graft Diameter 1", "Graft Diameter 2", "Hamstring Autograft", "Quadriceps Tendon")
        val barValues = listOf(graftD1, graftD2, hamstring, quad)
        val barColors = listOf(primaryBlue, primaryBlue, Color.rgb(59, 130, 246), Color.rgb(99, 102, 241))

        val chartInnerLeft = left + 130f
        val chartInnerRight = right - 60f
        val chartInnerWidth = chartInnerRight - chartInnerLeft
        val minScale = 5.0
        val maxScale = 12.0

        // Vertical Guide line for 8.0mm threshold
        val thresholdX = chartInnerLeft + ((8.0 - minScale) / (maxScale - minScale) * chartInnerWidth).toFloat()
        strokePaint.color = successGreen
        strokePaint.strokeWidth = 1.5f
        strokePaint.pathEffect = DashPathEffect(floatArrayOf(4f, 4f), 0f)
        canvas.drawLine(thresholdX, currentY + 10f, thresholdX, currentY + chartHeight - 12f, strokePaint)
        strokePaint.pathEffect = null

        textPaint.color = successGreen
        textPaint.textSize = 7.5f
        textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        textPaint.textAlign = Paint.Align.CENTER
        canvas.drawText("≥ 8.0 mm (Clinical Standard)", thresholdX, currentY + chartHeight - 4f, textPaint)

        for (i in barNames.indices) {
            val barY = currentY + 16f + (i * 22f)
            val valDouble = barValues[i]

            // Label
            textPaint.color = primaryDark
            textPaint.textSize = 8.5f
            textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.NORMAL)
            textPaint.textAlign = Paint.Align.LEFT
            canvas.drawText(barNames[i], left + 14f, barY + 9f, textPaint)

            // Bar background track
            fillPaint.color = Color.rgb(235, 240, 245)
            val trackRect = RectF(chartInnerLeft, barY, chartInnerRight, barY + 12f)
            canvas.drawRoundRect(trackRect, 4f, 4f, fillPaint)

            // Active bar fill
            val clampedVal = valDouble.coerceIn(minScale, maxScale)
            val barWidth = ((clampedVal - minScale) / (maxScale - minScale) * chartInnerWidth).toFloat()
            fillPaint.color = if (valDouble >= 8.0) successGreen else warningAmber
            val barRect = RectF(chartInnerLeft, barY, chartInnerLeft + barWidth, barY + 12f)
            canvas.drawRoundRect(barRect, 4f, 4f, fillPaint)

            // Value text
            textPaint.color = primaryDark
            textPaint.textSize = 8.5f
            textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
            textPaint.textAlign = Paint.Align.LEFT
            canvas.drawText("${String.format(Locale.US, "%.1f", valDouble)} mm", chartInnerRight + 8f, barY + 9.5f, textPaint)
        }

        // 7. Clinical Interpretation Box
        currentY += chartHeight + 16f
        val infoBoxHeight = 58f
        val infoBoxRect = RectF(left, currentY, right, currentY + infoBoxHeight)
        fillPaint.color = infoBlueBg
        canvas.drawRoundRect(infoBoxRect, 8f, 8f, fillPaint)
        strokePaint.color = infoBlueBorder
        canvas.drawRoundRect(infoBoxRect, 8f, 8f, strokePaint)

        textPaint.color = infoBlueText
        textPaint.textSize = 8.5f
        textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        textPaint.textAlign = Paint.Align.LEFT
        canvas.drawText("CLINICAL RECOMMENDATION", left + 12f, currentY + 16f, textPaint)

        textPaint.color = Color.rgb(30, 58, 138)
        textPaint.textSize = 8f
        textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.NORMAL)
        canvas.drawText("• Autograft diameter ≥ 8.0 mm is clinically recommended to minimize ACL reconstruction failure risk (Magnussen et al.).", left + 12f, currentY + 30f, textPaint)
        canvas.drawText("• If predicted hamstring graft is < 8.0 mm, consider 5-strand preparation, hybrid augmentation, or quadriceps autograft.", left + 12f, currentY + 44f, textPaint)

        // 8. Footer & Signature Line
        currentY = 760f
        strokePaint.color = cardBorder
        strokePaint.strokeWidth = 1f
        canvas.drawLine(left, currentY, right, currentY, strokePaint)

        currentY += 16f
        textPaint.color = textSecondary
        textPaint.textSize = 7.5f
        textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.NORMAL)
        textPaint.textAlign = Paint.Align.LEFT
        canvas.drawText("Confidential Medical Document • Generated by GraftPredict AI Clinical Sizing System", left, currentY, textPaint)
        canvas.drawText("For surgical planning and clinical decision support. Final sizing verified intraoperatively.", left, currentY + 12f, textPaint)

        // Signature on right
        strokePaint.color = Color.rgb(150, 160, 175)
        canvas.drawLine(right - 140f, currentY, right, currentY, strokePaint)
        textPaint.textAlign = Paint.Align.CENTER
        canvas.drawText("Orthopedic Surgeon Signature", right - 70f, currentY + 12f, textPaint)
    }

    private fun drawMetaItem(canvas: Canvas, x: Float, y: Float, label: String, value: String, textPaint: Paint) {
        textPaint.color = Color.rgb(100, 116, 139)
        textPaint.textSize = 7.5f
        textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        textPaint.textAlign = Paint.Align.LEFT
        canvas.drawText(label, x, y, textPaint)

        textPaint.color = Color.rgb(15, 23, 42)
        textPaint.textSize = 9.5f
        textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        canvas.drawText(value.ifBlank { "N/A" }, x, y + 14f, textPaint)
    }

    private fun drawPredictionBox(
        canvas: Canvas,
        x: Float,
        y: Float,
        width: Float,
        height: Float,
        title: String,
        subtitle: String,
        value: Double,
        isOptimal: Boolean,
        textPaint: Paint,
        fillPaint: Paint,
        strokePaint: Paint
    ) {
        val rect = RectF(x, y, x + width, y + height)
        fillPaint.color = Color.rgb(248, 250, 252)
        canvas.drawRoundRect(rect, 8f, 8f, fillPaint)
        strokePaint.color = Color.rgb(226, 232, 240)
        canvas.drawRoundRect(rect, 8f, 8f, strokePaint)

        textPaint.color = Color.rgb(100, 116, 139)
        textPaint.textSize = 8.5f
        textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        textPaint.textAlign = Paint.Align.LEFT
        canvas.drawText(title, x + 10f, y + 16f, textPaint)

        textPaint.color = Color.rgb(148, 163, 184)
        textPaint.textSize = 7f
        textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.NORMAL)
        canvas.drawText(subtitle, x + 10f, y + 26f, textPaint)

        // Large Value
        textPaint.color = Color.rgb(19, 127, 236)
        textPaint.textSize = 19f
        textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        val valueStr = String.format(Locale.US, "%.1f", value)
        canvas.drawText(valueStr, x + 10f, y + 54f, textPaint)

        val valWidth = textPaint.measureText(valueStr)
        textPaint.color = Color.rgb(100, 116, 139)
        textPaint.textSize = 9f
        textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.NORMAL)
        canvas.drawText("mm", x + 12f + valWidth, y + 54f, textPaint)

        // Status Tag
        val tagY = y + 64f
        val tagRect = RectF(x + 10f, tagY, x + width - 10f, tagY + 14f)
        fillPaint.color = if (isOptimal) Color.rgb(236, 253, 245) else Color.rgb(254, 243, 199)
        canvas.drawRoundRect(tagRect, 4f, 4f, fillPaint)

        textPaint.color = if (isOptimal) Color.rgb(5, 150, 105) else Color.rgb(217, 119, 6)
        textPaint.textSize = 7f
        textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        textPaint.textAlign = Paint.Align.CENTER
        canvas.drawText(if (isOptimal) "≥ 8.0 mm (Optimal)" else "< 8.0 mm (Caution)", tagRect.centerX(), tagY + 10f, textPaint)
    }

    private fun drawSecondaryBox(
        canvas: Canvas,
        x: Float,
        y: Float,
        width: Float,
        height: Float,
        title: String,
        value: String,
        textPaint: Paint,
        fillPaint: Paint,
        strokePaint: Paint
    ) {
        val rect = RectF(x, y, x + width, y + height)
        fillPaint.color = Color.rgb(248, 250, 252)
        canvas.drawRoundRect(rect, 8f, 8f, fillPaint)
        strokePaint.color = Color.rgb(226, 232, 240)
        canvas.drawRoundRect(rect, 8f, 8f, strokePaint)

        textPaint.color = Color.rgb(100, 116, 139)
        textPaint.textSize = 7.5f
        textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        textPaint.textAlign = Paint.Align.LEFT
        canvas.drawText(title, x + 10f, y + 18f, textPaint)

        textPaint.color = Color.rgb(15, 23, 42)
        textPaint.textSize = 14f
        textPaint.typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        canvas.drawText(value, x + 10f, y + 38f, textPaint)
    }

    private fun safeToDouble(value: Any?): Double {
        return when (value) {
            is Number -> value.toDouble()
            is String -> value.toDoubleOrNull() ?: 0.0
            else -> 0.0
        }
    }
}
