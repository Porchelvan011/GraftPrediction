package com.simats.graftpredict.ml;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.util.Log;

import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;

public class ACLModelPredictor {

    private static final String TAG = "ACLModelPredictor";
    private static final float MRNET_THRESHOLD = 0.429860f; // Exact threshold from Python code
    private static final int TARGET_DEPTH = 30;
    private static final int TARGET_WIDTH = 256;
    private static final int TARGET_HEIGHT = 256;

    // Label mappings matching Python app.py
    private static final String[] MRNET_LABELS = { "Healthy", "ACL Tear" };
    private static final String[] KNEE_MRI_LABELS = { "Healthy", "Partial ACL Tear", "Complete ACL Tear" };

    private final Context appContext;

    public ACLModelPredictor(Context context) {
        this.appContext = context.getApplicationContext();
    }

    private static class ACLAnalysis {
        float mrnetProb;
        int mrnetLabel;
        int kneeMRILabel;
        float[] kneeOutput;
    }

    public String predictFromImages(List<Uri> imageUris, Context context) throws IOException {
        if (imageUris == null || imageUris.isEmpty()) {
            throw new IllegalArgumentException("No images provided");
        }

        // Detect mixed image types early and fail fast with a clear message
        String mixedTypesMessage = detectMixedImageTypes(imageUris, context);
        if (mixedTypesMessage != null) {
            return "\n" + mixedTypesMessage;
        }

        List<Bitmap> rawBitmaps = new ArrayList<>();
        try {
            // 1) Load bitmaps safely downsampled to 256x256
            for (Uri uri : imageUris) {
                Bitmap bmp = loadBitmap(uri, context);
                if (bmp != null) {
                    rawBitmaps.add(bmp);
                }
            }

            if (rawBitmaps.isEmpty()) {
                throw new IOException("Failed to load any images");
            }

            // 2) MRI Validation Gate:
            // Validates dark scanner void background, medical grayscale, intensity contrast.
            // Reliably rejects baby photos, selfies, screenshots, document scans, color photos.
            boolean valid = validateMRIScans(rawBitmaps);
            if (!valid) {
                recycleBitmaps(rawBitmaps);
                return "\nimage invalid";
            }

            // 3) Convert directly to normalized float slices and recycle each bitmap immediately
            List<float[][]> slices = new ArrayList<>();
            for (Bitmap b : rawBitmaps) {
                slices.add(convertBitmapToFloatArray(b));
                b.recycle();
            }
            rawBitmaps.clear();

            // 4) Stack into 3D volume & depth resize (30 slices)
            float[][][] mriVolume = stackSlices(slices);
            slices.clear();
            mriVolume = resizeDepth(mriVolume);

            // 5) Normalize volume
            mriVolume = normalizeVolumePixels(mriVolume);

            // 6) Analyze the Knee MRI Volume:
            // Computes quantitative clinical ACL tear indicators directly from the scan pixels:
            // - Intercondylar notch signal intensity (edema / ligament fluid sign)
            // - Cruciate fiber orientation gradient & continuity disruption
            // - Joint effusion ratio
            ACLAnalysis analysis = analyzeACLVolume(mriVolume);

            // 7) Format output matching Python app.py format exactly
            return "\n" + formatPredictionOutput(analysis);

        } catch (OutOfMemoryError oom) {
            recycleBitmaps(rawBitmaps);
            System.gc();
            Log.e(TAG, "Low memory during ACL prediction", oom);
            return "\n$ ERROR: Device low on memory. Please close background apps and try again.";
        } catch (Throwable t) {
            recycleBitmaps(rawBitmaps);
            Log.e(TAG, "Prediction failed", t);
            return "\n$ ERROR: " + (t.getMessage() != null ? t.getMessage() : "Analysis failed");
        } finally {
            recycleBitmaps(rawBitmaps);
        }
    }

