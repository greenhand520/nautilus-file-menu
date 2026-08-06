import os
import shutil
import subprocess
import tempfile
import time

from .gio_utils import finalize_outputs, group_paths_by_parent
from .notify import logger
from .path_utils import find_binary

PNGQUANT_BIN = find_binary("pngquant")
BATCH_SIZE = 100


def has_pngquant() -> bool:
    """Check if pngquant is available."""
    return PNGQUANT_BIN is not None


def _quality_range(quality):
    q_max = max(1, min(100, int(quality)))
    return max(0, q_max - 15), q_max


def _compress_group(file_list, quality, suffix):
    """Compress one parent-directory group without copying original bytes."""
    if not file_list:
        return []

    q_min, q_max = _quality_range(quality)
    temp_dir = tempfile.mkdtemp(prefix=".nf-pngquant-", dir=os.path.dirname(file_list[0]))
    linked = []
    started = time.perf_counter()
    backend_finished = started
    finalized = started

    try:
        # Hard links keep the original data blocks in place while giving
        # pngquant a private, hidden staging directory. This avoids the old
        # copy2() pass and avoids exposing intermediate files in Nautilus.
        for src_path in file_list:
            staged_input = os.path.join(temp_dir, os.path.basename(src_path))
            try:
                os.link(src_path, staged_input)
                linked.append((src_path, staged_input))
            except OSError:
                logger.warning("pngquant: cannot stage %s with hard link", src_path)

        for start in range(0, len(linked), BATCH_SIZE):
            batch = linked[start:start + BATCH_SIZE]
            staged_inputs = [staged for _, staged in batch]
            cmd = [
                PNGQUANT_BIN,
                "--quality", f"{q_min}-{q_max}",
                "--speed", "3",
                "--force",
                "--skip-if-larger",
                "--ext", f"{suffix}.png",
                "--",
                *staged_inputs,
            ]

            logger.info("pngquant batch: %d/%d files", len(batch), len(linked))
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=300,
                )
            except subprocess.TimeoutExpired:
                logger.error("pngquant: timeout on batch of %d files", len(batch))
                continue
            except OSError:
                logger.exception("pngquant: failed to start batch")
                continue

            if result.returncode != 0:
                logger.warning("pngquant batch failed: %s",
                               result.stderr.strip()[:500])

        backend_finished = time.perf_counter()
        records = []
        for src_path, staged_input in linked:
            staged_base, ext = os.path.splitext(staged_input)
            source_base, source_ext = os.path.splitext(src_path)
            staged_output = f"{staged_base}{suffix}{ext}"
            output_path = f"{source_base}{suffix}{source_ext}"
            records.append((staged_output, output_path, src_path))

        results = finalize_outputs(records, check_smaller=True)
        finalized = time.perf_counter()
        logger.info(
            "pngquant timing: backend=%.3fs finalize=%.3fs files=%d",
            backend_finished - started,
            finalized - backend_finished,
            len(file_list),
        )
        return results
    finally:
        cleanup_started = time.perf_counter()
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.info(
            "pngquant cleanup: %.3fs files=%d",
            time.perf_counter() - cleanup_started,
            len(file_list),
        )


def compress_batch(file_list, quality, suffix=None) -> list[str]:
    """Batch compress PNG files with pngquant.

    The input list may contain files from multiple directories. Each group is
    processed independently so outputs stay beside their corresponding source.
    """
    if not PNGQUANT_BIN or not file_list:
        return []

    if suffix is None:
        suffix = f"_q{int(quality)}"

    results = []
    for _, group in group_paths_by_parent(file_list).items():
        results.extend(_compress_group(group, quality, suffix))

    logger.info("pngquant done: %d/%d files compressed", len(results), len(file_list))
    return results
