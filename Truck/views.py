from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.sessions.backends.db import SessionStore
from . import forms
from django.http import JsonResponse
from .models import Job, Courier
import datetime
from django.contrib.auth import logout
from django.http import JsonResponse
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings as django_settings
import logging
 
logger = logging.getLogger(__name__)

def home(request):
    if request.method == 'POST':
        form = forms.SignUpForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email').lower()
            user = form.save(commit=False)
            user.username = email
            user.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('/')
    else:
        form = forms.SignUpForm()

    # Check if the user has accepted cookies
    cookies_accepted = request.session.get('cookies_accepted', False)
    if cookies_accepted:
        # If cookies are accepted, set the session expiry to 2 hours from now
        request.session.set_expiry(7200)  # 2 hours in seconds

    return render(request, 'home.html', {
        'form': form,
        'cookies_accepted': cookies_accepted,
    })

def sign_up(request):
    form = forms.SignUpForm()
 
    if request.method == 'POST':
        form = forms.SignUpForm(request.POST)
 
        if form.is_valid():
            email = form.cleaned_data['email'].lower()
 
            user = form.save(commit=False)
            user.username   = email          # use email as username
            user.first_name = form.cleaned_data.get('first_name', '')
            user.last_name  = form.cleaned_data.get('last_name', '')
            user.save()
 
            # Save telephone to Customer profile
            telephone = form.cleaned_data.get('telephone', '')
            if telephone:
                try:
                    customer = user.customer
                    customer.phone_number = telephone
                    customer.save(update_fields=['phone_number'])
                except Exception:
                    pass  # Customer profile may not exist yet if using signals
 
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
 
            # Redirect to the correct portal
            next_url = request.POST.get('next') or request.GET.get('next', '/')
            if next_url not in ('/', '/customer/', '/courier/'):
                next_url = '/'
            return redirect(next_url)
 
    return render(request, 'sign_up.html', {'form': form})

def sign_out(request):
    if request.method == 'POST':
        logout(request)
        return redirect('/')
    else:
        return redirect('/')  # Or handle GET request if needed

def terms_and_conditions(request):
    return render(request, 'terms_and_conditions.html')

def billing(request):
    return render(request, 'billing-policy.html')

def fetch_stats(request):
    total_jobs = Job.objects.count()
    successful_jobs = Job.objects.filter(status=Job.COMPLETED_STATUS).count()
    total_couriers = Courier.objects.count()

    data = {
        'total_jobs': total_jobs,
        'successful_jobs': successful_jobs,
        'total_couriers': total_couriers,
    }

    return JsonResponse(data)

def set_cookie_expiry(request):
    if request.method == 'GET':
        # Set session expiry to 2 hours from now
        expiry_time = datetime.datetime.now() + datetime.timedelta(hours=2)
        request.session.set_expiry(7200)
        return JsonResponse({'expiry_time': expiry_time})

def cookie_policy(request):
    return render(request, 'cookie_policy.html')


def contact_page(request):
    """
    Public contact page.
    - Saves message to ContactMessage model
    - Sends confirmation email to sender
    - Urgent: sends immediate email to admin + optional WhatsApp
    """
    from Truck.forms  import ContactForm
    from Truck.models import ContactMessage
 
    submitted      = False
    ticket_number  = None
    submitted_email = None
    submitted_urgent = False
 
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            is_urgent = bool(request.POST.get('is_urgent') == '1')
 
            # ── Save to database ───────────────────────────────────────
            msg = ContactMessage.objects.create(
                name      = cd['name'],
                email     = cd['email'],
                phone     = cd.get('phone', ''),
                subject   = cd['subject'],
                category  = cd['category'],
                message   = cd['message'],
                is_urgent = is_urgent,
            )
 
            # ── Send confirmation email to sender ─────────────────────
            try:
                _send_confirmation_email(msg)
            except Exception as exc:
                logger.warning("Confirmation email failed for %s: %s", msg.ticket_number, exc)
 
            # ── Send admin notification ────────────────────────────────
            try:
                _send_admin_notification(msg, is_urgent)
            except Exception as exc:
                logger.warning("Admin notification failed for %s: %s", msg.ticket_number, exc)
 
            # ── WhatsApp alert for urgent messages ────────────────────
            if is_urgent:
                try:
                    _send_urgent_whatsapp(msg)
                except Exception as exc:
                    logger.warning("Urgent WhatsApp failed for %s: %s", msg.ticket_number, exc)
 
            submitted       = True
            ticket_number   = msg.ticket_number
            submitted_email = msg.email
            submitted_urgent = is_urgent
            form = ContactForm()  # reset
    else:
        form = ContactForm()
        # Pre-fill if logged in
        if request.user.is_authenticated:
            form.initial = {
                'name':  request.user.get_full_name() or '',
                'email': request.user.email,
            }
 
    admin_email = getattr(django_settings, 'ADMIN_EMAIL', '')
 
    return render(request, 'contact.html', {
        'form':             form,
        'submitted':        submitted,
        'ticket_number':    ticket_number,
        'submitted_email':  submitted_email,
        'submitted_urgent': submitted_urgent,
        'admin_email':      admin_email,
    })
 