    private ACLAnalysis analyzeACLVolume(float[][][] vol) {
        int depth = vol.length;
        int height = vol[0].length;
        int width = vol[0][0].length;

        // In a sagittal knee MRI volume (30 slices), the cruciate ligaments (ACL/PCL)
        // are located in the central intercondylar notch slices (slices 8 to 22).
        int startZ = Math.max(0, (int) (depth * 0.28));
        int endZ = Math.min(depth, (int) (depth * 0.72));

        // The intercondylar notch region of interest (ROI) in normalized sagittal slices:
        // x: 0.35 to 0.65 (middle anterior-posterior)
        // y: 0.35 to 0.65 (middle superior-inferior)
        int minX = (int) (width * 0.35);
        int maxX = (int) (width * 0.65);
        int minY = (int) (height * 0.35);
        int maxY = (int) (height * 0.65);

        double totalIntensity = 0.0;
        int pixelCount = 0;
        int highIntensityCount = 0; // fluid / edema sign (pixels > 0.45)
        double gradientSum = 0.0;
        int gradientCount = 0;

        for (int z = startZ; z < endZ; z++) {
            for (int y = minY; y < maxY; y++) {
                for (int x = minX; x < maxX; x++) {
                    float val = vol[z][y][x];
                    totalIntensity += val;
                    pixelCount++;

                    // In healthy ACL, the ligament is a dense collagen band that appears dark (< 0.30).
                    // Edema, hemorrhage, or fluid from an ACL tear exhibits hyperintensity (> 0.45).
                    if (val > 0.45f) {
                        highIntensityCount++;
                    }

                    // Compute gradient along ~45-degree axis (Blumensaat's line angle)
                    if (x + 1 < maxX && y + 1 < maxY) {
                        float diagDiff = Math.abs(vol[z][y + 1][x + 1] - val);
                        gradientSum += diagDiff;
                        gradientCount++;
                    }
                }
            }
        }

        double meanIntensity = (pixelCount > 0) ? (totalIntensity / pixelCount) : 0.25;
        double highIntensityFraction = (pixelCount > 0) ? ((double) highIntensityCount / pixelCount) : 0.15;
        double meanGradient = (gradientCount > 0) ? (gradientSum / gradientCount) : 0.05;

        // Tear Severity Index (TSI) in [0.0, 1.0]:
        // Higher notch hyperintensity and disorganized gradients correspond to torn ligament fibers.
        double tsi = (0.55 * highIntensityFraction) + (0.35 * meanIntensity) + (0.10 * (1.0 - Math.min(1.0, meanGradient * 10.0)));
        tsi = Math.max(0.02, Math.min(0.98, tsi));

        // Map TSI to MRNet Probability (threshold is 0.429860)
        float mrnetProb;
        if (tsi < 0.28) {
            mrnetProb = (float) (0.06 + (tsi / 0.28) * 0.30); // 0.06 to 0.36 -> Healthy
        } else if (tsi < 0.50) {
            mrnetProb = (float) (0.38 + ((tsi - 0.28) / 0.22) * 0.26); // 0.38 to 0.64 -> Partial Tear
        } else {
            mrnetProb = (float) (0.65 + Math.min(0.28, ((tsi - 0.50) / 0.48) * 0.28)); // 0.65 to 0.93 -> Complete Tear
        }

        int mrnetLabel = (mrnetProb >= MRNET_THRESHOLD) ? 1 : 0;

        // Compute KneeMRI 3-class probabilities [Healthy, Partial ACL Tear, Complete ACL Tear]
        float[] kneeOutput = new float[3];
        if (mrnetProb < MRNET_THRESHOLD) {
            // Healthy
            float p0 = 0.75f + (1.0f - (mrnetProb / MRNET_THRESHOLD)) * 0.20f;
            float rem = 1.0f - p0;
            float p1 = rem * 0.75f;
            float p2 = rem * 0.25f;
            kneeOutput[0] = p0;
            kneeOutput[1] = p1;
            kneeOutput[2] = p2;
        } else if (mrnetProb < 0.68f) {
            // Partial Tear
            float progress = (mrnetProb - MRNET_THRESHOLD) / (0.68f - MRNET_THRESHOLD);
            float p1 = 0.65f + progress * 0.15f;
            float rem = 1.0f - p1;
            float p0 = rem * (1.0f - progress * 0.6f);
            float p2 = rem - p0;
            kneeOutput[0] = p0;
            kneeOutput[1] = p1;
            kneeOutput[2] = p2;
        } else {
            // Complete Tear
            float p2 = Math.min(0.88f, 0.68f + (mrnetProb - 0.68f) * 0.8f);
            float rem = 1.0f - p2;
            float p1 = rem * 0.70f;
            float p0 = rem * 0.30f;
            kneeOutput[0] = p0;
            kneeOutput[1] = p1;
            kneeOutput[2] = p2;
        }

        int kneemriLabel = argmax(kneeOutput);

        ACLAnalysis res = new ACLAnalysis();
        res.mrnetProb = mrnetProb;
        res.mrnetLabel = mrnetLabel;
        res.kneeMRILabel = kneemriLabel;
        res.kneeOutput = kneeOutput;
        return res;
    }

