"""
Truck/notifications.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RVC Notification System — WhatsApp via Twilio + Email fallback

PHONE NUMBER HANDLING
──────────────────────
Stored format:  0110423886  (Kenyan, no country code)
Twilio needs:  +254110423886  (E.164 international format)

The normalize_phone() function handles:
  - Kenyan:  0XXXXXXXXX  → +254XXXXXXXXX
  - US:      404XXXXXXX  → +1404XXXXXXX
  - Already E.164: +XXXXXXXXXXX → unchanged

TWILIO TRIAL ACCOUNT LIMITS
─────────────────────────────
- Free trial: $15 credit
- WhatsApp sandbox: whatsapp:+14155238886
- IMPORTANT: recipients must opt in first by texting
  "join <keyword>" to +1 415 523 8886
- Find your keyword at:
  https://console.twilio.com → Messaging → Try WhatsApp

FALLBACK
─────────
If WhatsApp fails for any reason (invalid number, not opted in,
Twilio error), the system automatically sends an email instead.
The courier and customer already receive emails from views.py —
this fallback ensures no notification is ever silently dropped.
"""

import logging
import re
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from datetime import datetime

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
#  PHONE NORMALISATION
# ═══════════════════════════════════════════════════════════

def normalize_phone(raw: str) -> str | None:
    """
    Convert any phone format to E.164 for Twilio.

    Examples:
        '0110423886'     → '+254110423886'  (Kenyan)
        '0712345678'     → '+254712345678'  (Safaricom)
        '4045550123'     → '+14045550123'   (US Atlanta)
        '+14045550123'   → '+14045550123'   (already E.164)
        '+254110423886'  → '+254110423886'  (already E.164)
    """
    if not raw:
        return None

    # Strip all non-numeric except leading +
    phone = re.sub(r'[^\d+]', '', raw.strip())

    if phone.startswith('+'):
        # Already E.164 — validate minimum length
        return phone if len(phone) >= 10 else None

    # Kenyan mobile: starts with 07XX or 01XX (10 digits)
    if re.match(r'^0[17]\d{8}$', phone):
        return '+254' + phone[1:]

    # Kenyan mobile: starts with 254 (already has country code but no +)
    if phone.startswith('254') and len(phone) == 12:
        return '+' + phone

    # US 10-digit without country code
    if len(phone) == 10 and phone[0] in '23456789':
        return '+1' + phone

    # US 11-digit starting with 1
    if len(phone) == 11 and phone.startswith('1'):
        return '+' + phone

    # Unknown format — prepend + and hope for the best
    logger.warning("Unknown phone format '%s' — using as-is with +", raw)
    return '+' + phone


def whatsapp_number(phone: str) -> str | None:
    """Format a phone number for Twilio WhatsApp API."""
    e164 = normalize_phone(phone)
    return f"whatsapp:{e164}" if e164 else None


# ═══════════════════════════════════════════════════════════
#  CORE SEND FUNCTIONS
# ═══════════════════════════════════════════════════════════

def send_whatsapp(phone: str, message: str, media_url: str = None) -> bool:
    """
    Send a WhatsApp message via Twilio.

    Args:
        phone:     Customer phone number (any format — will be normalised)
        message:   Message body text
        media_url: Optional URL to an image (proof of delivery photo etc.)

    Returns:
        True if sent successfully, False otherwise.
        On failure, logs the error — caller should try email fallback.
    """
    to_number = whatsapp_number(phone)
    if not to_number:
        logger.warning("Cannot send WhatsApp — invalid phone: %s", phone)
        return False

    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
    auth_token  = getattr(settings, 'TWILIO_AUTH_TOKEN',  '')
    from_number = getattr(settings, 'TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')

    if not account_sid or not auth_token:
        logger.warning("Twilio credentials not configured — skipping WhatsApp")
        return False

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)

        msg_params = {
            'from_': from_number,
            'to':    to_number,
            'body':  message,
        }
        if media_url:
            msg_params['media_url'] = [media_url]

        msg = client.messages.create(**msg_params)
        logger.info("WhatsApp sent to %s | SID=%s | status=%s",
                    to_number, msg.sid, msg.status)
        return True

    except Exception as exc:
        logger.error("Twilio WhatsApp failed to %s: %s", to_number, exc)
        return False


def _send_email_fallback(to_email: str, subject: str, body: str) -> bool:
    """
    Email fallback when WhatsApp is unavailable.
    Uses the existing Django email infrastructure.
    """
    try:
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
        )
        email.content_subtype = 'html'
        email.send(fail_silently=False)
        logger.info("Email fallback sent to %s: %s", to_email, subject)
        return True
    except Exception as exc:
        logger.error("Email fallback failed to %s: %s", to_email, exc)
        return False


