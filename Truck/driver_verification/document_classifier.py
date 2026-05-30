"""
Lightweight document classifier to detect Georgia driver's licenses.
This module performs quick visual heuristics (aspect ratio, edge/card detection)
and a keyword scan using PaddleOCR to verify presence of typical license fields
(e.g. GEORGIA, DRIVER, LICENSE, DL, EXP). Designed to be fast and to run
before the heavier OCR parsing step.
"""
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


def _try_get_paddle_ocr():
    try:
        from paddleocr import PaddleOCR
        return PaddleOCR(use_angle_cls=False, lang='en', use_gpu=False, show_log=False)
    except Exception:
        return None


def classify_document(image_path: str) -> Tuple[bool, float, str]:
    """
    Returns (is_license, confidence, reason).
    confidence: 0.0 - 1.0
    reason: human-readable short description when rejecting
    """
    try:
        import cv2
        import numpy as np
    except Exception as exc:
        logger.error("OpenCV not available: %s", exc)
        return False, 0.0, "Server missing OpenCV dependency"

    # Read image
    img = cv2.imread(image_path)
    if img is None:
        return False, 0.0, "Could not read uploaded image."

    h, w = img.shape[:2]
    aspect = w / float(h) if h else 0

    # Heuristic 1: reasonable card aspect ratio for ID (approx 1.2 - 2.5 — permissive)
    if not (1.0 <= aspect <= 3.0):
        # not definitive — keep low confidence
        return False, 0.1, f"Unexpected aspect ratio ({aspect:.2f}) for an ID card."

    # Heuristic 2: detect large rectangular contour (card-like)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    img_area = h * w
    large_rect_found = False
    for c in contours:
        area = cv2.contourArea(c)
        if area < img_area * 0.05:
            continue
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            # likely a rectangle
            large_rect_found = True
            break

    # Note: edge detection can fail on some photos; allow pass-through if other heuristics OK
    if not large_rect_found:
        logger.debug("No prominent rectangular region found in image.")

    # Heuristic 3: light background proportion (licenses often have light card backgrounds)
    try:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        v = hsv[:, :, 2]
        light_frac = float((v > 150).sum()) / (img_area)
        # Permissive: just log if too dark, don't auto-reject
        if light_frac < 0.1:
            logger.debug("Image has low light proportion (%.2f); may be difficult to read.", light_frac)
    except Exception:
        # non-fatal
        light_frac = 0.5  # neutral default

    # Heuristic 4: Text-keyword scan via PaddleOCR
    ocr = _try_get_paddle_ocr()
    keyword_score = 0.0
    if ocr is not None:
        try:
            res = ocr.ocr(image_path, cls=False)
            texts = []
            # result format varies; flatten
            for line in res:
                for item in line:
                    if isinstance(item, (list, tuple)) and item:
                        texts.append(str(item[1][0]).upper())
                    elif isinstance(item, str):
                        texts.append(item.upper())

            joined = " ".join(texts)
            # keywords typical of Georgia driver's license
            keywords = ['GEORGIA', "DRIVER'S LICENSE", 'DRIVER', 'LICENSE', 'DL', 'EXP', 'EXPIR', 'DOB', 'DATE OF BIRTH', 'CLASS', 'ENDORSEMENT']
            hits = sum(1 for k in keywords if k in joined)
            # Permissive: even 1 keyword gives some score
            if hits >= 1:
                keyword_score = min(1.0, hits / len(keywords))
            else:
                keyword_score = 0.0
        except Exception as exc:
            logger.debug("PaddleOCR quick-scan failed: %s", exc)
            keyword_score = 0.0
    else:
        logger.debug("PaddleOCR not available for keyword scan; skipping text checks.")

    # Combine heuristics into final confidence — permissive, allow OCR to do heavy lifting
    base_conf = 0.3  # lowered from 0.5
    if aspect >= 1.0 and aspect <= 3.0:
        base_conf += 0.2  # aspect OK
    if large_rect_found:
        base_conf += 0.2
    if light_frac >= 0.1:
        base_conf += 0.1
    final_conf = base_conf + (keyword_score * 0.3)
    final_conf = max(0.0, min(1.0, final_conf))

    # Lower threshold to let OCR decide; classifier is just a sanity check
    if final_conf < 0.25:
        return False, final_conf, "Uploaded image does not appear to be a document (unreadable or too small)."

    return True, final_conf, ""