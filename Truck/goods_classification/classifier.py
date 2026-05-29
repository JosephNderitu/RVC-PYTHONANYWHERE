"""
Truck/goods_classification/classifier.py
==========================================
CLIP zero-shot goods classification engine.

Uses openai/clip-vit-base-patch32 loaded via HuggingFace transformers.
Model is loaded once per Celery worker process via @lru_cache.

First call downloads ~600MB of model weights to ~/.cache/huggingface/
(or wherever HF_HOME is set). Subsequent calls use the cache.

CPU inference time: ~2–5 seconds per image on a modern CPU.
"""

import logging
import torch
from functools import lru_cache
from PIL import Image

from .categories import (
    CATEGORY_DEFINITIONS,
    CATEGORY_SLUGS,
    LOW_CONFIDENCE_THRESHOLD,
)

logger = logging.getLogger(__name__)


# ── Model loader (cached per process) ────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_clip():
    """
    Loads CLIP model and processor exactly once per Celery worker process.
    Thread-safe via Python's GIL — only one load even under concurrent tasks.

    Returns:
        (CLIPModel, CLIPProcessor) tuple
    """
    logger.info("Loading CLIP model openai/clip-vit-base-patch32 ...")
    from transformers import CLIPModel, CLIPProcessor

    model_name = "openai/clip-vit-base-patch32"
    processor  = CLIPProcessor.from_pretrained(model_name)
    model      = CLIPModel.from_pretrained(model_name)
    model.eval()

    logger.info("CLIP model loaded successfully")
    return model, processor


# ── Build text prompts ────────────────────────────────────────────────────────

def _build_prompt_matrix():
    """
    Builds a matrix of prompts for multi-prompt classification.

    Returns:
        prompts_per_category: list of lists, one inner list per category
        flat_prompts:         flat list of all prompts (for batch CLIP call)
        prompt_to_cat_idx:    maps flat index → category index
    """
    prompts_per_category = [
        CATEGORY_DEFINITIONS[slug]['clip_prompts']
        for slug in CATEGORY_SLUGS
    ]
    flat_prompts = []
    prompt_to_cat_idx = []

    for cat_idx, prompts in enumerate(prompts_per_category):
        for prompt in prompts:
            flat_prompts.append(prompt)
            prompt_to_cat_idx.append(cat_idx)

    return prompts_per_category, flat_prompts, prompt_to_cat_idx


# ── Core classification ───────────────────────────────────────────────────────

def classify_image(pil_image: Image.Image) -> dict:
    """
    Classifies a PIL image using CLIP zero-shot inference.

    Strategy:
      1. Run all prompts from all categories in one batch
      2. Average similarity scores across prompts per category
      3. Softmax → probability per category
      4. Return top category + confidence + all scores

    Args:
        pil_image: PIL.Image.Image, already preprocessed to 224×224 RGB

    Returns:
        {
            'success':        bool,
            'category_slug':  str  (e.g. 'electronics'),
            'category_name':  str  (e.g. 'Electronics'),
            'confidence':     float (0.0–1.0),
            'low_confidence': bool,
            'item_name':      str,
            'all_scores':     {slug: score, ...},
            'top_3':          [(slug, score), ...],
            'error':          str or None,
        }
    """
    try:
        model, processor = _get_clip()

        _, flat_prompts, prompt_to_cat_idx = _build_prompt_matrix()

        # Tokenise all text prompts and process the image
        inputs = processor(
            text=flat_prompts,
            images=pil_image,
            return_tensors='pt',
            padding=True,
            truncation=True,
        )

        with torch.no_grad():
            outputs = model(**inputs)

        # logits_per_image: shape [1, num_prompts]
        logits = outputs.logits_per_image[0]   # shape [num_prompts]

        # Average logits per category (handles different prompt counts)
        num_cats = len(CATEGORY_SLUGS)
        cat_scores = torch.zeros(num_cats)
        cat_counts = torch.zeros(num_cats)

        for prompt_idx, cat_idx in enumerate(prompt_to_cat_idx):
            cat_scores[cat_idx] += logits[prompt_idx]
            cat_counts[cat_idx] += 1

        cat_scores = cat_scores / cat_counts.clamp(min=1)

        # Softmax to get probabilities
        probs = cat_scores.softmax(dim=0)

        # Build result dict
        all_scores = {
            CATEGORY_SLUGS[i]: float(probs[i])
            for i in range(num_cats)
        }

        sorted_cats = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
        top_slug, top_conf = sorted_cats[0]
        top_3 = sorted_cats[:3]

        cat_def      = CATEGORY_DEFINITIONS[top_slug]
        is_low_conf  = top_conf < LOW_CONFIDENCE_THRESHOLD

        # Item name suggestion from top category
        item_name = _suggest_item_name(pil_image, top_slug, processor, model)

        logger.info(
            "CLIP classification: %s (%.1f%%) | low_conf=%s",
            top_slug, top_conf * 100, is_low_conf
        )

        return {
            'success':        True,
            'category_slug':  top_slug,
            'category_name':  cat_def['name'],
            'confidence':     round(top_conf, 4),
            'low_confidence': is_low_conf,
            'item_name':      item_name,
            'all_scores':     {k: round(v, 4) for k, v in all_scores.items()},
            'top_3':          [(s, round(c, 4)) for s, c in top_3],
            'error':          None,
        }

    except Exception as exc:
        logger.error("CLIP classification error: %s", exc, exc_info=True)
        return {
            'success':        False,
            'category_slug':  'general',
            'category_name':  'General Cargo',
            'confidence':     0.0,
            'low_confidence': True,
            'item_name':      '',
            'all_scores':     {},
            'top_3':          [],
            'error':          str(exc),
        }


