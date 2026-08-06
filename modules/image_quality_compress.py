import io
import logging
import os
import shutil
import subprocess

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

FORMAT_MAP = {
    ".jpg": "JPEG", ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
    ".tiff": "TIFF", ".tif": "TIFF",
}

PNGQUANT_BIN = shutil.which("pngquant")


def _count_unique_colors(img):
    """Count unique colors in an image (memory-efficient for large images)."""
    rgb = img.convert("RGB")
    colors = set()
    for pixel in rgb.getdata():
        colors.add(pixel)
        if len(colors) > 100000:  # cap to avoid OOM on huge images
            return len(colors)
    return len(colors)


def _compress_jpeg_webp(img, fmt, orig_size, quality):
    """Compress JPEG or WEBP using binary search for optimal quality."""
    if fmt == "JPEG" and img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    def _encode(q):
        buf = io.BytesIO()
        if fmt == "JPEG":
            img.save(buf, "JPEG", quality=q, progressive=True, optimize=True)
        else:
            img.save(buf, "WEBP", quality=q, method=6)
        return buf

    best_buf = None
    diag = {}

    # Try requested quality first
    trial = _encode(quality)
    if trial.tell() < orig_size:
        best_buf = trial
        diag["actual_quality"] = quality
    else:
        # Binary search for the highest quality that fits
        lo, hi = 1, quality - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            trial = _encode(mid)
            if trial.tell() < orig_size:
                best_buf = trial
                diag["actual_quality"] = mid
                lo = mid + 1
            else:
                hi = mid - 1

    return best_buf, diag


def _compress_png_pngquant(src_path, dst_path, quality):
    """Compress PNG using pngquant. Returns (success, diag)."""
    log = logging.getLogger("nautilus-file-menu")
    q_max = max(1, min(100, quality))
    q_min = max(0, q_max - 15)

    cmd = [
        PNGQUANT_BIN,
        "--quality", f"{q_min}-{q_max}",
        "--speed", "1",
        "--force",
        "--skip-if-larger",
        "--output", dst_path,
        src_path,
    ]

    log.info("pngquant: running %s", " ".join(cmd))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        log.info("pngquant: returncode=%d, stderr=%s", result.returncode, result.stderr.strip()[:200])
    except subprocess.TimeoutExpired:
        log.error("pngquant: timeout after 120s")
        return False, {"error": "pngquant timeout"}

    if result.returncode == 0 and os.path.isfile(dst_path):
        src_size = os.path.getsize(src_path)
        dst_size = os.path.getsize(dst_path)
        log.info("pngquant: success, %d -> %d bytes", src_size, dst_size)
        return True, {
            "method": "pngquant",
            "pngquant_quality": f"{q_min}-{q_max}",
            "original_size": src_size,
            "output_size": dst_size,
            "ratio": f"{(dst_size - src_size) / src_size * 100:+.1f}%",
        }

    log.info("pngquant: skipped (exit %d), trying Pillow fallback", result.returncode)
    return False, {
        "method": "pngquant",
        "error": result.stderr.strip() or f"exit code {result.returncode}",
    }


def _compress_png_pillow(img, orig_size, quality):
    """Compress PNG using Pillow (fallback when pngquant is unavailable)."""
    log = logging.getLogger("nautilus-file-menu")
    log.info("Pillow PNG: starting, quality=%d, orig_size=%d", quality, orig_size)
    diag = {"method": "pillow"}
    best_buf = None

    # Lossless optimization
    lossless = io.BytesIO()
    img.save(lossless, "PNG", optimize=True)
    diag["lossless_size"] = lossless.tell()
    log.info("Pillow PNG: lossless size=%d", lossless.tell())

    if quality >= 95 and lossless.tell() < orig_size:
        return lossless, diag

    target_colors = max(2, int(quality * 2.55))
    diag["target_colors"] = target_colors

    # Check if image already has fewer colors than target
    if img.mode in ("RGBA", "LA", "P"):
        rgb_for_count = img.convert("RGB")
    else:
        rgb_for_count = img
    try:
        actual_colors = _count_unique_colors(rgb_for_count)
    except Exception:
        actual_colors = None
    diag["actual_colors"] = actual_colors

    if actual_colors is not None and actual_colors <= target_colors:
        if lossless.tell() < orig_size:
            return lossless, diag
        return None, diag

    # Quantize
    if img.mode in ("RGBA", "LA"):
        q_img = img.quantize(colors=target_colors, method=Image.Quantize.FASTOCTREE)
    elif img.mode == "P":
        q_img = img
    else:
        q_img = img.convert("RGB").quantize(colors=target_colors, method=Image.Quantize.MEDIANCUT)

    lossy = io.BytesIO()
    q_img.save(lossy, "PNG", optimize=True)
    diag["lossy_size"] = lossy.tell()

    for buf in (lossless, lossy):
        if buf.tell() < orig_size:
            if best_buf is None or buf.tell() < best_buf.tell():
                best_buf = buf

    return best_buf, diag


