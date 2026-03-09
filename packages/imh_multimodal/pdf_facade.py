"""
TASK-M Sprint 2: PDF-to-Text integration facade (plan §6)

Design:
  - Wraps existing LocalPDFProvider (pypdf).
  - Timeout: 3 seconds (hard limit).
  - Fallback: on failure or timeout, returns "" (empty string).
  - Result is stored immutably in session_config_snapshot["resume_text"].
  - Plan §6 Constraints: text-layer only; no OCR; page/size limits enforced.

If MM_ENABLE_PDF_TEXT=False (default), extract_resume_text() returns "" immediately.
No DB writes in this module — the caller (SessionEngine) owns the snapshot write.
"""
from __future__ import annotations
import logging
import threading
from typing import Optional

from packages.imh_multimodal.mm_flags import MMFlags

logger = logging.getLogger("imh.multimodal.pdf")

_PDF_TIMEOUT_SEC = 3
_MAX_PAGES = 30           # plan §6 page limit
_MAX_FILE_SIZE_MB = 10    # plan §6 file size limit


def extract_resume_text(
    pdf_path: str,
    timeout: int = _PDF_TIMEOUT_SEC,
) -> str:
    """
    Extract plain text from a PDF file using the existing LocalPDFProvider.

    Returns:
        Extracted text string (trimmed).
        "" on any error, timeout, or when feature flag is off.

    Contract:
        Caller stores result into session_config_snapshot["resume_text"].
        This function MUST NOT write to the database.
    """
    if not MMFlags.pdf_text_active():
        return ""

    import os
    # File size guard
    try:
        size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
        if size_mb > _MAX_FILE_SIZE_MB:
            logger.warning(
                "PDF too large (%.1f MB > %d MB limit) — skipping: %s",
                size_mb, _MAX_FILE_SIZE_MB, pdf_path,
            )
            return ""
    except OSError as exc:
        logger.warning("PDF file access error: %s — %s", pdf_path, exc)
        return ""

    result: list[str] = [""]

    def _extract():
        try:
            import pypdf  # type: ignore
            reader = pypdf.PdfReader(pdf_path, strict=False)
            pages = reader.pages[:_MAX_PAGES]
            text = "\n".join(
                (page.extract_text() or "") for page in pages
            )
            result[0] = text.strip()
        except Exception as exc:
            logger.warning("PDF extraction failed for %s: %s — returning empty", pdf_path, exc)

    thread = threading.Thread(target=_extract, daemon=True, name="pdf-extract")
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        logger.warning("PDF extraction timed out after %ds — returning empty", timeout)
        return ""

    return result[0]
