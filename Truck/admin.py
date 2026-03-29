# Truck/admin.py
import random
import string
from django.contrib import admin, messages
from django.conf import settings
from django.core.mail import send_mail
from paypalrestsdk import configure, Payout
from .models import (
    Transaction, Courier, Customer, Category,
    Truck, Service, Worker, Owner, Job,
    DeliveryZone, CourierLocationHistory, GeofenceEvent,
)

configure({
    "mode": settings.PAYPAL_MODE,
    "client_id": settings.PAYPAL_CLIENT_ID,
    "client_secret": settings.PAYPAL_CLIENT_SECRET,
})


def payout_to_courier(modeladmin, request, queryset):
    payout_items = []
    transaction_querysets = []
    couriers_to_notify = []

    for courier in queryset:
        if courier.paypal_email:
            courier_transactions = Transaction.objects.filter(
                job__courier=courier,
                status=Transaction.IN_STATUS
            )
            if courier_transactions:
                transaction_querysets.append(courier_transactions)
                balance = sum(t.amount for t in courier_transactions)
                payout_items.append({
                    "recipient_type": "EMAIL",
                    "amount": {
                        "value": "{:.2f}".format(balance * 0.8),
                        "currency": "USD"
                    },
                    "receiver": courier.paypal_email,
                    "note": "Thank you.",
                    "sender_item_id": str(courier.id)
                })
        else:
            couriers_to_notify.append(courier)

    sender_batch_id = ''.join(random.choice(string.ascii_uppercase) for _ in range(12))
    payout = Payout({
        "sender_batch_header": {
            "sender_batch_id": sender_batch_id,
            "email_subject": "You have a payment"
        },
        "items": payout_items
    })

    try:
        if payout.create():
            for t in transaction_querysets:
                t.update(status=Transaction.OUT_STATUS)
            messages.success(request, f"Payout {payout.batch_header.payout_batch_id} created successfully")
            for courier in queryset:
                if courier.paypal_email:
                    balance = sum(
                        t.amount for t in Transaction.objects.filter(
                            job__courier=courier, status=Transaction.IN_STATUS
                        )
                    )
                    send_mail(
                        "Payment Confirmation",
                        (
                            f"Dear {courier.user.get_full_name()},\n\n"
                            f"A payment of ${balance * 0.8:.2f} has been sent to {courier.paypal_email}.\n\n"
                            "Thank you for your service.\n\nRiftValley Carriers"
                        ),
                        settings.DEFAULT_FROM_EMAIL,
                        [courier.user.email],
                        fail_silently=False,
                    )
        else:
            messages.error(request, payout.error)
    except Exception as e:
        messages.error(request, str(e))

    for courier in couriers_to_notify:
        send_mail(
            "Action Required: Update Your PayPal Email",
            (
                f"Dear {courier.user.get_full_name()},\n\n"
                "Please update your PayPal email in your profile to receive payments.\n\n"
                "RiftValley Carriers"
            ),
            settings.DEFAULT_FROM_EMAIL,
            [courier.user.email],
            fail_silently=False,
        )

payout_to_courier.short_description = "Payout to Couriers"


# ── Customer ─────────────────────────────────────────────────────────────────
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_number', 'stripe_customer_id']
    list_filter = ['stripe_customer_id']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'phone_number']
    fieldsets = (
        (None, {'fields': ('user', 'avatar')}),
        ('Stripe', {
            'fields': ('stripe_customer_id', 'stripe_payment_method_id', 'stripe_card_last4'),
            'classes': ('collapse',),
        }),
        ('Contact', {'fields': ('phone_number',)}),
    )
    readonly_fields = ['stripe_customer_id', 'stripe_payment_method_id', 'stripe_card_last4']


# ── Courier ───────────────────────────────────────────────────────────────────
@admin.register(Courier)
class CourierAdmin(admin.ModelAdmin):
    list_display = ['user_full_name', 'paypal_email', 'is_available', 'is_on_shift', 'balance']
    list_filter = ['is_available', 'is_on_shift']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'paypal_email']
    actions = [payout_to_courier]
    readonly_fields = ['location_display']

    fieldsets = (
        ('Account', {'fields': ('user', 'paypal_email', 'fcm_token')}),
        ('Status', {'fields': ('is_available', 'is_on_shift')}),
        ('Location', {'fields': ('location', 'location_display')}),
    )

    def user_full_name(self, obj):
        return obj.user.get_full_name()
    user_full_name.short_description = 'Name'

    def balance(self, obj):
        return round(
            sum(t.amount for t in Transaction.objects.filter(
                job__courier=obj, status=Transaction.IN_STATUS
            )) * 0.8, 2
        )
    balance.short_description = 'Pending Balance (USD)'

    def location_display(self, obj):
        if obj.location:
            return f"lat: {obj.lat:.6f}, lng: {obj.lng:.6f}"
        return "No location set"
    location_display.short_description = 'Current coordinates'


