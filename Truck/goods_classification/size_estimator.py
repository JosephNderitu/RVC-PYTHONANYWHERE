# ================================================================
# Truck/goods_classification/size_estimator.py
# ================================================================
"""
Estimates size class (Small/Medium/Large) from category slug.
 
Mapping is based on typical real-world item dimensions for each category.
The suggestion is non-binding — customer can always change it.
"""
 
 
def estimate_size(category_slug: str, confidence: float) -> dict:
    from .categories import CATEGORY_DEFINITIONS, LOW_CONFIDENCE_THRESHOLD
 
    cat_def = CATEGORY_DEFINITIONS.get(category_slug, CATEGORY_DEFINITIONS['general'])
 
    suggested = cat_def['default_size']
    options   = cat_def['size_options']
    reliable  = confidence >= LOW_CONFIDENCE_THRESHOLD
 
    SIZE_LABELS = {
        'small':  'Small — Cargo Van (up to 150 lbs)',
        'medium': 'Medium — Box Truck (up to 5 tons)',
        'large':  'Large — Semi-Truck (up to 36 tons)',
    }
 
    reason = (
        f'{cat_def["name"]} items are typically {suggested.capitalize()} '
        f'({SIZE_LABELS.get(suggested, suggested)}). '
        f'You can change this if your item is different.'
    )
 
    if not reliable:
        reason = 'Unable to determine size from photo. Please select the appropriate size below.'
 
    return {
        'suggested_size': suggested,
        'size_options':   options,
        'reason':         reason,
        'reliable':       reliable,
    }