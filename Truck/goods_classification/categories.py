"""
Truck/goods_classification/categories.py
=========================================
Static category definitions for RVC goods classification.

These map directly to the Category model (slug field).
The CLIP_PROMPTS list is what gets sent to the CLIP model for zero-shot
classification — more specific and varied prompts = better accuracy.

IMPORTANT: Do NOT change slugs after seeding — existing jobs reference them.
"""

# ── Category definitions ─────────────────────────────────────────────────────
#
# Each entry:
#   name           → display name (matches Category.name in DB)
#   clip_prompts   → list of natural language descriptions for CLIP
#                    (more prompts = better coverage, averaged per category)
#   default_size   → suggested size for this category
#   size_options   → valid size choices for this type of item
#   fragility_base → base fragility score 0.0–1.0 (CLIP confidence amplifies this)
#   description    → shown to customer when suggestion is accepted

CATEGORY_DEFINITIONS = {
    'electronics': {
        'name': 'Electronics',
        'clip_prompts': [
            'a photo of a laptop computer or notebook',
            'a photo of a smartphone or tablet device',
            'a photo of a television screen or computer monitor',
            'a photo of electronic equipment or circuit boards',
            'a photo of a camera or audio speaker or headphones',
            'a photo of a gaming console or electronic gadget',
        ],
        'default_size': 'small',
        'size_options': ['small', 'medium'],
        'fragility_base': 0.85,
        'description': 'Laptops, phones, TVs, cameras, audio equipment',
    },
    'furniture': {
        'name': 'Furniture',
        'clip_prompts': [
            'a photo of a chair or armchair or office chair',
            'a photo of a sofa or couch or loveseat',
            'a photo of a dining table or coffee table or desk',
            'a photo of a bed frame or headboard',
            'a photo of a bookshelf or cabinet or wardrobe',
            'a photo of furniture or home furnishings',
        ],
        'default_size': 'large',
        'size_options': ['medium', 'large'],
        'fragility_base': 0.30,
        'description': 'Chairs, tables, sofas, beds, shelves',
    },
    'documents': {
        'name': 'Documents & Files',
        'clip_prompts': [
            'a photo of papers or documents or files',
            'a photo of a folder or binder or envelope',
            'a photo of books or textbooks or manuals',
            'a photo of printed materials or paperwork',
            'a photo of legal documents or certificates',
        ],
        'default_size': 'small',
        'size_options': ['small'],
        'fragility_base': 0.10,
        'description': 'Papers, books, folders, envelopes, legal documents',
    },
    'food': {
        'name': 'Food & Perishables',
        'clip_prompts': [
            'a photo of food or groceries or produce',
            'a photo of packaged food or snacks or beverages',
            'a photo of fruits or vegetables or fresh food',
            'a photo of a meal or takeout container or food box',
            'a photo of perishable goods or refrigerated items',
        ],
        'default_size': 'small',
        'size_options': ['small', 'medium'],
        'fragility_base': 0.50,
        'description': 'Groceries, produce, packaged food, beverages',
    },
    'clothing': {
        'name': 'Clothing & Textiles',
        'clip_prompts': [
            'a photo of clothes or garments or apparel',
            'a photo of shoes or footwear or boots',
            'a photo of a bag or handbag or backpack',
            'a photo of fabric or textile or linen',
            'a photo of folded clothes or a clothing bundle',
        ],
        'default_size': 'small',
        'size_options': ['small', 'medium'],
        'fragility_base': 0.05,
        'description': 'Clothes, shoes, bags, fabric, textiles',
    },
    'medical': {
        'name': 'Medical Supplies',
        'clip_prompts': [
            'a photo of medicine or pharmaceutical drugs',
            'a photo of medical equipment or first aid kit',
            'a photo of surgical tools or medical devices',
            'a photo of a wheelchair or medical mobility aid',
            'a photo of a pharmacy or medical supplies box',
        ],
        'default_size': 'small',
        'size_options': ['small', 'medium'],
        'fragility_base': 0.75,
        'description': 'Medicine, medical devices, first aid, mobility aids',
    },
    'construction': {
        'name': 'Construction Materials',
        'clip_prompts': [
            'a photo of construction materials like bricks or lumber',
            'a photo of pipes or metal beams or steel rods',
            'a photo of bags of cement or sand or gravel',
            'a photo of tiles or flooring materials',
            'a photo of building supplies or hardware materials',
        ],
        'default_size': 'large',
        'size_options': ['medium', 'large'],
        'fragility_base': 0.10,
        'description': 'Bricks, lumber, pipes, cement, building hardware',
    },
    'automotive': {
        'name': 'Automotive Parts',
        'clip_prompts': [
            'a photo of a car tyre or wheel or rim',
            'a photo of engine parts or car components',
            'a photo of a car battery or alternator',
            'a photo of automotive accessories or tools',
            'a photo of vehicle spare parts or mechanical components',
        ],
        'default_size': 'medium',
        'size_options': ['small', 'medium', 'large'],
        'fragility_base': 0.20,
        'description': 'Tyres, engine parts, batteries, car accessories',
    },
    'artwork': {
        'name': 'Artwork & Instruments',
        'clip_prompts': [
            'a photo of a painting or canvas artwork or sculpture',
            'a photo of a musical instrument like a guitar or violin',
            'a photo of framed art or decorative items',
            'a photo of antique or collectible items',
            'a photo of a vase or decorative glass or ceramic',
        ],
        'default_size': 'medium',
        'size_options': ['small', 'medium', 'large'],
        'fragility_base': 0.90,
        'description': 'Paintings, sculptures, instruments, antiques, ceramics',
    },
    'general': {
        'name': 'General Cargo',
        'clip_prompts': [
            'a photo of a cardboard box or package or parcel',
            'a photo of household items or miscellaneous goods',
            'a photo of wrapped goods or a shipping box',
            'a photo of general merchandise or mixed items',
            'a photo of a storage container or packed goods',
        ],
        'default_size': 'medium',
        'size_options': ['small', 'medium', 'large'],
        'fragility_base': 0.25,
        'description': 'Boxes, packages, household items, general merchandise',
    },
}

