from Truck.models import Job
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from Truck.models import *
from . import forms
from django.contrib import messages

from django.db.models import Sum, F, FloatField, ExpressionWrapper
from django.db.models.functions import Round

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from datetime import datetime
from datetime import timedelta
from django.utils import timezone
from django.http import JsonResponse

# ── Verification gate helper ──────────────────────────────────────────────────
def _needs_verification(courier):
    """
    Returns True if the courier must complete verification before proceeding.
    Checks safely — works even if migration hasn't run yet on a fresh clone.
    """
    if not hasattr(courier, 'is_verified'):
        return False
    return not courier.is_verified


@login_required(login_url="/sign_in/?next=/courier/")
def home(request):
    """
    Courier dashboard — proper landing page.
    Redirects to verification if courier is not yet verified.
    """
    courier = request.user.courier

    # ── Verification gate ────────────────────────────────────────────────────
    if _needs_verification(courier):
        return redirect(reverse('courier:verification'))

    today   = timezone.now().date()
    completed_jobs = Job.objects.filter(courier=courier, status=Job.COMPLETED_STATUS)
    today_jobs_qs  = completed_jobs.filter(delivered_at__date=today)
    week_start     = today - timedelta(days=7)

    today_earnings = round(sum(j.price for j in today_jobs_qs) * 0.8, 2)
    today_count    = today_jobs_qs.count()
    today_miles    = round(sum(j.distance for j in today_jobs_qs), 1)
    week_earnings  = round(
        sum(j.price for j in completed_jobs.filter(delivered_at__date__gte=week_start)) * 0.8, 2
    )
    total_jobs = completed_jobs.count()

    active_job = Job.objects.filter(
        courier=courier,
        status__in=[Job.PICKING_STATUS, Job.DELIVERING_STATUS],
    ).select_related('Customer').first()

    return render(request, 'courier/home.html', {
        'is_online':      courier.is_available,
        'today_earnings': today_earnings,
        'today_jobs':     today_count,
        'today_miles':    today_miles,
        'week_earnings':  week_earnings,
        'total_jobs':     total_jobs,
        'active_job':     active_job,
    })


@login_required(login_url="/sign_in/?next=/courier/")
def available_jobs_page(request):
    """Redirects unverified couriers to complete verification first."""
    courier = request.user.courier
    if _needs_verification(courier):
        return redirect(reverse('courier:verification'))
    return render(request, 'courier/available_jobs.html')


@login_required(login_url="/sign_in/?next=/courier/")
def verification_page(request):
    """
    Driver licence verification page.
    Shows current verification status and upload form if not yet verified.
    Verified couriers are redirected to the dashboard.
    """
    courier = request.user.courier

    # Already verified — send them to the dashboard
    if getattr(courier, 'is_verified', False):
        return redirect(reverse('courier:home'))

    return render(request, 'courier/verification.html', {
        'courier': courier,
    })


@login_required(login_url="/sign_in/?next=/courier/")
def available_job_page(request, id):
    job = Job.objects.filter(id=id, status=Job.PROCESSING_STATUS).last()

    if not job:
        return redirect(reverse('courier:available_jobs'))

    if request.method == 'POST':
        job.courier = request.user.courier
        job.status  = Job.PICKING_STATUS
        job.save()

        customer_email    = job.Customer.user.email
        customer_name     = job.Customer.user.get_full_name()
        courier_name      = job.courier.user.get_full_name()
        job_created_time  = job.created_at.strftime('%Y-%m-%d %H:%M:%S')

        email_body = render_to_string('emails/courier_on_the_way.html', {
            'customer_name':    customer_name,
            'job':              job,
            'courier_name':     courier_name,
            'job_created_time': job_created_time,
            'current_year':     datetime.now().year,
        })
        plain_message = strip_tags(email_body)
        send_mail(
            'Courier On The Way',
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [customer_email],
            html_message=email_body,
        )

        try:
            from Truck.notifications import notify_job_accepted
            notify_job_accepted(job)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "WhatsApp notification failed for job %s: %s", job.id, exc
            )

        return redirect(reverse('courier:available_jobs'))

    return render(request, 'courier/available_job.html', {"job": job})


@login_required(login_url="/sign_in/?next=/courier/")
def current_job_page(request):
    job = Job.objects.filter(
        courier=request.user.courier,
        status__in=[Job.PICKING_STATUS, Job.DELIVERING_STATUS],
    ).last()
    return render(request, "courier/current_job.html", {
        "job":           job,
        "OSRM_BASE_URL": settings.OSRM_BASE_URL,
    })


