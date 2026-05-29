"""
Truck/goods_classification/prohibited.py
==========================================
Prohibited goods detection using YOLOv8 nano.
 
YOLOv8n is trained on COCO (80 classes). We flag items that
suggest dangerous, prohibited, or hazardous goods.
 
IMPORTANT: COCO doesn't include firearms as a class.
We use a two-track approach:
  Track 1: Direct YOLO COCO class matches (knife, scissors)
  Track 2: CLIP-based check for firearm/weapon-related content
 
On first run, yolov8n.pt (~6MB) is downloaded to Ultralytics cache.
"""
 
import logging
from functools import lru_cache
from PIL import Image
 
from .categories import (
    YOLO_SUSPICIOUS_CLASS_IDS,
    PROHIBITED_CONFIDENCE_THRESHOLD,
)
 
logger = logging.getLogger(__name__)
 
# Extra CLIP prompts for weapons/prohibited items not in COCO
WEAPON_CLIP_PROMPTS = [
    'a photo of a firearm, gun, pistol, or rifle',
    'a photo of explosives, bombs, or grenades',
    'a photo of illegal drugs or controlled substances',
    'a photo of hazardous chemicals or toxic materials',
    'a photo of a knife, blade, or sharp weapon',
    'a photo of household items or food or clothing',   # negative anchor
]
WEAPON_PROMPT_LABELS = [
    'Firearm / weapon',
    'Explosive / bomb',
    'Illegal drugs / narcotics',
    'Hazardous chemicals',
    'Sharp weapon / knife',
    None,   # negative — not prohibited
]
# Confidence threshold for CLIP weapon detection (higher than YOLO because
# CLIP context is broad — don't want to flag kitchen knives in food photos)
CLIP_WEAPON_THRESHOLD = 0.40
 
 
# ── YOLOv8 loader ────────────────────────────────────────────────────────────
 
@lru_cache(maxsize=1)
def _get_yolo():
    logger.info("Loading YOLOv8n model for prohibited goods detection...")
    from ultralytics import YOLO
    model = YOLO('yolov8n.pt')   # ~6MB, downloads once
    logger.info("YOLOv8n loaded")
    return model
 
 
# ── Main detection function ───────────────────────────────────────────────────
 
def detect_prohibited(pil_image: Image.Image) -> dict:
    """
    Runs prohibited goods detection on a PIL image.
 
    Two-track detection:
      1. YOLOv8 object detection (knives, scissors via COCO)
      2. CLIP zero-shot check for weapons, drugs, explosives
 
    Args:
        pil_image: PIL.Image in RGB mode, 224×224
 
    Returns:
        {
            'prohibited_detected': bool,
            'items':               [{'item': str, 'confidence': float, 'source': str}],
            'reason':              str (human-readable reason for flag),
            'error':               str or None,
        }
    """
    detected_items = []
 
    # ── Track 1: YOLOv8 COCO detection ───────────────────────────────────
    try:
        yolo = _get_yolo()
        results = yolo(pil_image, conf=PROHIBITED_CONFIDENCE_THRESHOLD, verbose=False)
 
        for result in results:
            for box in result.boxes:
                cls_id   = int(box.cls[0])
                cls_name = result.names[cls_id].lower()
                conf     = float(box.conf[0])
 
                if cls_id in YOLO_SUSPICIOUS_CLASS_IDS:
                    detected_items.append({
                        'item':       cls_name.capitalize(),
                        'confidence': round(conf, 3),
                        'source':     'object_detection',
                    })
                    logger.warning("YOLO prohibited: %s (%.1f%%)", cls_name, conf * 100)
 
    except Exception as exc:
        logger.warning("YOLOv8 detection error (non-fatal): %s", exc)
 
    # ── Track 2: CLIP weapon check ────────────────────────────────────────
    try:
        import torch
        from transformers import CLIPModel, CLIPProcessor
 
        # Reuse cached CLIP model from classifier if available
        try:
            from .classifier import _get_clip
            model, processor = _get_clip()
        except Exception:
            logger.debug("CLIP not yet loaded — skipping weapon check")
            model = processor = None
 
        if model and processor:
            inputs = processor(
                text=WEAPON_CLIP_PROMPTS,
                images=pil_image,
                return_tensors='pt',
                padding=True,
                truncation=True,
            )
            with torch.no_grad():
                outputs = model(**inputs)
 
            probs = outputs.logits_per_image[0].softmax(dim=0)
 
            for i, (prompt_lbl, prob) in enumerate(zip(WEAPON_PROMPT_LABELS, probs)):
                if prompt_lbl is None:
                    continue    # negative anchor
                if float(prob) >= CLIP_WEAPON_THRESHOLD:
                    # Check it's not already flagged by YOLO
                    already_flagged = any(
                        d['item'].lower() in prompt_lbl.lower()
                        for d in detected_items
                    )
                    if not already_flagged:
                        detected_items.append({
                            'item':       prompt_lbl,
                            'confidence': round(float(prob), 3),
                            'source':     'clip_weapon_check',
                        })
                        logger.warning(
                            "CLIP weapon detected: %s (%.1f%%)",
                            prompt_lbl, float(prob) * 100
                        )
 
    except Exception as exc:
        logger.warning("CLIP weapon check error (non-fatal): %s", exc)
 
    prohibited = len(detected_items) > 0
    reason = ''
    if prohibited:
        item_names = [d['item'] for d in detected_items]
        reason = (
            f"Potentially prohibited item(s) detected: {', '.join(item_names)}. "
            f"An admin will review your job before it is processed. "
            f"If this is a false detection, admin can clear the flag."
        )
 
    return {
        'prohibited_detected': prohibited,
        'items':               detected_items,
        'reason':              reason,
        'error':               None,
    }