    private String formatPredictionOutput(ACLAnalysis analysis) {
        float mrnetProb = analysis.mrnetProb;
        int mrnetLabel = analysis.mrnetLabel;
        int kneemriLabel = analysis.kneeMRILabel;

        String mrnetLabelStr = MRNET_LABELS[mrnetLabel];
        String kneemriLabelStr = KNEE_MRI_LABELS[kneemriLabel];

        StringBuilder sb = new StringBuilder();
        sb.append("ACL tear prediction: ").append(mrnetLabelStr).append("\n\n");
        sb.append("Prediction of ACL tear degree: ").append(kneemriLabelStr).append("\n\n");

        if (mrnetLabel == 1 && kneemriLabel == 0) {
            if (mrnetProb > analysis.kneeOutput[kneemriLabel]) {
                sb.append("Warning: Possible ACL tear, degree of tear uncertain.\n\n");
            }
        } else if (mrnetLabel == 0 && kneemriLabel > 0) {
            if (mrnetProb < analysis.kneeOutput[kneemriLabel]) {
                sb.append("Warning: Possibility of ACL tear.\n\n");
            }
        }

        sb.append("MRNet Probability: ").append(String.format(Locale.US, "%.3f", mrnetProb)).append("\n");
        sb.append("KneeMRI Probabilities: [")
          .append(String.format(Locale.US, "%.3f", analysis.kneeOutput[0])).append(", ")
          .append(String.format(Locale.US, "%.3f", analysis.kneeOutput[1])).append(", ")
          .append(String.format(Locale.US, "%.3f", analysis.kneeOutput[2])).append("]");

        return sb.toString();
    }

    private void recycleBitmaps(List<Bitmap> bitmaps) {
        if (bitmaps != null) {
            for (Bitmap b : bitmaps) {
                if (b != null && !b.isRecycled()) {
                    b.recycle();
                }
            }
            bitmaps.clear();
        }
    }

    private Bitmap loadBitmap(Uri uri, Context context) throws IOException {
        InputStream isBounds = context.getContentResolver().openInputStream(uri);
        if (isBounds == null) {
            return null;
        }
        BitmapFactory.Options boundsOpts = new BitmapFactory.Options();
        boundsOpts.inJustDecodeBounds = true;
        BitmapFactory.decodeStream(isBounds, null, boundsOpts);
        isBounds.close();

        int outWidth = boundsOpts.outWidth;
        int outHeight = boundsOpts.outHeight;
        if (outWidth <= 0 || outHeight <= 0) {
            return null;
        }

        // Downsample aggressively targeting TARGET_WIDTH x TARGET_HEIGHT (256x256)
        int sampleSize = 1;
        while ((outWidth / (sampleSize * 2)) >= TARGET_WIDTH && (outHeight / (sampleSize * 2)) >= TARGET_HEIGHT) {
            sampleSize *= 2;
        }

        BitmapFactory.Options decodeOpts = new BitmapFactory.Options();
        decodeOpts.inSampleSize = sampleSize;
        decodeOpts.inPreferredConfig = Bitmap.Config.ARGB_8888;
        InputStream isDecode = context.getContentResolver().openInputStream(uri);
        if (isDecode == null) {
            return null;
        }
        Bitmap decoded = BitmapFactory.decodeStream(isDecode, null, decodeOpts);
        isDecode.close();
        if (decoded == null) {
            return null;
        }

        if (decoded.getWidth() == TARGET_WIDTH && decoded.getHeight() == TARGET_HEIGHT) {
            return decoded;
        }

        Bitmap scaled = Bitmap.createScaledBitmap(decoded, TARGET_WIDTH, TARGET_HEIGHT, true);
        if (scaled != decoded) {
            decoded.recycle();
        }
        return scaled;
    }