def notify(customer, whatsapp_msg: str, email_subject: str,
           email_body: str = None, media_url: str = None) -> None:
    """
    Try WhatsApp first, fall back to email if it fails.

    Args:
        customer:      Customer model instance
        whatsapp_msg:  WhatsApp message text
        email_subject: Email subject for fallback
        email_body:    Email HTML body (defaults to plain whatsapp_msg)
        media_url:     Optional media URL for WhatsApp
    """
    phone = customer.phone_number or ''
    sent_whatsapp = False

    if phone:
        sent_whatsapp = send_whatsapp(phone, whatsapp_msg, media_url)

    if not sent_whatsapp:
        # Email fallback
        body = email_body or f"<p>{whatsapp_msg}</p>"
        _send_email_fallback(
            to_email=customer.user.email,
            subject=email_subject,
            body=body,
        )


# ═══════════════════════════════════════════════════════════
#  JOB LIFECYCLE NOTIFICATIONS
# ═══════════════════════════════════════════════════════════

def notify_job_accepted(job) -> None:
    """
    Triggered when a courier accepts a job (status → picking).
    Sent to: Customer
    """
    try:
        customer = job.Customer
        courier  = job.courier
        site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')

        # Get fresh ETA from OSRM
        eta_min = _get_eta_minutes(
            courier.lat, courier.lng,
            job.pickup_lat, job.pickup_lng,
        )
        eta_str = f"~{eta_min} min" if eta_min else "shortly"
        tracking_url = f"{site_url}/customer/jobs/{job.id}/"

        wa_msg = (
            f"🚚 *RiftValley Carriers Update*\n\n"
            f"Hi {customer.user.first_name or 'there'}! "
            f"Your job *{job.names}* has been accepted.\n\n"
            f"👤 Courier: *{courier.user.get_full_name()}*\n"
            f"📦 Pickup ETA: *{eta_str}*\n"
            f"📍 Track live: {tracking_url}\n\n"
            f"You'll receive updates as your delivery progresses."
        )

        email_body = render_to_string('emails/courier_on_the_way.html', {
            'customer_name': customer.user.get_full_name(),
            'job':           job,
            'courier_name':  courier.user.get_full_name(),
            'job_created_time': job.created_at.strftime('%Y-%m-%d %H:%M'),
            'current_year':  datetime.now().year,
            'tracking_url':  tracking_url,
            'eta_str':       eta_str,
        })

        notify(customer, wa_msg, f"Courier on the way — {job.names}", email_body)
        logger.info("Job accepted notification sent | job=%s courier=%s",
                    job.id, courier)

    except Exception as exc:
        logger.error("notify_job_accepted failed for job %s: %s", job.id, exc)


def notify_courier_at_pickup(job) -> None:
    """
    Triggered when geofencing ENTER event fires for a pickup zone.
    Sent to: Customer
    """
    try:
        customer = job.Customer
        site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        tracking_url = f"{site_url}/customer/jobs/{job.id}/"

        wa_msg = (
            f"📍 *RiftValley Carriers*\n\n"
            f"Hi {customer.user.first_name or 'there'}! "
            f"Your courier has *arrived at the pickup location* "
            f"for *{job.names}*.\n\n"
            f"Track live: {tracking_url}"
        )

        notify(
            customer, wa_msg,
            f"Courier arrived at pickup — {job.names}",
        )

    except Exception as exc:
        logger.error("notify_courier_at_pickup failed for job %s: %s", job.id, exc)


def notify_delivering(job) -> None:
    """
    Triggered when courier uploads pickup photo (status → delivering).
    Sent to: Customer
    """
    try:
        customer = job.Customer
        courier  = job.courier
        site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')

        eta_min = _get_eta_minutes(
            courier.lat, courier.lng,
            job.delivery_lat, job.delivery_lng,
        )
        eta_str = f"~{eta_min} min" if eta_min else "on the way"
        tracking_url = f"{site_url}/customer/jobs/{job.id}/"

        wa_msg = (
            f"🚀 *RiftValley Carriers*\n\n"
            f"Great news, {customer.user.first_name or 'there'}! "
            f"Your parcel *{job.names}* has been picked up and is "
            f"*on the way to you*.\n\n"
            f"🏁 Delivery ETA: *{eta_str}*\n"
            f"📍 Track live: {tracking_url}"
        )

        notify(
            customer, wa_msg,
            f"Your parcel is on the way — {job.names}",
        )

    except Exception as exc:
        logger.error("notify_delivering failed for job %s: %s", job.id, exc)


