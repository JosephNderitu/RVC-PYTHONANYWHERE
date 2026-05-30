"""
Face verification using InsightFace (buffalo_l model, ONNX runtime).
Compares the face on the license photo against the courier's selfie.
No TensorFlow dependency. Runs on CPU via onnxruntime.
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Cosine similarity threshold: >= 0.4 is a match (InsightFace scale, not distance)
SIMILARITY_THRESHOLD = 0.40

_face_app = None


def _get_face_app():
    """Lazy-load InsightFace app. Model pre-downloaded at Docker build time."""
    global _face_app
    if _face_app is None:
        from insightface.app import FaceAnalysis  # deferred import
        _face_app = FaceAnalysis(
            name='buffalo_l',
            providers=['CPUExecutionProvider'],
        )
        _face_app.prepare(ctx_id=-1, det_size=(640, 640))
        logger.info("InsightFace buffalo_l model loaded.")
    return _face_app


@dataclass
class FaceVerificationResult:
    verified: bool
    similarity: float          # 0.0–1.0; higher = more similar
    confidence: float          # normalised 0.0–1.0 for scoring
    error: str = ""


def _load_image(path: str) -> Optional[np.ndarray]:
    img = cv2.imread(path)
    if img is None:
        logger.error("Could not read image at path: %s", path)
        return None
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def _extract_embedding(app, image: np.ndarray, label: str) -> Optional[np.ndarray]:
    """Detect faces and return the embedding of the largest detected face."""
    faces = app.get(image)
    if not faces:
        logger.warning("No face detected in %s image.", label)
        return None
    # Use the face with the largest bounding box if multiple detected
    largest = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    return largest.normed_embedding


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two L2-normalised embeddings."""
    return float(np.dot(a, b))


def verify_faces(license_image_path: str, selfie_image_path: str) -> FaceVerificationResult:
    """
    Compare the face on the license against the courier's selfie.
    Returns FaceVerificationResult with similarity score and match status.
    """
    try:
        app = _get_face_app()

        license_img = _load_image(license_image_path)
        selfie_img  = _load_image(selfie_image_path)

        if license_img is None:
            return FaceVerificationResult(False, 0.0, 0.0, error="Could not load license image.")
        if selfie_img is None:
            return FaceVerificationResult(False, 0.0, 0.0, error="Could not load selfie image.")

        license_emb = _extract_embedding(app, license_img, "license")
        selfie_emb  = _extract_embedding(app, selfie_img,  "selfie")

        if license_emb is None:
            return FaceVerificationResult(False, 0.0, 0.0, error="No face detected in license photo.")
        if selfie_emb is None:
            return FaceVerificationResult(False, 0.0, 0.0, error="No face detected in selfie photo.")

        similarity = _cosine_similarity(license_emb, selfie_emb)
        # Clamp to [0, 1] — cosine on normed embeddings can slightly exceed bounds
        similarity = float(np.clip(similarity, 0.0, 1.0))
        verified   = similarity >= SIMILARITY_THRESHOLD
        confidence = round(similarity, 4)

        logger.info(
            "Face verification | verified=%s | similarity=%.4f | threshold=%.2f",
            verified, similarity, SIMILARITY_THRESHOLD,
        )
        return FaceVerificationResult(verified=verified, similarity=similarity, confidence=confidence)

    except Exception as exc:
        logger.error("Face verification exception: %s", exc, exc_info=True)
        return FaceVerificationResult(False, 0.0, 0.0, error=str(exc))