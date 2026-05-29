from django.utils import timezone
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.contrib.gis.db import models as gis_models
from django.contrib.gis.geos import Point
import random
import string


class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to='customer/avatars/', blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    stripe_payment_method_id = models.CharField(max_length=255, blank=True)
    stripe_card_last4 = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.user.get_full_name()


class Courier(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    location = gis_models.PointField(
        geography=True,
        srid=4326,
        null=True,
        blank=True,
        spatial_index=True,
    )
    # ── Geofencing: stores last EMA-smoothed position ──────────────────────
    # The ExponentialSmoother in Truck/geofencing/smoothing.py reads these
    # values as the "previous" smoothed position, computes the new smoothed
    # position, and writes it back here before running PiP evaluation.
    # Nullable on first GPS update (no prior value yet).
    smoothed_lat = models.FloatField(null=True, blank=True)
    smoothed_lng = models.FloatField(null=True, blank=True)
    # ───────────────────────────────────────────────────────────────────────
    paypal_email = models.EmailField(max_length=255, blank=True)
    fcm_token = models.TextField(blank=True)
    is_available = models.BooleanField(default=False)
    is_on_shift = models.BooleanField(default=False)
    # ── Courier profile ─────────────────────────────────────────────────
    avatar = models.ImageField(
        upload_to='courier/avatars/',
        blank=True, null=True,
        help_text="Courier profile photo — shown in the app and job pages."
    )
    vehicle_type = models.CharField(
        max_length=50, blank=True,
        choices=[
            ('van',        'Van'),
            ('truck',      'Truck'),
            ('pickup',     'Pickup Truck'),
            ('motorcycle', 'Motorcycle'),
            ('car',        'Car'),
        ],
        help_text="Vehicle type used for deliveries."
    )
     # ── Driver Licence Verification ──────────────────────────────────────────
    VERIFICATION_UNVERIFIED = 'unverified'
    VERIFICATION_PENDING    = 'pending'
    VERIFICATION_VERIFIED   = 'verified'
    VERIFICATION_FAILED     = 'failed'
    VERIFICATION_CHOICES    = [
        ('unverified', 'Unverified'),
        ('pending',    'Pending Review'),
        ('verified',   'Verified'),
        ('failed',     'Failed — resubmit'),
    ]
 
    verification_status   = models.CharField(
        max_length=20,
        choices=VERIFICATION_CHOICES,
        default='unverified',
        help_text="Current driver licence verification status.",
    )
    is_verified           = models.BooleanField(default=False)
    face_verified         = models.BooleanField(default=False)
 
    license_photo         = models.ImageField(
        upload_to='courier/licenses/',
        blank=True, null=True,
        help_text="Front of the courier's driver's licence.",
    )
    selfie_photo          = models.ImageField(
        upload_to='courier/selfies/',
        blank=True, null=True,
        help_text="Selfie used for face matching against the licence photo.",
    )
 
    license_number        = models.CharField(max_length=50, blank=True)
    license_class         = models.CharField(max_length=10, blank=True)
    license_expiry        = models.DateField(null=True, blank=True)
    verification_score    = models.FloatField(default=0.0)
    verification_notes    = models.TextField(blank=True)
    verification_attempts = models.IntegerField(default=0)
    verified_at           = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.user.get_full_name()

    def set_location(self, lat, lng):
        """Update courier position from raw GPS coordinates."""
        self.location = Point(lng, lat, srid=4326)   # Point(lng, lat) — not a typo
        self.save(update_fields=['location'])

    @property
    def lat(self):
        return self.location.y if self.location else 0

    @property
    def lng(self):
        return self.location.x if self.location else 0


class Category(models.Model):
    slug = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Job(models.Model):
    SMALL_SIZE = "small"
    MEDIUM_SIZE = "medium"
    LARGE_SIZE = "large"
    SIZES = (
        (SMALL_SIZE,  "Small — Cargo Van (up to 150 lbs)"),
        (MEDIUM_SIZE, "Medium — Box Truck (150 lbs to 10,000 lbs / ~5 tons)"),
        (LARGE_SIZE,  "Large — Semi-Truck (10,000 lbs to 80,000 lbs / up to 36 tons)"),
    )
    CREATING_STATUS = 'creating'
    PROCESSING_STATUS = 'processing'
    PICKING_STATUS = 'picking'
    DELIVERING_STATUS = 'delivering'
    COMPLETED_STATUS = 'completed'
    CANCELED_STATUS = 'cancel'
    STATUSES = (
        (CREATING_STATUS, "Creating..."),
        (PROCESSING_STATUS, "Processing.."),
        (PICKING_STATUS, "Picking up the item."),
        (DELIVERING_STATUS, "Delivering to customer."),
        (COMPLETED_STATUS, "Completed!"),
        (CANCELED_STATUS, "Cancelled."),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    Customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    courier = models.ForeignKey(Courier, on_delete=models.CASCADE, null=True, blank=True)
    names = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    size = models.CharField(max_length=20, choices=SIZES, default=MEDIUM_SIZE)
    quantity = models.IntegerField(default=1)
    photo = models.ImageField(upload_to='job/photo/')
    status = models.CharField(max_length=20, choices=STATUSES, default=CREATING_STATUS)
    created_at = models.DateTimeField(default=timezone.now)

    pickup_address = models.CharField(max_length=255, blank=True)
    pickup_location = gis_models.PointField(
        geography=True, srid=4326, null=True, blank=True, spatial_index=True
    )
    pickup_name = models.CharField(max_length=255, blank=True)
    pickup_phone = models.CharField(max_length=255, blank=True)

    delivery_address = models.CharField(max_length=255, blank=True)
    delivery_location = gis_models.PointField(
        geography=True, srid=4326, null=True, blank=True, spatial_index=True
    )
    delivery_name = models.CharField(max_length=255, blank=True)
    delivery_phone = models.CharField(max_length=255, blank=True)

    duration = models.IntegerField(default=0)
    distance = models.FloatField(default=0)
    price = models.FloatField(default=0)

    pickup_photo = models.ImageField(upload_to='job/pickup_photos/', null=True, blank=True)
    pickedup_at = models.DateTimeField(null=True, blank=True)

    delivery_photo = models.ImageField(upload_to='job/delivery_photos/', null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    # ── Customer delivery confirmation ──────────────────────────────────────
    confirmation_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    customer_confirmed = models.BooleanField(default=False)
    confirmed_at       = models.DateTimeField(null=True, blank=True)
    # ── Goods classification (added for ML pipeline) ─────────────────────
    CLASSIFICATION_PENDING    = 'pending'
    CLASSIFICATION_PROCESSING = 'processing'
    CLASSIFICATION_COMPLETE   = 'complete'
    CLASSIFICATION_FAILED     = 'failed'
    CLASSIFICATION_FLAGGED    = 'flagged'
    CLASSIFICATION_SKIPPED    = 'skipped'
    CLASSIFICATION_STATUSES   = (
        (CLASSIFICATION_PENDING,    'Pending'),
        (CLASSIFICATION_PROCESSING, 'Processing'),
        (CLASSIFICATION_COMPLETE,   'Complete'),
        (CLASSIFICATION_FAILED,     'Failed'),
        (CLASSIFICATION_FLAGGED,    'Flagged — admin review'),
        (CLASSIFICATION_SKIPPED,    'Skipped'),
    )
 
    classification_status  = models.CharField(
        max_length=20, choices=CLASSIFICATION_STATUSES,
        default='pending',
        help_text='Status of AI goods classification for this job'
    )
    is_flagged_prohibited  = models.BooleanField(
        default=False,
        help_text='True if prohibited goods detected — blocks job until admin review'
    )
    fragility_flag         = models.BooleanField(
        default=False,
        help_text='True if AI detected fragile item — shown to courier'
    )

    def get_confirmation_url(self, base_url=''):
        from django.conf import settings
        base = base_url or getattr(settings, 'SITE_URL', 'http://localhost:8000')
        return f"{base}/customer/confirm/{self.id}/{self.confirmation_token}/"

    def __str__(self):
        return f"{self.names} - {self.Customer}"

    @property
    def pickup_lat(self):
        return self.pickup_location.y if self.pickup_location else 0

    @property
    def pickup_lng(self):
        return self.pickup_location.x if self.pickup_location else 0

    @property
    def delivery_lat(self):
        return self.delivery_location.y if self.delivery_location else 0

    @property
    def delivery_lng(self):
        return self.delivery_location.x if self.delivery_location else 0

class ClassificationResult(models.Model):
    STATUS_CHOICES = [
        ('pending',    'Pending'),
        ('processing', 'Processing'),
        ('complete',   'Complete'),
        ('failed',     'Failed'),
        ('flagged',    'Flagged — prohibited items detected'),
    ]
 
    job               = models.OneToOneField(
        'Job', on_delete=models.CASCADE,
        related_name='classification'
    )
    task_id           = models.CharField(max_length=255, blank=True,
                            help_text='Celery task ID for debugging')
 
    # ── CLIP results ──────────────────────────────────────────────────────
    status                = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    category_suggestion   = models.CharField(max_length=50, blank=True)
    category_confidence   = models.FloatField(default=0.0)
    item_name_suggestion  = models.CharField(max_length=255, blank=True)
    low_confidence        = models.BooleanField(default=False,
                               help_text='True when CLIP confidence < 0.35')
 
    # ── Size suggestion ───────────────────────────────────────────────────
    size_suggestion       = models.CharField(max_length=20, blank=True)
    size_reliable         = models.BooleanField(default=True)
 
    # ── Fragility ─────────────────────────────────────────────────────────
    fragility_score       = models.FloatField(default=0.0)
    is_fragile            = models.BooleanField(default=False)
 
    # ── Prohibited detection ──────────────────────────────────────────────
    prohibited_detected   = models.BooleanField(default=False)
    prohibited_items      = models.JSONField(default=list,
                               help_text='List of detected prohibited items with confidence scores')
    prohibited_reason     = models.TextField(blank=True)
 
    # ── Processing metadata ───────────────────────────────────────────────
    processing_time_s     = models.FloatField(default=0.0)
    error_message         = models.TextField(blank=True)
    raw_results           = models.JSONField(default=dict,
                               help_text='Full raw output from all pipeline stages (debug)')
 
    # ── Future: AI chatbot linkage ────────────────────────────────────────
    chatbot_session_id    = models.CharField(max_length=120, blank=True,
                               help_text='Reserved for future AI chatbot session linkage')
 
    created_at            = models.DateTimeField(auto_now_add=True)
    updated_at            = models.DateTimeField(auto_now=True)
 
    class Meta:
        ordering = ['-created_at']
 
    def __str__(self):
        return f'Classification({self.job_id}) — {self.status}'
        
        
class Transaction(models.Model):
    IN_STATUS = "in"
    OUT_STATUS = "out"
    STATUSES = (
        (IN_STATUS, 'in'),
        (OUT_STATUS, 'out'),
    )
    stripe_payment_intent_id = models.CharField(max_length=255, unique=True)
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    amount = models.FloatField(default=0)
    status = models.CharField(max_length=20, choices=STATUSES, default=IN_STATUS)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.stripe_payment_intent_id


# ═══════════════════════════════════════════════════════════
#   GEOSPATIAL MODELS
# ═══════════════════════════════════════════════════════════

class DeliveryZone(models.Model):
    """
    Geofence polygon defining a delivery zone.
    Supports concave polygons — required for real urban boundaries.
    Winding Number PiP handles these correctly where ray-casting fails.
    """
    name = models.CharField(max_length=255)
    boundary = gis_models.PolygonField(
        geography=True,
        srid=4326,
        spatial_index=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name


class CourierLocationHistory(models.Model):
    """
    Stores every GPS update per courier for trajectory analysis.
    Logged in courier_location_update_api before the Celery task fires.
    """
    courier = models.ForeignKey(Courier, on_delete=models.CASCADE, related_name='location_history')
    location = gis_models.PointField(geography=True, srid=4326, spatial_index=True)
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)
    speed_kmh = models.FloatField(default=0, null=True)
    heading = models.FloatField(default=0, null=True)

    class Meta:
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['courier', 'recorded_at']),
        ]

    def __str__(self):
        return f"{self.courier} @ {self.recorded_at}"


class GeofenceEvent(models.Model):
    """
    Fired by the state machine when a courier enters or exits a zone.
    The 3-consecutive-point threshold (ENTER_THRESHOLD in state_machine.py)
    prevents GPS jitter false positives.
    """
    ENTER = 'enter'
    EXIT = 'exit'
    EVENT_TYPES = (
        (ENTER, 'Entered zone'),
        (EXIT, 'Exited zone'),
    )
    courier = models.ForeignKey(Courier, on_delete=models.CASCADE, related_name='geofence_events')
    zone = models.ForeignKey(DeliveryZone, on_delete=models.CASCADE)
    event_type = models.CharField(max_length=10, choices=EVENT_TYPES)
    triggered_at = models.DateTimeField(default=timezone.now, db_index=True)
    trigger_location = gis_models.PointField(geography=True, srid=4326)

    class Meta:
        ordering = ['-triggered_at']

    def __str__(self):
        return f"{self.courier} {self.event_type} {self.zone} @ {self.triggered_at}"


class CourierZoneState(models.Model):
    """
    Persists the geofence state machine state for each courier×zone pair.

    Why a DB table instead of Redis?
    - Auditable — you can query which couriers are inside which zones at any time
    - Survives Celery worker restarts
    - Works without Redis being available
    - Row count stays small (active couriers × nearby zones, typically 1-3 per courier)

    One row is created or updated per courier per candidate zone on every GPS update.
    Rows where consecutive_inside = consecutive_outside = 0 and state = OUTSIDE
    can be pruned by a periodic Celery task if the table grows.
    """
    OUTSIDE = 'outside'
    DWELL   = 'dwell'    # transitional — accumulating inside readings, not yet confirmed
    INSIDE  = 'inside'
    STATE_CHOICES = [
        (OUTSIDE, 'Outside zone'),
        (DWELL,   'Potentially entering (dwell)'),
        (INSIDE,  'Confirmed inside zone'),
    ]

    courier             = models.ForeignKey(Courier, on_delete=models.CASCADE, related_name='zone_states')
    zone                = models.ForeignKey(DeliveryZone, on_delete=models.CASCADE, related_name='courier_states')
    state               = models.CharField(max_length=10, choices=STATE_CHOICES, default=OUTSIDE)
    consecutive_inside  = models.IntegerField(default=0)
    consecutive_outside = models.IntegerField(default=0)
    last_updated        = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('courier', 'zone')
        indexes = [
            models.Index(fields=['courier', 'state']),
        ]

    def __str__(self):
        return f"{self.courier} / {self.zone} → {self.state}"
    
class DispatchLog(models.Model):
    """
    Records every step of the auto-assignment dispatch pipeline.
    Used to generate pilot study data proving < 60s dispatch time.

    Events:
      notified       — FCM push sent to a courier
      accepted       — courier accepted (job.status changed from processing)
      timeout        — 90s expired, escalating to next courier
      no_couriers    — no available couriers found
      exhausted      — all 5 couriers tried, none accepted
      already_accepted — job was accepted before task even ran

    Key metric: sum(elapsed_seconds WHERE event='accepted') for pilot study
    """

    EVENT_CHOICES = [
        ('notified',          'FCM Notified'),
        ('accepted',          'Job Accepted'),
        ('timeout',           'Timed Out (90s)'),
        ('no_couriers',       'No Couriers Available'),
        ('exhausted',         'All Attempts Exhausted'),
        ('already_accepted',  'Already Accepted'),
        ('fcm_failed',        'FCM Push Failed'),
    ]

    job             = models.ForeignKey('Job', on_delete=models.CASCADE,
                          related_name='dispatch_logs')
    courier         = models.ForeignKey('Courier', on_delete=models.SET_NULL,
                          null=True, blank=True, related_name='dispatch_logs')
    event           = models.CharField(max_length=30, choices=EVENT_CHOICES)
    attempt_number  = models.IntegerField(default=1)
    distance_km     = models.FloatField(null=True, blank=True,
                          help_text="Distance from courier to pickup (km)")
    elapsed_seconds = models.FloatField(null=True, blank=True,
                          help_text="Seconds since dispatch started")
    notes           = models.TextField(blank=True)
    created_at      = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['created_at']
        indexes  = [models.Index(fields=['job', 'created_at'])]

    def __str__(self):
        return f"Dispatch {self.job_id} | {self.event} | attempt {self.attempt_number}"
    
def generate_ticket_number():
    """Generates RVC26-XXXXX style unique ticket numbers."""
    year   = timezone.now().strftime('%y')
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f'RVC{year}-{suffix}'
 
 
class ContactMessage(models.Model):
    """
    Stores all contact form submissions.
    Urgent messages trigger immediate admin email + WhatsApp.
    chatbot_session_id is reserved for future AI chatbot integration.
    """
 
    CATEGORY_CHOICES = [
        ('delivery',  'Delivery Issue'),
        ('billing',   'Billing & Payments'),
        ('tracking',  'Tracking & GPS'),
        ('courier',   'Courier Enquiry'),
        ('technical', 'Technical Support'),
        ('general',   'General Enquiry'),
        ('feedback',  'Feedback'),
    ]
 
    STATUS_CHOICES = [
        ('open',     'Open'),
        ('replied',  'Replied'),
        ('resolved', 'Resolved'),
        ('closed',   'Closed'),
    ]
 
    # Sender info
    name          = models.CharField(max_length=120)
    email         = models.EmailField()
    phone         = models.CharField(max_length=25, blank=True)
 
    # Message
    subject       = models.CharField(max_length=250)
    category      = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='general')
    message       = models.TextField()
    is_urgent     = models.BooleanField(default=False)
 
    # Ticket
    ticket_number = models.CharField(max_length=16, unique=True,
                                     default=generate_ticket_number)
 
    # Status
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    admin_notes   = models.TextField(blank=True,
                                     help_text='Internal notes — not visible to sender')
    replied_at    = models.DateTimeField(null=True, blank=True)
 
    # Timestamps
    created_at    = models.DateTimeField(auto_now_add=True, db_index=True)
 
    # Future: AI chatbot session linkage (provision for chatbot integration)
    chatbot_session_id = models.CharField(max_length=120, blank=True,
                                          help_text='Reserved for AI chatbot session linkage')
 
    class Meta:
        ordering = ['-is_urgent', '-created_at']
        indexes  = [models.Index(fields=['status', 'created_at'])]
 
    def __str__(self):
        urgent = '🚨 ' if self.is_urgent else ''
        return f'{urgent}[{self.ticket_number}] {self.name} — {self.subject}'