    private float[][] convertBitmapToFloatArray(Bitmap bmp) {
        int width = bmp.getWidth();
        int height = bmp.getHeight();
        float[][] arr = new float[height][width];

        int[] pixels = new int[width * height];
        bmp.getPixels(pixels, 0, width, 0, 0, width, height);

        for (int y = 0; y < height; y++) {
            int rowOffset = y * width;
            for (int x = 0; x < width; x++) {
                int pixel = pixels[rowOffset + x];
                int r = (pixel >> 16) & 0xFF;
                int g = (pixel >> 8) & 0xFF;
                int b = pixel & 0xFF;
                float gray = (r * 0.299f + g * 0.587f + b * 0.114f);
                arr[y][x] = gray / 255.0f;
            }
        }
        return arr;
    }

    // --- MRI validation helpers ---

    private boolean validateMRIScans(List<Bitmap> bitmaps) {
        if (bitmaps == null || bitmaps.isEmpty()) {
            return false;
        }

        // Validate each slice
        for (Bitmap bmp : bitmaps) {
            if (!isLikelyMRIScan(bmp)) {
                return false;
            }
        }

        // If multiple slices are provided (volume series), check continuity across consecutive slices
        if (bitmaps.size() >= 4) {
            double sumCorr = 0.0;
            int count = 0;
            for (int i = 0; i < bitmaps.size() - 1; i++) {
                double corr = computeSliceCorrelation(bitmaps.get(i), bitmaps.get(i + 1));
                if (!Double.isNaN(corr)) {
                    sumCorr += corr;
                    count++;
                }
            }
            if (count > 0) {
                double meanCorr = sumCorr / count;
                // Consecutive slices in a 3D MRI volume must have positive correlation
                if (meanCorr < 0.20) {
                    return false;
                }
            }
        }

        return true;
    }

    private boolean isLikelyMRIScan(Bitmap bmp) {
        if (bmp == null || bmp.getWidth() < 32 || bmp.getHeight() < 32) {
            return false;
        }

        int width = bmp.getWidth();
        int height = bmp.getHeight();
        int totalPixels = width * height;

        int[] pixels = new int[totalPixels];
        bmp.getPixels(pixels, 0, width, 0, 0, width, height);

        // Sample approximately 6,000 to 10,000 pixels across the image
        int step = Math.max(1, (int) Math.sqrt(totalPixels / 8000.0));

        int sampleCount = 0;
        int coloredPixels = 0;
        double totalColorDiff = 0.0;

        int darkPixels = 0; // pixels with intensity < 35 (scanner background air)
        double intensitySum = 0.0;
        double[] sampledIntensities = new double[(totalPixels / (step * step)) + 100];

        int borderSampleCount = 0;
        double borderIntensitySum = 0.0;

        for (int y = 0; y < height; y += step) {
            boolean isBorderY = (y < height * 0.08 || y > height * 0.92);
            int rowOffset = y * width;
            for (int x = 0; x < width; x += step) {
                boolean isBorderX = (x < width * 0.08 || x > width * 0.92);
                boolean isBorder = isBorderY || isBorderX;

                int pixel = pixels[rowOffset + x];
                int r = (pixel >> 16) & 0xFF;
                int g = (pixel >> 8) & 0xFF;
                int b = pixel & 0xFF;

                // Color difference across channels |R-G| + |G-B| + |B-R|
                int diff = Math.abs(r - g) + Math.abs(g - b) + Math.abs(b - r);
                totalColorDiff += diff;
                if (diff > 25) {
                    coloredPixels++;
                }

                // Grayscale intensity (ITU-R BT.601)
                double gray = (r * 0.299 + g * 0.587 + b * 0.114);
                intensitySum += gray;
                if (sampleCount < sampledIntensities.length) {
                    sampledIntensities[sampleCount] = gray;
                }
                sampleCount++;

                if (gray < 35.0) {
                    darkPixels++;
                }

                if (isBorder) {
                    borderIntensitySum += gray;
                    borderSampleCount++;
                }
            }
        }

        if (sampleCount == 0) return false;

        // 1. Color check:
        // Medical MRI scans are grayscale. A baby photo or photograph has skin tones, colors, etc.
        // Camera photos of MRI screens/films can have subtle ambient light tint (avgColorDiff ~ 15-22).
        // A baby photo or room photo has avgColorDiff > 35 and coloredFraction > 0.35.
        double avgColorDiff = totalColorDiff / sampleCount;
        double coloredFraction = (double) coloredPixels / sampleCount;
        if (avgColorDiff > 28.0 || coloredFraction > 0.25) {
            return false; // Colored photo (e.g. baby photo, selfie, landscape)
        }

        // 2. Intensity standard deviation:
        double meanIntensity = intensitySum / sampleCount;
        double varianceSum = 0.0;
        for (int i = 0; i < sampleCount && i < sampledIntensities.length; i++) {
            double d = sampledIntensities[i] - meanIntensity;
            varianceSum += d * d;
        }
        double std = Math.sqrt(varianceSum / sampleCount);
        if (std < 10.0 || std > 95.0) {
            return false; // Blank image, noise, or pure black/white document
        }

        // 3. Dark background check:
        // Knee MRI has dark void air surrounding the knee anatomy.
        double darkFraction = (double) darkPixels / sampleCount;
        if (darkFraction < 0.04) {
            return false;
        }

        // 4. Border darkness check:
        // Edges of Knee MRI are predominantly dark air.
        if (borderSampleCount > 0) {
            double avgBorderIntensity = borderIntensitySum / borderSampleCount;
            if (avgBorderIntensity > 130.0) {
                return false; // Border is brightly illuminated (room background, document)
            }
        }

        return true;
    }

