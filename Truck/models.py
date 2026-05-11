from django.utils import timezone
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.contrib.gis.db import models as gis_models
from django.contrib.gis.geos import Point


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
        (SMALL_SIZE, "Small"),
        (MEDIUM_SIZE, "Medium"),
        (LARGE_SIZE, "Large"),
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