def _compress_png_subprocess(src_path, dst_path, quality, orig_size):
    """Compress PNG with pngquant, falling back to Pillow when needed."""
    log = logging.getLogger("nautilus-file-menu")
    diag = {"format": "PNG"}

    # Try pngquant
    if PNGQUANT_BIN:
        q_max = max(1, min(100, quality))
        q_min = max(0, q_max - 15)
        cmd = [
            PNGQUANT_BIN,
            "--quality", f"{q_min}-{q_max}",
            "--speed", "3",
            "--force",
            "--skip-if-larger",
            "--output", dst_path,
            src_path,
        ]
        log.info("pngquant: %s", " ".join(cmd))
        result = None
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            log.info("pngquant: exit=%d", result.returncode)
        except subprocess.TimeoutExpired:
            log.error("pngquant: timeout; trying Pillow fallback")

        if result is not None and result.returncode == 0 and os.path.isfile(dst_path):
            dst_size = os.path.getsize(dst_path)
            if dst_size < orig_size:
                diag.update({
                    "method": "pngquant",
                    "output_size": dst_size,
                    "ratio": f"{(dst_size - orig_size) / orig_size * 100:+.1f}%",
                })
                return True, diag
            os.remove(dst_path)
            log.info("pngquant: output larger, trying Pillow fallback")

        if result is not None:
            log.info("pngquant failed (exit %d), trying Pillow fallback",
                     result.returncode)

    if HAS_PIL:
        try:
            with Image.open(src_path) as img:
                best_buf, pillow_diag = _compress_png_pillow(
                    img, orig_size, quality
                )
            if best_buf:
                best_buf.seek(0)
                with open(dst_path, "wb") as output:
                    output.write(best_buf.getvalue())
                dst_size = os.path.getsize(dst_path)
                return True, {
                    **diag,
                    **pillow_diag,
                    "output_size": dst_size,
                    "ratio": f"{(dst_size - orig_size) / orig_size * 100:+.1f}%",
                }
        except Exception:
            log.exception("Pillow PNG fallback failed: %s", src_path)

    if not PNGQUANT_BIN:
        error = "pngquant not found"
    elif result is None:
        error = "pngquant timeout"
    else:
        error = result.stderr.strip() or f"exit {result.returncode}"
    return False, {**diag, "method": "pngquant", "error": error}


def _compress_png(img, src_path, dst_path, orig_size, quality):
    """Compress PNG: try pngquant first, fall back to Pillow (main thread only)."""
    diag = {}

    # Try pngquant
    if PNGQUANT_BIN:
        ok, pq_diag = _compress_png_pngquant(src_path, dst_path, quality)
        diag.update(pq_diag)
        if ok:
            diag["output_size"] = os.path.getsize(dst_path)
            diag["ratio"] = pq_diag.get("ratio", "")
            return True, diag
        diag["fallback_reason"] = pq_diag.get("error", "pngquant output larger")

    # Fallback to Pillow
    best_buf, pillow_diag = _compress_png_pillow(img, orig_size, quality)
    diag.update(pillow_diag)

    if best_buf:
        best_buf.seek(0)
        with open(dst_path, "wb") as f:
            f.write(best_buf.getvalue())
        diag["output_size"] = os.path.getsize(dst_path)
        diag["ratio"] = f"{(diag['output_size'] - orig_size) / orig_size * 100:+.1f}%"
        return True, diag

    diag["output_size"] = None
    return False, diag


def _compress_tiff(img, dst_path, orig_size, quality):
    """Compress TIFF by trying LZW, deflate, and JPEG in order."""
    diag = {}

    if img.mode in ("RGBA", "LA", "P", "CMYK"):
        pass  # keep as-is for these modes
    elif img.mode != "RGB":
        img = img.convert("RGB")

    best_buf = None
    for method in ("tiff_lzw", "tiff_deflate", "jpeg"):
        buf = io.BytesIO()

        if method == "jpeg":
            if img.mode not in ("RGB", "L"):
                continue
            img.save(buf, "TIFF", compression="jpeg", quality=quality)
        else:
            img.save(buf, "TIFF", compression=method)

        if buf.tell() < orig_size:
            best_buf = buf
            diag["compression_method"] = method
            break

    if best_buf:
        best_buf.seek(0)
        with open(dst_path, "wb") as f:
            f.write(best_buf.getvalue())
        diag["output_size"] = os.path.getsize(dst_path)
        diag["ratio"] = f"{(diag['output_size'] - orig_size) / orig_size * 100:+.1f}%"
        return True, diag

    diag["output_size"] = None
    return False, diag


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compress_image(src_path, dst_path, quality):
    """
    Compress an image file. Output is only written if smaller than the original.

    quality (1-100):
      JPEG/WEBP → encoding quality
      PNG       → color count (100=lossless only, lower=fewer colors)
      TIFF      → JPEG compression quality (for lossy method)

    Returns: (success: bool, diag: dict)
    """
    quality = max(1, min(100, quality))
    orig_size = os.path.getsize(src_path)
    ext = os.path.splitext(src_path)[1].lower()
    fmt = FORMAT_MAP.get(ext)

    diag = {
        "format": fmt,
        "original_size": orig_size,
        "quality": quality,
    }

    # PNG: use pngquant subprocess only (avoids PIL threading issues)
    if fmt == "PNG":
        ok, png_diag = _compress_png_subprocess(src_path, dst_path, quality, orig_size)
        diag.update(png_diag)
        return ok, diag

    # JPEG/WEBP/TIFF: use PIL (must be called from main thread or idle handler)
    if not HAS_PIL:
        return False, {"error": "Pillow not installed"}

    with Image.open(src_path) as img:
        img.load()
        diag["mode"] = img.mode

        if fmt in ("JPEG", "WEBP"):
            best_buf, fmt_diag = _compress_jpeg_webp(img, fmt, orig_size, quality)
            diag.update(fmt_diag)

            if best_buf:
                best_buf.seek(0)
                with open(dst_path, "wb") as f:
                    f.write(best_buf.getvalue())
                diag["output_size"] = os.path.getsize(dst_path)
                diag["ratio"] = f"{(diag['output_size'] - orig_size) / orig_size * 100:+.1f}%"
                return True, diag

        elif fmt == "TIFF":
            return _compress_tiff(img, dst_path, orig_size, quality)

    diag["output_size"] = None
    return False, diag