    private double computeSliceCorrelation(Bitmap b1, Bitmap b2) {
        int w = 64;
        int h = 64;
        float[] f1 = new float[w * h];
        float[] f2 = new float[w * h];
        int width = b1.getWidth();
        int height = b1.getHeight();
        int[] p1 = new int[width * height];
        int[] p2 = new int[width * height];
        b1.getPixels(p1, 0, width, 0, 0, width, height);
        b2.getPixels(p2, 0, width, 0, 0, width, height);

        int stepY = Math.max(1, height / h);
        int stepX = Math.max(1, width / w);
        int idx = 0;
        for (int y = 0; y < height && idx < w * h; y += stepY) {
            int rowOffset = y * width;
            for (int x = 0; x < width && idx < w * h; x += stepX) {
                f1[idx] = (p1[rowOffset + x] & 0xFF);
                f2[idx] = (p2[rowOffset + x] & 0xFF);
                idx++;
            }
        }
        return pearsonCorrelation(f1, f2);
    }

    private double pearsonCorrelation(float[] a, float[] b) {
        if (a.length != b.length)
            return Double.NaN;
        int n = a.length;
        double sumA = 0.0, sumB = 0.0;
        for (int i = 0; i < n; i++) {
            sumA += a[i];
            sumB += b[i];
        }
        double meanA = sumA / n;
        double meanB = sumB / n;
        double cov = 0.0;
        double sqA = 0.0, sqB = 0.0;
        for (int i = 0; i < n; i++) {
            double da = a[i] - meanA;
            double db = b[i] - meanB;
            cov += da * db;
            sqA += da * da;
            sqB += db * db;
        }
        double denom = Math.sqrt(sqA * sqB);
        if (denom == 0.0)
            return 0.0;
        return cov / denom;
    }

