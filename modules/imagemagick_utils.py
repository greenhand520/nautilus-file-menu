import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .gio_utils import finalize_outputs
from .notify import logger
from .path_utils import find_binary

# ImageMagick 7 uses `magick <subcommand>`; ImageMagick 6 commonly exposes
# standalone `mogrify`, `convert`, and `identify` commands.
MAGICK_BIN = find_binary("magick")
CONVERT_BIN = find_binary("convert")
MOGRIFY_BIN = find_binary("mogrify")
IDENTIFY_BIN = find_binary("identify")

FORMAT_EXTENSIONS = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "JPG": ".jpg",
    "WEBP": ".webp",
    "BMP": ".bmp",
    "TIFF": ".tiff",
}

RESIZE_FORMAT_MAP = {
    ".jpg": "JPEG", ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
    ".tiff": "TIFF", ".tif": "TIFF",
    ".bmp": "BMP",
}

BATCH_SIZE = 100


def has_imagemagick() -> bool:
    """Check if an ImageMagick identify/convert capability is available."""
    return bool(MAGICK_BIN or CONVERT_BIN)


def has_mogrify() -> bool:
    """Check if the batch mogrify command is available."""
    return bool(MAGICK_BIN or MOGRIFY_BIN)


def _mogrify_command():
    if MAGICK_BIN:
        return [MAGICK_BIN, "mogrify"]
    if MOGRIFY_BIN:
        return [MOGRIFY_BIN]
    return None


def _identify_command():
    if MAGICK_BIN:
        return [MAGICK_BIN, "identify"]
    if IDENTIFY_BIN:
        return [IDENTIFY_BIN]
    if CONVERT_BIN:
        return [CONVERT_BIN, "identify"]
    return None


def _run_mogrify_batches(file_list, output_dir, options, suffix,
                         check_smaller=False, operation="mogrify"):
    """Run mogrify in batches and finalize only expected outputs."""
    if not file_list or not has_mogrify():
        return []

    output_dir = str(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    temp_dir = tempfile.mkdtemp(prefix=f".nf-{operation}-", dir=output_dir)
    results = []
    started = time.perf_counter()
    backend_finished = started
    finalized = started

    try:
        command = _mogrify_command()
        for start in range(0, len(file_list), BATCH_SIZE):
            batch = file_list[start:start + BATCH_SIZE]
            cmd = command + list(options) + ["-path", temp_dir, *batch]
            logger.info("%s batch: %d/%d files", operation, len(batch), len(file_list))
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=600,
                )
            except subprocess.TimeoutExpired:
                logger.error("%s batch timeout", operation)
                continue
            except OSError:
                logger.exception("%s batch failed to start", operation)
                continue

            if result.returncode != 0:
                logger.warning("%s batch failed: %s", operation,
                               result.stderr.strip()[:500])

        backend_finished = time.perf_counter()
        records = []
        for src_path in file_list:
            name = os.path.basename(src_path)
            temp_path = os.path.join(temp_dir, name)
            base, ext = os.path.splitext(name)
            output_path = os.path.join(output_dir, f"{base}{suffix}{ext}")
            records.append((temp_path, output_path, src_path))

        results = finalize_outputs(records, check_smaller=check_smaller)
        finalized = time.perf_counter()
        logger.info(
            "%s timing: backend=%.3fs finalize=%.3fs files=%d",
            operation,
            backend_finished - started,
            finalized - backend_finished,
            len(file_list),
        )
        return results
    finally:
        cleanup_started = time.perf_counter()
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.info(
            "%s cleanup: %.3fs files=%d",
            operation,
            time.perf_counter() - cleanup_started,
            len(file_list),
        )


def convert_format(file_list, output_dir: str, target_format: str) -> tuple[int, int]:
    """Convert images using ImageMagick mogrify in batches."""
    total = len(file_list)
    if not file_list or not has_mogrify():
        logger.warning("ImageMagick mogrify is not available")
        return 0, total

    normalized = target_format.upper()
    if normalized == "JPG":
        normalized = "JPEG"
    output_ext = FORMAT_EXTENSIONS.get(normalized, f".{target_format.lower()}")

    # `mogrify -format` writes the target extension into the staging directory.
    # It is finalized to output_dir after processing.
    output_dir = str(Path(output_dir))
    os.makedirs(output_dir, exist_ok=True)
    temp_dir = tempfile.mkdtemp(prefix=".nf-convert-", dir=output_dir)
    results = []

    try:
        command = _mogrify_command()
        for start in range(0, total, BATCH_SIZE):
            batch = file_list[start:start + BATCH_SIZE]
            cmd = command + [
                "-format", normalized.lower(),
                "-path", temp_dir,
                *batch,
            ]
            logger.info("mogrify convert batch: %d/%d files -> %s",
                        len(batch), total, normalized)
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=600,
                )
            except subprocess.TimeoutExpired:
                logger.error("mogrify convert batch timeout")
                continue
            except OSError:
                logger.exception("mogrify convert batch failed to start")
                continue

            if result.returncode != 0:
                logger.warning("mogrify convert batch failed: %s",
                               result.stderr.strip()[:500])

        records = []
        for src_path in file_list:
            base = Path(src_path).stem
            temp_path = os.path.join(temp_dir, f"{base}{output_ext}")
            output_path = os.path.join(output_dir, f"{base}{output_ext}")
            records.append((temp_path, output_path, src_path))
        results = finalize_outputs(records)
        return len(results), total
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def compress_batch_by_quality(file_list, output_dir, quality):
    """Compress files with ImageMagick while preserving original files."""
    return _run_mogrify_batches(
        file_list,
        output_dir,
        ["-quality", str(int(quality))],
        f"_q{int(quality)}",
        check_smaller=True,
        operation="IM compress",
    )


def _batch_mogrify_resize(file_list, output_dir, resize_arg, suffix):
    return _run_mogrify_batches(
        file_list,
        output_dir,
        ["-resize", resize_arg],
        suffix,
        operation="mogrify resize",
    )


def resize_batch_by_dimensions(file_list, output_dir, width, height) -> tuple[int, int]:
    """Batch resize images to exact dimensions using ImageMagick."""
    total = len(file_list)
    if not file_list or not has_mogrify():
        return 0, total
    results = _batch_mogrify_resize(
        file_list, output_dir, f"{width}x{height}!", f"_{width}x{height}"
    )
    return len(results), total


def resize_batch_by_percent(file_list, output_dir, percent) -> tuple[int, int]:
    """Batch resize images by percentage using ImageMagick."""
    total = len(file_list)
    if not file_list or not has_mogrify():
        return 0, total
    pct_label = int(percent) if percent == int(percent) else percent
    results = _batch_mogrify_resize(
        file_list, output_dir, f"{percent}%", f"_p{pct_label}"
    )
    return len(results), total


def get_image_size(src_path):
    """Get image dimensions using ImageMagick. Returns (width, height)."""
    command = _identify_command()
    if not command:
        return 0, 0
    try:
        result = subprocess.run(
            command + ["-format", "%w %h", src_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split()
            if len(parts) == 2:
                return int(parts[0]), int(parts[1])
    except Exception as exc:
        logger.exception("Failed to get image size with IM, cause: %s", exc)
    return 0, 0
