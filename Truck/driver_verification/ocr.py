"""
OCR extraction from license images using PaddleOCR.
Faster and more accurate than EasyOCR on document/ID card text.
"""
import re
import logging
from datetime import date, datetime
from typing import Optional

logger = logging.getLogger(__name__)

_ocr_engine = None


def _get_engine():
    """Lazy-load PaddleOCR (downloads models on first call if not cached)."""
    global _ocr_engine
    if _ocr_engine is None:
        from paddleocr import PaddleOCR  # deferred — heavy import
        _ocr_engine = PaddleOCR(
            use_angle_cls=True,   # handles rotated/angled license photos
            lang='en',
            use_gpu=False,
            show_log=False,       # suppress paddle verbose output
        )
    return _ocr_engine


def extract_license_text(image_path: str) -> list[str]:
    """
    Run PaddleOCR on the license image.
    Returns a flat list of detected text strings, confidence-filtered.
    """
    engine = _get_engine()
    result = engine.ocr(image_path, cls=True)

    lines: list[str] = []
    if not result or not result[0]:
        logger.warning("PaddleOCR returned no results for %s", image_path)
        return lines

    for line in result[0]:
        text, confidence = line[1][0], line[1][1]
        if confidence >= 0.6:          # discard low-confidence detections
            lines.append(text.strip())

    logger.debug("OCR extracted %d lines from %s: %s", len(lines), image_path, lines)
    return lines


def parse_license_data(lines: list[str]) -> dict:
    """
    Parse OCR text lines into structured license fields.
    Returns: {license_number, license_class, expiry_date}
    All values are None when not detected.
    """
    text_block = " ".join(lines).upper()

    return {
        "license_number": _extract_license_number(text_block),
        "license_class":  _extract_license_class(text_block),
        "expiry_date":    _extract_expiry_date(text_block),
    }


def _extract_license_number(text: str) -> Optional[str]:
    patterns = [
        r'\bDL[#:\s]*([A-Z0-9]{6,12})\b',
        r'\bLIC(?:ENSE)?[#:\s]*([A-Z0-9]{6,12})\b',
        r'\bNO[.:\s]+([A-Z0-9]{6,12})\b',
        r'\b([A-Z]{1,3}[0-9]{6,9})\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def _extract_license_class(text: str) -> Optional[str]:
    match = re.search(r'\bCLASS[:\s]*([A-E])\b', text)
    if match:
        return match.group(1)
    for cls in ['CDL-A', 'CDL-B', 'CDL-C', 'CLASS A', 'CLASS B', 'CLASS C']:
        if cls in text:
            return cls.replace('CLASS ', '')
    return None


def _extract_expiry_date(text: str) -> Optional[date]:
    date_patterns = [
        (r'\b(\d{2}/\d{2}/\d{4})\b', '%m/%d/%Y'),
        (r'\b(\d{2}-\d{2}-\d{4})\b', '%m-%d-%Y'),
        (r'\b(\d{4}-\d{2}-\d{2})\b', '%Y-%m-%d'),
        (r'\b(\d{2}/\d{2}/\d{4})\b', '%d/%m/%Y'),
    ]
    exp_keywords = ('EXP', 'EXPIR', 'EXPIRES', 'EXPIRY', 'VALID THRU', 'VALID THROUGH')

    for keyword in exp_keywords:
        idx = text.find(keyword)
        if idx == -1:
            continue
        nearby = text[idx: idx + 30]
        for pattern, fmt in date_patterns:
            match = re.search(pattern, nearby)
            if match:
                try:
                    return datetime.strptime(match.group(1), fmt).date()
                except ValueError:
                    continue

    # Fallback: any future date in the full text
    for pattern, fmt in date_patterns:
        for match in re.finditer(pattern, text):
            try:
                candidate = datetime.strptime(match.group(1), fmt).date()
                if candidate > date.today():
                    return candidate
            except ValueError:
                continue
    return None