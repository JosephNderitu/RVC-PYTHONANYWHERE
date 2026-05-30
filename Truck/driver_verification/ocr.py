"""
OCR extraction from licence images using PaddleOCR.

Key design decisions:
- Confidence threshold lowered to 0.35 — card background graphics reduce
  OCR confidence even on clearly printed text.
- Date extraction is POSITION-AWARE: we map every date's character position
  to its nearest keyword (EXP, ISS, DOB etc.) rather than assuming the label
  always precedes the value. On many US licences the value prints to the
  right of the label so OCR column-order can put the date before the keyword
  in the joined text string.
- Licence number extraction handles "DL NO. 123456789" (with NO. prefix)
  and pure-numeric numbers (e.g. Tennessee 9-digit numbers).
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
        from paddleocr import PaddleOCR
        _ocr_engine = PaddleOCR(
            use_angle_cls=True,
            lang='en',
            use_gpu=False,
            show_log=False,
        )
    return _ocr_engine


def extract_license_text(image_path: str) -> list[str]:
    """
    Run PaddleOCR on the licence image.
    Returns a flat list of detected text strings.
    Threshold lowered to 0.35 to capture text on graphically busy backgrounds.
    """
    engine = _get_engine()
    result = engine.ocr(image_path, cls=True)

    lines: list[str] = []
    if not result or not result[0]:
        logger.warning("PaddleOCR returned no results for %s", image_path)
        return lines

    for line in result[0]:
        text, confidence = line[1][0], line[1][1]
        if confidence >= 0.35:
            lines.append(text.strip())

    logger.debug("OCR extracted %d lines from %s: %s", len(lines), image_path, lines)
    return lines


def parse_license_data(lines: list[str]) -> dict:
    """
    Parse OCR text lines into structured licence fields.
    Returns: {license_number, license_class, expiry_date}
    All values are None when not detected.
    """
    text_block = " ".join(lines).upper()

    result = {
        "license_number": _extract_license_number(text_block),
        "license_class":  _extract_license_class(text_block),
        "expiry_date":    _extract_expiry_date(text_block),
    }
    logger.debug(
        "Parsed licence data | number=%s | class=%s | expiry=%s",
        result["license_number"], result["license_class"], result["expiry_date"],
    )
    return result


# ── Date patterns (shared) ──────────────────────────────────────────────────
_DATE_RE_FORMATS = [
    (r'\b(\d{2}/\d{2}/\d{4})\b', '%m/%d/%Y'),   # 06/01/2032  (US standard)
    (r'\b(\d{2}-\d{2}-\d{4})\b', '%m-%d-%Y'),   # 06-01-2032
    (r'\b(\d{4}-\d{2}-\d{2})\b', '%Y-%m-%d'),   # 2032-06-01
    (r'\b(\d{2}/\d{2}/\d{2})\b', '%m/%d/%y'),   # 06/01/32  (2-digit year)
    (r'\b(\d{2}/\d{4})\b',       '%m/%Y'),      # 06/2032   (no day)
]

# Keywords indicating expiry
_EXP_KEYWORDS = (
    'VALID THROUGH', 'VALID THRU', 'EXPIRY', 'EXPIRES', 'EXPIR', 'EXPIRE', 'EXP',
)
# Keywords to EXCLUDE from expiry matching
_EXCL_KEYWORDS = (
    'DATE OF BIRTH', 'BORN', 'DOB', 'ISSUED', 'ISSUE', 'ISS',
)


def _all_dates_in_text(text: str) -> dict:
    """
    Return a dict of {character_position: date} for every date in text.
    Tries all format patterns; skips implausible dates (before year 2000).
    """
    found: dict[int, date] = {}
    for pattern, fmt in _DATE_RE_FORMATS:
        for m in re.finditer(pattern, text):
            if m.start() in found:
                continue  # already claimed by an earlier, higher-priority pattern
            try:
                d = datetime.strptime(m.group(1), fmt).date()
                if d.year >= 2000:
                    found[m.start()] = d
            except ValueError:
                pass
    return found


def _keyword_positions(text: str, keywords: tuple) -> list[tuple[int, str]]:
    """Return [(position, keyword)] for all occurrences of every keyword."""
    positions = []
    for kw in keywords:
        idx = 0
        while True:
            idx = text.find(kw, idx)
            if idx == -1:
                break
            positions.append((idx, kw))
            idx += len(kw)
    return positions


def _extract_expiry_date(text: str) -> Optional[date]:
    """
    Position-aware expiry date extraction.

    Strategy:
    1. Map every date in the text to its character position.
    2. Map every EXP and EXCL keyword to its character position.
    3. For each date, find the nearest keyword within 60 chars (before or after).
    4. Dates nearest an EXP keyword → expiry candidates.
    5. Dates nearest an EXCL keyword → excluded.
    6. Return the best expiry candidate that is a future date.
    7. Fallback: any future date not flagged as excluded.
    """
    all_dates = _all_dates_in_text(text)
    if not all_dates:
        return None

    exp_kw_pos  = _keyword_positions(text, _EXP_KEYWORDS)
    excl_kw_pos = _keyword_positions(text, _EXCL_KEYWORDS)
    all_kw_pos  = exp_kw_pos + excl_kw_pos

    WINDOW = 60  # chars to search around each keyword

    def nearest_keyword(date_pos: int):
        """Return (distance, keyword) of the closest keyword, or None."""
        best = None
        best_dist = WINDOW + 1
        for kw_pos, kw in all_kw_pos:
            dist = abs(date_pos - kw_pos)
            if dist < best_dist:
                best_dist = dist
                best = (dist, kw)
        return best

    exp_candidates:  list[tuple[int, date]] = []
    excl_positions:  set[int]               = set()

    for date_pos, d in all_dates.items():
        nearest = nearest_keyword(date_pos)
        if nearest is None:
            continue
        _, kw = nearest
        if kw in _EXCL_KEYWORDS:
            excl_positions.add(date_pos)
        elif kw in _EXP_KEYWORDS:
            exp_candidates.append((date_pos, d))

    today = date.today()

    # Step 1 — Return a future date nearest an EXP keyword
    future_exp = [(pos, d) for pos, d in exp_candidates if d > today]
    if future_exp:
        # Return the one with the highest year (most likely the far-future expiry)
        return max(future_exp, key=lambda x: x[1])[1]

    # Step 2 — Fallback: any future date not excluded
    for pos in sorted(all_dates.keys()):
        if pos not in excl_positions:
            d = all_dates[pos]
            if d > today:
                logger.debug(
                    "Expiry fallback: using date %s at pos %d (no EXP keyword nearby)",
                    d, pos,
                )
                return d

    return None


def _extract_license_number(text: str) -> Optional[str]:
    """
    Extract the DL number from OCR text.

    Handles:
    - "DL NO. 123456789"   (Tennessee, many US states)
    - "DL# 123456789"
    - "DL 123456789"
    - "LICENSE 123456789"
    - "NO. 123456789"
    - "GA123456789"        (state-prefix format)
    - "123456789"          (pure numeric — last resort, context-filtered)
    """
    patterns = [
        # Explicit "DL NO." variants — highest priority
        r'\bDL\s*NO[.:\s]+([A-Z0-9]{6,15})\b',
        # Generic DL prefix
        r'\bDL[#:\-\s]+([A-Z0-9]{6,15})\b',
        # DRIVER LICENCE / LICENSE prefix
        r'\bDRIVER(?:\'?S)?\s+LIC(?:ENSE)?[#:\s]+([A-Z0-9]{6,15})\b',
        # LICENSE alone
        r'\bLIC(?:ENSE)?[#:\s]+([A-Z0-9]{6,15})\b',
        # "NO." label
        r'\bNO[.:\s]+([A-Z0-9]{6,15})\b',
        # State-prefix alphanumeric (e.g. GA1234567, TX123456)
        r'\b([A-Z]{1,3}[0-9]{5,12})\b',
        # DD (document discriminator) — fallback only
        r'\bDD\s+([A-Z0-9]{12,})\b',
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            result = match.group(1).strip()
            # Reject: too short, or looks like a year, or all same char
            if (
                len(result) >= 6
                and not re.match(r'^(19|20)\d{2}$', result)
                and len(set(result)) > 2
            ):
                logger.debug("Licence number matched pattern '%s': %s", pattern, result)
                return result

    # Last resort: standalone 7-12 digit number that isn't part of a date
    date_digits = set()
    for m in re.finditer(r'\b(\d{2}/\d{2}/\d{4})\b', text):
        date_digits.update(m.group(1).replace('/', '').split())
    # Also exclude year-like numbers and short segments
    for m in re.finditer(r'\b(\d{7,12})\b', text):
        num = m.group(1)
        if (
            num not in date_digits
            and not re.match(r'^(19|20)\d{2}', num)
            and len(set(num)) > 1      # not all same digit
        ):
            logger.debug("Licence number fallback (pure numeric): %s", num)
            return num

    return None


def _extract_license_class(text: str) -> Optional[str]:
    """Extract the licence class (A, B, C, D, CDL-A, etc.)."""
    # "CLASS D", "CLASS A", "CLASS CDL", etc.
    match = re.search(r'\bCLASS[:\s]+([A-E](?:DL)?)\b', text)
    if match:
        return match.group(1)

    # CDL variants printed separately
    for cls in ('CDL-A', 'CDL-B', 'CDL-C', 'CLASS A', 'CLASS B', 'CLASS C', 'CLASS D'):
        if cls in text:
            return cls.replace('CLASS ', '')

    return None