@login_required(login_url="/sign_in/?next=/courier/")
def current_job_take_photo(request, id):
    job = Job.objects.filter(
        id=id,
        courier=request.user.courier,
        status__in=[Job.PICKING_STATUS, Job.DELIVERING_STATUS],
    ).last()

    if not job:
        return redirect(reverse('courier:current_job'))

    return render(request, 'courier/current_job_take_photo.html', {"job": job})


@login_required(login_url="/sign_in/?next=/courier/")
def job_complete_page(request):
    return render(request, 'courier/job_complete.html')


@login_required(login_url="/sign_in/?next=/courier/")
def archived_jobs_page(request):
    jobs = Job.objects.filter(
        courier=request.user.courier,
        status=Job.COMPLETED_STATUS,
    )
    return render(request, 'courier/archived-jobs.html', {"jobs": jobs})


@login_required(login_url="/sign_in/?next=/courier/")
def profile_page(request):
    completed_jobs = Job.objects.filter(courier=request.user.courier, status=Job.COMPLETED_STATUS)
    total_earnings = round(sum(job.price for job in completed_jobs) * 0.8, 2)
    total_jobs     = len(completed_jobs)
    total_km       = round(sum(job.distance for job in completed_jobs), 2)

    pending_payments = Transaction.objects.filter(
        job__courier=request.user.courier,
        status=Transaction.IN_STATUS,
    ).annotate(
        amount_to_receive=Round(Sum(F('amount') * 0.8, output_field=FloatField()), 2)
    )

    return render(request, 'courier/profile.html', {
        "total_earnings":   total_earnings,
        "total_jobs":       total_jobs,
        "total_km":         total_km,
        "pending_payments": pending_payments,
    })


@login_required(login_url="/sign_in/?next=/courier/")
def payout_method_page(request):
    payout_form = forms.PayoutForm(instance=request.user.courier)

    if request.method == 'POST':
        payout_form = forms.PayoutForm(request.POST, instance=request.user.courier)
        if payout_form.is_valid():
            payout_form.save()
            messages.success(request, "Payout address is updated.")
            return redirect(reverse('courier:profile'))

    return render(request, 'courier/payout-method.html', {"payout_form": payout_form})


@login_required(login_url="/sign_in/?next=/courier/")
def settings_page(request):
    courier      = request.user.courier
    avatar_form  = forms.CourierAvatarForm(instance=courier)
    vehicle_form = forms.CourierVehicleForm(instance=courier)
    email_form   = forms.CourierEmailForm(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'update_avatar':
            avatar_form = forms.CourierAvatarForm(request.POST, request.FILES, instance=courier)
            if avatar_form.is_valid():
                avatar_form.save()
                messages.success(request, "Profile photo updated.")
                return redirect(reverse('courier:settings'))
            else:
                messages.error(request, "Invalid file. Please upload a JPG or PNG image.")

        elif action == 'update_email':
            email_form = forms.CourierEmailForm(request.user, request.POST)
            if email_form.is_valid():
                new_email = email_form.cleaned_data['new_email']
                request.user.email = new_email
                request.user.save(update_fields=['email'])
                messages.success(request, f"Email updated to {new_email}.")
                return redirect(reverse('courier:settings'))

        elif action == 'update_vehicle':
            vehicle_form = forms.CourierVehicleForm(request.POST, instance=courier)
            if vehicle_form.is_valid():
                vehicle_form.save()
                messages.success(request, "Vehicle type saved.")
                return redirect(reverse('courier:settings'))

    return render(request, 'courier/settings.html', {
        'avatar_form':  avatar_form,
        'email_form':   email_form,
        'vehicle_form': vehicle_form,
        'courier':      courier,
    })

@login_required(login_url="/sign_in/?next=/courier/")
def verification_status_api(request):
    """
    Simple JSON status check — used by the polling JS on the verification page.
    Plain Django view (not DRF) — always works with session auth.
    """
    courier = getattr(request.user, 'courier', None)
    if courier is None:
        return JsonResponse({'error': 'Courier profile not found'}, status=404)

    return JsonResponse({
        'verification_status':   getattr(courier, 'verification_status', 'unverified'),
        'is_verified':           getattr(courier, 'is_verified', False),
        'verification_score':    getattr(courier, 'verification_score', 0.0),
        'verification_notes':    getattr(courier, 'verification_notes', ''),
        'verification_attempts': getattr(courier, 'verification_attempts', 0),
    })