# ── Ordered list of slugs (used to align CLIP output indices) ────────────────
CATEGORY_SLUGS = list(CATEGORY_DEFINITIONS.keys())

# ── All CLIP prompts in order (flattened, one representative per category) ───
# We use the FIRST prompt as the primary representative for fast single-pass
# classification. The full list is used in the detailed multi-prompt pass.
CATEGORY_REPRESENTATIVE_PROMPTS = [
    CATEGORY_DEFINITIONS[slug]['clip_prompts'][0]
    for slug in CATEGORY_SLUGS
]

# ── Prohibited item YOLO labels (COCO dataset class names) ──────────────────
# These are COCO class names returned by YOLOv8 trained on COCO
YOLO_PROHIBITED_CLASSES = {
    # Class name → human-readable label shown to customer
    'knife':         'Sharp blade / knife',
    'scissors':      'Scissors',
    'gun':           'Firearm',
    'rifle':         'Rifle / firearm',
    'pistol':        'Pistol / firearm',
    'bomb':          'Explosive device',
    'grenade':       'Grenade / explosive',
    # Note: COCO doesn't have a 'gun' class directly.
    # We also flag based on context (see prohibited.py for extra heuristics).
}

# COCO numeric class IDs that are suspicious/prohibited
YOLO_SUSPICIOUS_CLASS_IDS = {
    43,   # knife
    76,   # scissors
    # COCO doesn't include firearms — extra model or heuristic needed
}

# Confidence threshold for prohibited detection — intentionally low
# to err on the side of caution (admin can clear false positives)
PROHIBITED_CONFIDENCE_THRESHOLD = 0.25

# ── Classification thresholds ────────────────────────────────────────────────
# Below this confidence → show "Unable to classify" + manual entry
LOW_CONFIDENCE_THRESHOLD = 0.35

# Above this fragility score → show fragile warning
FRAGILITY_THRESHOLD = 0.60