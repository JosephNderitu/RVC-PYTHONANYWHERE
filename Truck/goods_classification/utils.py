"""
Truck/goods_classification/utils.py
=====================================
Image validation and preprocessing utilities.

- Max file size: 20 MB
- Resize to 224×224 before classification (CLIP input size)
- Convert to RGB (handles PNG transparency, CMYK photos)
- Returns PIL Image ready for CLIP processor
"""

import os
import logging
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
MAX_FILE_SIZE_MB   = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
CLIP_INPUT_SIZE    = (224, 224)

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.gif'}
ALLOWED_MIME_TYPES = {
    'image/jpeg', 'image/png', 'image/webp',
    'image/bmp', 'image/tiff', 'image/gif',
}


class ImageValidationError(Exception):
    """Raised when an uploaded image fails validation."""
    pass


def validate_image_file(file_obj) -> None:
    """
    Validates an uploaded image file before processing.

    Args:
        file_obj: Django UploadedFile or file-like object

    Raises:
        ImageValidationError: with a user-friendly message
    """
    # ── Size check ────────────────────────────────────────────────────────
    file_obj.seek(0, 2)          # seek to end
    size_bytes = file_obj.tell()
    file_obj.seek(0)             # reset

    if size_bytes > MAX_FILE_SIZE_BYTES:
        size_mb = size_bytes / (1024 * 1024)
        raise ImageValidationError(
            f'Image too large ({size_mb:.1f} MB). '
            f'Maximum allowed size is {MAX_FILE_SIZE_MB} MB.'
        )

    if size_bytes == 0:
        raise ImageValidationError('Uploaded file is empty.')

    # ── Extension check ───────────────────────────────────────────────────
    name = getattr(file_obj, 'name', '')
    ext  = Path(name).suffix.lower() if name else ''
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise ImageValidationError(
            f'File type "{ext}" is not supported. '
            f'Please upload a JPEG, PNG, WebP, or BMP image.'
        )

    # ── PIL integrity check ───────────────────────────────────────────────
    try:
        img = Image.open(file_obj)
        img.verify()             # checks file integrity without loading pixels
        file_obj.seek(0)         # verify closes/invalidates, must re-open
    except UnidentifiedImageError:
        raise ImageValidationError(
            'The file does not appear to be a valid image. '
            'Please upload a JPEG, PNG, or WebP photo.'
        )
    except Exception as exc:
        raise ImageValidationError(f'Could not read image file: {exc}')


def load_and_preprocess(image_path: str) -> Image.Image:
    """
    Loads an image from disk and preprocesses it for CLIP:
      1. Open with PIL
      2. Convert to RGB (handles RGBA, CMYK, grayscale, palette modes)
      3. Resize to 224×224 using high-quality Lanczos resampling

    Args:
        image_path: absolute path to the image file

    Returns:
        PIL.Image.Image in RGB mode, 224×224 pixels

    Raises:
        ImageValidationError: if the file cannot be opened
    """
    try:
        img = Image.open(image_path)
    except FileNotFoundError:
        raise ImageValidationError(f'Image file not found: {image_path}')
    except UnidentifiedImageError:
        raise ImageValidationError(f'Cannot identify image file: {image_path}')
    except Exception as exc:
        raise ImageValidationError(f'Failed to open image: {exc}')

    # Convert to RGB — CLIP expects 3-channel images
    if img.mode != 'RGB':
        logger.debug("Converting image from %s to RGB", img.mode)
        try:
            img = img.convert('RGB')
        except Exception as exc:
            raise ImageValidationError(f'Failed to convert image to RGB: {exc}')

    # Resize to CLIP input size (224×224)
    if img.size != CLIP_INPUT_SIZE:
        img = img.resize(CLIP_INPUT_SIZE, Image.LANCZOS)

    return img


def get_image_bytes(pil_image: Image.Image, fmt: str = 'JPEG') -> bytes:
    """
    Converts a PIL image to bytes (useful for sending to external APIs).
    """
    buf = BytesIO()
    pil_image.save(buf, format=fmt, quality=90)
    return buf.getvalue()


def validate_and_preprocess(image_path: str) -> Image.Image:
    """
    Convenience function: validate file on disk then preprocess.
    Used by the Celery task.
    """
    if not os.path.exists(image_path):
        raise ImageValidationError(f'Image file does not exist: {image_path}')

    size_bytes = os.path.getsize(image_path)
    if size_bytes > MAX_FILE_SIZE_BYTES:
        raise ImageValidationError(
            f'Image file is too large ({size_bytes / 1024 / 1024:.1f} MB). '
            f'Maximum is {MAX_FILE_SIZE_MB} MB.'
        )

    return load_and_preprocess(image_path)