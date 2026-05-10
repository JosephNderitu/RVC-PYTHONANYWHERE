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


@login_required(login_url="sign-in/?next=/courier/")
def home(request):
    return redirect(reverse('courier:available_jobs'))


@login_required(login_url="/sign_in/?next=/courier/")
def available_jobs_page(request):
    return render(request, 'courier/available_jobs.html')


@login_required(login_url="/sign_in/?next=/courier/")
def available_job_page(request, id):
    job = Job.objects.filter(id=id, status=Job.PROCESSING_STATUS).last()

    if not job:
        return redirect(reverse('courier:available_jobs'))

    if request.method == 'POST':
        job.courier = request.user.courier
        job.status  = Job.PICKING_STATUS
        job.save()

        # ── Email notification (existing) ───────────────────────────────
        customer_email    = job.Customer.user.email
        customer_name     = job.Customer.user.get_full_name()
        courier_name      = job.courier.user.get_full_name()
        job_created_time  = job.created_at.strftime('%Y-%m-%d %H:%M:%S')

        email_body = render_to_string('emails/courier_on_the_way.html', {
            'customer_name':   customer_name,
            'job':             job,
            'courier_name':    courier_name,
            'job_created_time': job_created_time,
            'current_year':    datetime.now().year,
        })
        plain_message = strip_tags(email_body)
        send_mail(
            'Courier On The Way',
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [customer_email],
            html_message=email_body,
        )

        # ── WhatsApp notification (NEW) ──────────────────────────────────
        # Sends WhatsApp to customer's phone number.
        # Falls back to email silently if Twilio not configured or
        # customer hasn't opted into the WhatsApp sandbox yet.
        try:
            from Truck.notifications import notify_job_accepted
            notify_job_accepted(job)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "WhatsApp notification failed for job %s: %s", job.id, exc
            )
            # Non-fatal — email was already sent above

        return redirect(reverse('courier:available_jobs'))

    return render(request, 'courier/available_job.html', {"job": job})


@login_required(login_url="/sign_in/?next=/courier/")
def current_job_page(request):
    job = Job.objects.filter(
        courier=request.user.courier,
        status__in=[Job.PICKING_STATUS, Job.DELIVERING_STATUS],
    ).last()
    return render(request, "courier/current_job.html", {
        "job": job,
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
    completed_jobs  = Job.objects.filter(courier=request.user.courier, status=Job.COMPLETED_STATUS)
    total_earnings  = round(sum(job.price for job in completed_jobs) * 0.8, 2)
    total_jobs      = len(completed_jobs)
    total_km        = round(sum(job.distance for job in completed_jobs), 2)

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