# ── Category ──────────────────────────────────────────────────────────────────
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


# ── Job ───────────────────────────────────────────────────────────────────────
@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        'names', 'Customer', 'courier', 'category',
        'size', 'status', 'distance_km', 'price', 'created_at',
    )
    list_filter = ('status', 'size', 'category', 'created_at')
    search_fields = ('names', 'pickup_address', 'delivery_address')
    readonly_fields = (
        'id', 'created_at',
        'pickup_coords_display', 'delivery_coords_display',
    )
    fieldsets = (
        ('Basic Info', {
            'fields': ('id', 'Customer', 'courier', 'names', 'description',
                       'category', 'size', 'quantity', 'photo', 'status', 'created_at'),
        }),
        ('Pickup', {
            'fields': ('pickup_address', 'pickup_location',
                       'pickup_coords_display', 'pickup_name', 'pickup_phone'),
        }),
        ('Delivery', {
            'fields': ('delivery_address', 'delivery_location',
                       'delivery_coords_display', 'delivery_name', 'delivery_phone'),
        }),
        ('Pricing & Route', {
            'fields': ('duration', 'distance', 'price'),
        }),
        ('Proof of Delivery', {
            'fields': ('pickup_photo', 'pickedup_at', 'delivery_photo', 'delivered_at'),
            'classes': ('collapse',),
        }),
    )
    ordering = ('-created_at',)

    def distance_km(self, obj):
        return f"{obj.distance:.2f} km" if obj.distance else '-'
    distance_km.short_description = 'Distance'

    def pickup_coords_display(self, obj):
        if obj.pickup_location:
            return f"lat: {obj.pickup_lat:.6f}, lng: {obj.pickup_lng:.6f}"
        return "Not set"
    pickup_coords_display.short_description = 'Pickup coordinates'

    def delivery_coords_display(self, obj):
        if obj.delivery_location:
            return f"lat: {obj.delivery_lat:.6f}, lng: {obj.delivery_lng:.6f}"
        return "Not set"
    delivery_coords_display.short_description = 'Delivery coordinates'


# ── Transaction ───────────────────────────────────────────────────────────────
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        'stripe_payment_intent_id', 'courier_name',
        'courier_paypal_email', 'job', 'amount', 'status', 'created_at',
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['stripe_payment_intent_id', 'job__names']

    def courier_name(self, obj):
        return obj.job.courier.user.get_full_name() if obj.job.courier else '-'
    courier_name.short_description = 'Courier'

    def courier_paypal_email(self, obj):
        return obj.job.courier.paypal_email if obj.job.courier else '-'
    courier_paypal_email.short_description = 'PayPal Email'


# ── DeliveryZone ──────────────────────────────────────────────────────────────
@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']
    readonly_fields = ['created_at']


# ── CourierLocationHistory ────────────────────────────────────────────────────
@admin.register(CourierLocationHistory)
class CourierLocationHistoryAdmin(admin.ModelAdmin):
    list_display = ['courier', 'lat_display', 'lng_display', 'speed_kmh', 'recorded_at']
    list_filter = ['courier', 'recorded_at']
    search_fields = ['courier__user__first_name', 'courier__user__last_name']
    readonly_fields = ['recorded_at']

    def lat_display(self, obj):
        return f"{obj.location.y:.6f}" if obj.location else '-'
    lat_display.short_description = 'Lat'

    def lng_display(self, obj):
        return f"{obj.location.x:.6f}" if obj.location else '-'
    lng_display.short_description = 'Lng'


# ── GeofenceEvent ─────────────────────────────────────────────────────────────
@admin.register(GeofenceEvent)
class GeofenceEventAdmin(admin.ModelAdmin):
    list_display = ['courier', 'zone', 'event_type', 'triggered_at']
    list_filter = ['event_type', 'zone', 'triggered_at']
    search_fields = ['courier__user__first_name', 'courier__user__last_name']
    readonly_fields = ['triggered_at']


# ── Content models ────────────────────────────────────────────────────────────
@admin.register(Truck)
class TruckAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('title', 'description')
    search_fields = ('title',)

@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = ('name', 'job_title')
    search_fields = ('name', 'job_title')

@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = ('name', 'job_title')
    search_fields = ('name', 'job_title')