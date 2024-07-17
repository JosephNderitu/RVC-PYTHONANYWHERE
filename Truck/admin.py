import random
import string
from django.contrib import admin, messages
from django.conf import settings
from django.core.mail import send_mail
from paypalrestsdk import configure, Payout
from .models import Transaction, Courier, Customer, Category, Truck, Service, Worker, Owner, Job

# Configure PayPal SDK
configure({
    "mode": settings.PAYPAL_MODE,  # sandbox or live
    "client_id": settings.PAYPAL_CLIENT_ID,
    "client_secret": settings.PAYPAL_CLIENT_SECRET,
})

def payout_to_courier(modeladmin, request, queryset):
    payout_items = []
    transaction_querysets = []
    couriers_to_notify = []

    # Step 1: Gather all valid couriers in the queryset
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
                        "value": "{:.2f}".format(balance * 0.8),  # 80% paid to courier
                        "currency": "USD"
                    },
                    "receiver": courier.paypal_email,
                    "note": "Thank you.",
                    "sender_item_id": str(courier.id)
                })
        else:
            couriers_to_notify.append(courier)

    # Step 2: Create payout batch and send email to the receivers
    sender_batch_id = ''.join(random.choice(string.ascii_uppercase) for _ in range(12))
    payout = Payout({
        "sender_batch_header": {
            "sender_batch_id": sender_batch_id,
            "email_subject": "You have a payment"
        },
        "items": payout_items
    })

    # Step 3: Execute payout process and update transaction status if successful
    try:
        if payout.create():
            for t in transaction_querysets:
                t.update(status=Transaction.OUT_STATUS)
            messages.success(request, f"Payout {payout.batch_header.payout_batch_id} created successfully")
            
            # Step 4: Send confirmation emails to couriers with successful payout
            for courier in queryset:
                if courier.paypal_email:
                    subject = "Payment Confirmation"
                    message = (
                        f"Dear {courier.user.get_full_name()},\n\n"
                        f"We are pleased to inform you that a payment of ${balance * 0.8:.2f} has been successfully sent to your PayPal account ({courier.paypal_email}).\n\n"
                        "Thank you for your continued service.\nWe are eager to cultivate a productive and supportive working environment with you.\n\n"
                        "Best regards,\nRiftValley Carriers"
                    )
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [courier.user.email],
                        fail_silently=False,
                    )
        else:
            messages.error(request, payout.error)
    except Exception as e:
        messages.error(request, str(e))

    # Step 5: Send emails to couriers without a PayPal email
    for courier in couriers_to_notify:
        subject = "Action Required: Update Your PayPal Email"
        message = (
            f"Dear {courier.user.get_full_name()},\n\n"
            "We noticed that you don't have a PayPal email set up in your profile. "
            "Please update your PayPal email address in your account settings to receive your payments.\nPlease be aware that money sent to wrong email is not refundable.\n\n"
            "Best regards,\nRiftValley Carriers"
        )
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [courier.user.email],
            fail_silently=False,
        )

payout_to_courier.short_description = "Payout to Couriers"

# Register models with admin site
class CourierAdmin(admin.ModelAdmin):
    list_display = ['user_full_name', 'paypal_email', 'balance']
    actions = [payout_to_courier]

    def user_full_name(self, obj):
        return obj.user.get_full_name()

    def balance(self, obj):
        return round(sum(t.amount for t in Transaction.objects.filter(job__courier=obj, status=Transaction.IN_STATUS)) * 0.8, 2)  # 80% paid to courier

class TransactionAdmin(admin.ModelAdmin):
    list_display = ['stripe_payment_intent_id', 'courier_paypal_email', 'courier', 'job', 'amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']

    def courier(self, obj):
        return obj.job.courier

    def courier_paypal_email(self, obj):
        return obj.job.courier.paypal_email if obj.job.courier else None


class JobAdmin(admin.ModelAdmin):
    list_display = ('names', 'Customer', 'courier', 'category', 'size', 'quantity', 'status', 'created_at')
    list_filter = ('status', 'size', 'category', 'created_at')
    search_fields = ('names', 'Customer__name', 'courier__name', 'pickup_address', 'delivery_address')
    fieldsets = (
        ('Basic Information', {
            'fields': ('names', 'Customer', 'courier', 'description', 'category', 'size', 'quantity', 'photo', 'status', 'created_at')
        }),
        ('Pickup Information', {
            'fields': ('pickup_address', 'pickup_lat', 'pickup_lng', 'pickup_name', 'pickup_phone')
        }),
        ('Delivery Information', {
            'fields': ('delivery_address', 'delivery_lat', 'delivery_lng', 'delivery_name', 'delivery_phone')
        }),
        ('Additional Details', {
            'fields': ('duration', 'distance', 'price', 'pickup_photo', 'pickedup_at', 'delivery_photo', 'delivered_at')
        }),
    )
    ordering = ('-created_at',)
    
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('title', 'description')
    search_fields = ('title', 'description')

class WorkerAdmin(admin.ModelAdmin):
    list_display = ('name', 'job_title', 'description')
    search_fields = ('name', 'job_title', 'description')

class OwnerAdmin(admin.ModelAdmin):
    list_display = ('name', 'job_title', 'description')
    search_fields = ('name', 'job_title', 'description')

class TruckAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name', 'description')


class CustomerAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_number', 'stripe_customer_id']
    list_filter = ['stripe_customer_id']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'phone_number']

    fieldsets = (
        (None, {
            'fields': ('user', 'avatar')
        }),
        ('Stripe Information', {
            'fields': ('stripe_customer_id', 'stripe_payment_method_id', 'stripe_card_last4'),
            'classes': ('collapse',)  # Collapsible fieldset
        }),
        ('Contact Information', {
            'fields': ('phone_number',),
        }),
    )

    readonly_fields = ['stripe_customer_id', 'stripe_payment_method_id', 'stripe_card_last4']

admin.site.register(Customer,CustomerAdmin)
admin.site.register(Courier, CourierAdmin)
admin.site.register(Category)
admin.site.register(Service, ServiceAdmin)
admin.site.register(Worker, WorkerAdmin)
admin.site.register(Owner, OwnerAdmin)
admin.site.register(Truck, TruckAdmin)
admin.site.register(Job, JobAdmin)
admin.site.register(Transaction, TransactionAdmin)