# ── Email helpers ─────────────────────────────────────────────────
 
def _send_confirmation_email(msg):
    """Auto-reply to sender with their ticket number."""
    subject = f'[{msg.ticket_number}] Message received — RiftValley Carriers'
    text_body = f"""Hi {msg.name},
 
Thank you for contacting RiftValley Carriers. We've received your message and your ticket has been created.
 
Ticket Number: {msg.ticket_number}
Category: {msg.get_category_display()}
Subject: {msg.subject}
Submitted: {msg.created_at.strftime('%B %d, %Y at %I:%M %p ET')}
 
{'⚠️  This message was marked as URGENT. Our team has been notified immediately.' if msg.is_urgent else 'Our support team will respond within 2 business hours during working hours (Mon–Fri 9AM–6PM ET).'}
 
Please keep your ticket number ({msg.ticket_number}) when following up with us.
 
— RiftValley Carriers Support Team
"""
    send_mail(
        subject=subject,
        message=text_body,
        from_email=django_settings.EMAIL_HOST_USER,
        recipient_list=[msg.email],
        fail_silently=True,
    )
 
 
def _send_admin_notification(msg, is_urgent):
    """
    Notifies admin of new contact message.
    Urgent messages get a high-priority subject prefix.
    """
    admin_email = getattr(django_settings, 'ADMIN_EMAIL', '')
    if not admin_email:
        return
 
    urgency_prefix = '🚨 URGENT — ' if is_urgent else ''
 
    subject = f'{urgency_prefix}[{msg.ticket_number}] {msg.subject} ({msg.get_category_display()})'
 
    text_body = f"""New contact message received on RiftValley Carriers.
 
{'━━━ URGENT — RESPOND IMMEDIATELY ━━━' if is_urgent else ''}
 
TICKET:   {msg.ticket_number}
FROM:     {msg.name} <{msg.email}>
PHONE:    {msg.phone or 'Not provided'}
CATEGORY: {msg.get_category_display()}
URGENT:   {'YES ⚠️' if is_urgent else 'No'}
TIME:     {msg.created_at.strftime('%B %d, %Y at %I:%M %p ET')}
 
SUBJECT:
{msg.subject}
 
MESSAGE:
{msg.message}
 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Reply directly to this email to respond to {msg.name}.
Admin panel: http://localhost:8000/admin/Truck/contactmessage/
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=django_settings.EMAIL_HOST_USER,
        to=[admin_email],
        reply_to=[msg.email],   # admin can reply directly to sender
    )
    email.send()
 
 
def _send_urgent_whatsapp(msg):
    """
    Sends a WhatsApp notification to the admin for urgent messages.
    Uses the existing Twilio setup in settings.
    """
    account_sid = getattr(django_settings, 'TWILIO_ACCOUNT_SID', '')
    auth_token  = getattr(django_settings, 'TWILIO_AUTH_TOKEN', '')
    admin_wa    = getattr(django_settings, 'ADMIN_WHATSAPP', '')
    from_wa     = getattr(django_settings, 'TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
 
    if not all([account_sid, auth_token, admin_wa]):
        logger.debug("WhatsApp not configured — skipping urgent alert")
        return
 
    from twilio.rest import Client
    client = Client(account_sid, auth_token)
    client.messages.create(
        from_=from_wa,
        to=f'whatsapp:{admin_wa}',
        body=(
            f'🚨 URGENT CONTACT — RiftValley Carriers\n\n'
            f'Ticket:   {msg.ticket_number}\n'
            f'From:     {msg.name} ({msg.email})\n'
            f'Category: {msg.get_category_display()}\n'
            f'Subject:  {msg.subject}\n\n'
            f'{msg.message[:300]}{"..." if len(msg.message) > 300 else ""}\n\n'
            f'Reply to: {msg.email}'
        )
    )
    logger.info("Urgent WhatsApp sent for ticket %s", msg.ticket_number)