# ================================================================
# Truck/goods_classification/fragility.py
# ================================================================
"""
Computes a fragility score based on CLIP classification results.
 
Fragility score = category base weight × confidence amplifier
Threshold ≥ 0.60 → item is fragile
"""
 
 
def compute_fragility(category_slug: str, confidence: float) -> dict:
    """
    Computes fragility score and flag.
 
    Args:
        category_slug: CLIP-detected category (e.g. 'electronics')
        confidence:    CLIP confidence for that category (0.0–1.0)
 
    Returns:
        {
            'is_fragile':      bool,
            'fragility_score': float (0.0–1.0),
            'reason':          str,
        }
    """
    from .categories import CATEGORY_DEFINITIONS, FRAGILITY_THRESHOLD
 
    cat_def = CATEGORY_DEFINITIONS.get(category_slug, CATEGORY_DEFINITIONS['general'])
    base    = cat_def['fragility_base']
 
    # Amplify base by confidence — high confidence + high base = more fragile
    # Dampen slightly for medium confidence (0.35–0.65)
    amplifier = 0.7 + 0.3 * confidence    # range: 0.7–1.0
    score     = min(base * amplifier, 1.0)
 
    is_fragile = score >= FRAGILITY_THRESHOLD
 
    reason = ''
    if is_fragile:
        reason = (
            f'{cat_def["name"]} items are typically fragile and require '
            f'careful handling. Your item will be marked for extra care.'
        )
 
    return {
        'is_fragile':      is_fragile,
        'fragility_score': round(score, 3),
        'reason':          reason,
    }