def _suggest_item_name(pil_image, top_slug, processor, model) -> str:
    """
    Uses CLIP to suggest a specific item name within the top category.
    Uses a curated list of common item names per category.

    Returns a string like "Laptop Computer" or "" if unclear.
    """
    ITEM_NAMES = {
        'electronics': [
            'a laptop computer', 'a smartphone', 'a tablet',
            'a television', 'a desktop computer', 'a camera',
            'a gaming console', 'headphones', 'a printer', 'a monitor',
        ],
        'furniture': [
            'an office chair', 'a dining table', 'a sofa', 'a bed',
            'a bookshelf', 'a wardrobe', 'a desk', 'a coffee table',
            'a cabinet', 'a chest of drawers',
        ],
        'documents': [
            'documents', 'books', 'a folder of papers',
            'an envelope', 'a binder', 'certificates',
        ],
        'food': [
            'groceries', 'packaged food', 'fresh produce',
            'beverages', 'a meal or takeout', 'snacks',
        ],
        'clothing': [
            'clothes', 'shoes', 'a handbag', 'a backpack',
            'sports clothing', 'formal wear',
        ],
        'medical': [
            'medicine', 'a first aid kit', 'medical equipment',
            'a wheelchair', 'medical supplies',
        ],
        'construction': [
            'building materials', 'lumber or wood', 'pipes',
            'bags of cement', 'tiles', 'hardware tools',
        ],
        'automotive': [
            'a car tyre', 'engine parts', 'a car battery',
            'automotive tools', 'vehicle accessories',
        ],
        'artwork': [
            'a painting', 'a musical instrument', 'a sculpture',
            'framed artwork', 'a decorative vase', 'antiques',
        ],
        'general': [
            'a cardboard box', 'household items', 'a package',
            'mixed goods', 'wrapped items',
        ],
    }

    item_list = ITEM_NAMES.get(top_slug, ITEM_NAMES['general'])
    item_texts = [f'a photo of {item}' for item in item_list]

    try:
        inputs = processor(
            text=item_texts,
            images=pil_image,
            return_tensors='pt',
            padding=True,
            truncation=True,
        )
        with torch.no_grad():
            outputs = model(**inputs)

        probs = outputs.logits_per_image[0].softmax(dim=0)
        top_idx  = int(probs.argmax())
        top_conf = float(probs[top_idx])

        if top_conf > 0.20:   # only suggest if reasonably confident
            # Convert "a photo of a laptop computer" → "Laptop Computer"
            raw = item_list[top_idx]
            name = raw.lstrip('a ').lstrip('an ').strip().title()
            return name

    except Exception as exc:
        logger.debug("Item name suggestion failed: %s", exc)

    return ''