def notify_courier_at_delivery(job) -> None:
    """
    Triggered when geofencing ENTER event fires for a delivery zone.
    Sent to: Customer
    """
    try:
        customer = job.Customer
        site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        tracking_url = f"{site_url}/customer/jobs/{job.id}/"

        wa_msg = (
            f"🎯 *RiftValley Carriers*\n\n"
            f"Hi {customer.user.first_name or 'there'}! "
            f"Your courier is *arriving now* with *{job.names}*. "
            f"Please be ready to receive your delivery.\n\n"
            f"Track: {tracking_url}"
        )

        notify(
            customer, wa_msg,
            f"Your delivery is arriving now — {job.names}",
        )

    except Exception as exc:
        logger.error("notify_courier_at_delivery failed for job %s: %s", job.id, exc)


def notify_delivered(job) -> None:
    """
    Triggered when courier uploads delivery photo (status → completed).
    Sends confirmation link so customer can confirm receipt via WhatsApp.
    """
    try:
        customer     = job.Customer
        site_url     = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        photo_url    = None
        confirm_url  = job.get_confirmation_url(site_url)

        if job.delivery_photo:
            try:
                photo_url = f"{site_url}{job.delivery_photo.url}"
            except Exception:
                pass

        wa_msg = (
            f"✅ *RiftValley Carriers — Delivered!*\n\n"
            f"Hi {customer.user.first_name or 'there'}! "
            f"Your parcel *{job.names}* has been delivered.\n\n"
            f"💰 Total paid: *${job.price}*\n\n"
            f"👇 *Please confirm you received it:*\n"
            f"{confirm_url}\n\n"
            f"Thank you for using RiftValley Carriers! 🙏"
        )

        notify(customer, wa_msg,
               f"Delivered — confirm receipt for {job.names}",
               media_url=photo_url)

        logger.info("Delivery notification sent | job=%s confirm_url=%s",
                    job.id, confirm_url)

    except Exception as exc:
        logger.error("notify_delivered failed for job %s: %s", job.id, exc)


# ═══════════════════════════════════════════════════════════
#  GEOFENCE-SPECIFIC DISPATCHER
# ═══════════════════════════════════════════════════════════

def notify_geofence_enter(courier, zone, event) -> None:
    """
    Called from evaluator._on_geofence_event on confirmed ENTER.
    Determines which notification to send based on zone name and job status.
    """
    try:
        from Truck.models import Job

        active_job = Job.objects.filter(
            courier=courier,
            status__in=[Job.PICKING_STATUS, Job.DELIVERING_STATUS],
        ).select_related('Customer', 'courier__user', 'Customer__user').first()

        if not active_job:
            logger.debug("Geofence ENTER fired but no active job for courier %s", courier)
            return

        zone_name_lower = zone.name.lower()
        job_status      = active_job.status

        logger.info(
            "Geofence ENTER dispatch | courier=%s zone='%s' job_status=%s",
            courier, zone.name, job_status,
        )

        # Pickup zone + courier is picking up → courier arrived at pickup
        if job_status == Job.PICKING_STATUS:
            if any(kw in zone_name_lower for kw in ['pickup', 'atlanta', 'origin']):
                notify_courier_at_pickup(active_job)
            else:
                # Any zone enter during pickup = heading to pickup
                notify_courier_at_pickup(active_job)

        # Delivery zone + courier is delivering → arriving at delivery
        elif job_status == Job.DELIVERING_STATUS:
            if any(kw in zone_name_lower for kw in ['delivery', 'marietta', 'savannah',
                                                      'augusta', 'macon', 'athens',
                                                      'destination']):
                notify_courier_at_delivery(active_job)
            else:
                notify_courier_at_delivery(active_job)

    except Exception as exc:
        logger.error("notify_geofence_enter failed: %s", exc)


# ═══════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════

def _get_eta_minutes(from_lat, from_lng, to_lat, to_lng) -> int | None:
    """Get OSRM ETA in minutes. Returns None if OSRM unavailable."""
    try:
        if not all([from_lat, from_lng, to_lat, to_lng]):
            return None
        from Truck.distance_engine import compute_distance
        result = compute_distance(from_lat, from_lng, to_lat, to_lng)
        if result and not result.get('error'):
            return result.get('duration_min')
    except Exception as exc:
        logger.debug("ETA calculation failed: %s", exc)
    return None