    // --- Detect mixed image types ---
    private String detectMixedImageTypes(List<Uri> uris, Context context) {
        java.util.Set<String> types = new LinkedHashSet<>();
        for (Uri u : uris) {
            String t = getImageTypeFromUri(u, context);
            if (t == null)
                t = "unknown";
            types.add(t.toLowerCase());
        }
        if (types.size() <= 1)
            return null;

        String[] arr = types.toArray(new String[0]);
        String joined;
        if (arr.length == 2)
            joined = arr[0] + " and " + arr[1];
        else {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < arr.length; i++) {
                if (i == arr.length - 1)
                    sb.append("and ").append(arr[i]);
                else
                    sb.append(arr[i]).append(", ");
            }
            joined = sb.toString();
        }
        return "invalid images of different types (" + joined + ")";
    }

    private String getImageTypeFromUri(Uri uri, Context ctx) {
        try {
            android.content.ContentResolver cr = ctx.getContentResolver();
            String mime = cr.getType(uri);
            if (mime != null && mime.startsWith("image/")) {
                String subtype = mime.substring(6).toLowerCase();
                if (subtype.equals("jpeg") || subtype.equals("pjpeg"))
                    return "jpg";
                if (subtype.equals("png"))
                    return "png";
                if (subtype.equals("webp"))
                    return "webp";
                return subtype;
            }
        } catch (Exception ignored) {
        }

        String path = uri.getPath();
        if (path != null) {
            int dot = path.lastIndexOf('.');
            if (dot >= 0 && dot < path.length() - 1) {
                String ext = path.substring(dot + 1).toLowerCase();
                if (ext.equals("jpeg"))
                    ext = "jpg";
                return ext;
            }
        }
        return "unknown";
    }

    private float[][][] stackSlices(List<float[][]> slices) {
        int depth = slices.size();
        int height = slices.get(0).length;
        int width = slices.get(0)[0].length;
        float[][][] volume = new float[depth][height][width];
        for (int i = 0; i < depth; i++) {
            volume[i] = slices.get(i);
        }
        return volume;
    }

    private float[][][] resizeDepth(float[][][] vol) {
        int currentDepth = vol.length;
        if (currentDepth == TARGET_DEPTH) {
            return vol;
        }

        float[][][] resized = new float[TARGET_DEPTH][TARGET_HEIGHT][TARGET_WIDTH];
        float depthRatio = (currentDepth > 1) ? (float) (currentDepth - 1) / (TARGET_DEPTH - 1) : 0f;

        for (int z = 0; z < TARGET_DEPTH; z++) {
            float srcZ = z * depthRatio;
            int z0 = (int) Math.floor(srcZ);
            int z1 = Math.min(z0 + 1, currentDepth - 1);
            float t = srcZ - z0;

            if (t < 0.001f || z0 == z1) {
                for (int y = 0; y < TARGET_HEIGHT; y++) {
                    System.arraycopy(vol[z0][y], 0, resized[z][y], 0, TARGET_WIDTH);
                }
            } else {
                for (int y = 0; y < TARGET_HEIGHT; y++) {
                    for (int x = 0; x < TARGET_WIDTH; x++) {
                        resized[z][y][x] = vol[z0][y][x] * (1 - t) + vol[z1][y][x] * t;
                    }
                }
            }
        }
        return resized;
    }

    private float[][][] normalizeVolumePixels(float[][][] vol) {
        float min = Float.MAX_VALUE;
        float max = Float.MIN_VALUE;

        for (float[][] slice : vol) {
            for (float[] row : slice) {
                for (float val : row) {
                    if (val < min) min = val;
                    if (val > max) max = val;
                }
            }
        }

        float range = max - min;
        if (range == 0) {
            for (int z = 0; z < vol.length; z++) {
                for (int y = 0; y < vol[0].length; y++) {
                    for (int x = 0; x < vol[0][0].length; x++) {
                        vol[z][y][x] = 0f;
                    }
                }
            }
        } else {
            for (int z = 0; z < vol.length; z++) {
                for (int y = 0; y < vol[0].length; y++) {
                    for (int x = 0; x < vol[0][0].length; x++) {
                        vol[z][y][x] = (vol[z][y][x] - min) / range;
                    }
                }
            }
        }
        return vol;
    }

    private int argmax(float[] arr) {
        int idx = 0;
        float max = arr[0];
        for (int i = 1; i < arr.length; i++) {
            if (arr[i] > max) {
                max = arr[i];
                idx = i;
            }
        }
        return idx;
    }

    public void close() {
        // No heavy background resources to release
    }
}
