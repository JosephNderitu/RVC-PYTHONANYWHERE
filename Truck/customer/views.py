import requests
import math
from django.conf import settings
from django.core.mail import send_mail
from datetime import datetime
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.contrib.gis.geos import Point

import stripe
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from Truck.models import Courier, Job, Transaction
from django.core.paginator import Paginator

from Truck.customer import forms
from .forms import (
    BasicUserForm,
    BasicCustomerForm,
    JobCreateStep1Form,
    JobCreateStep2Form,
    JobCreateStep3Form,
)
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash

from geopy.distance import geodesic
from geopy.exc import GeopyError
from Truck.distance_engine import compute_distance 

stripe.api_key = settings.STRIPE_API_SECRET_KEY


@login_required()
def home(request):
    return redirect(reverse('customer:profile'))


@login_required(login_url="/sign_in/?next=/customer/")
def profile_page(request):
    user_form = forms.BasicUserForm(instance=request.user)
    customer_form = forms.BasicCustomerForm(instance=request.user.customer)
    password_form = PasswordChangeForm(request.user)

    if request.method == 'POST':
        if request.POST.get('action') == 'update_profile':
            user_form = forms.BasicUserForm(request.POST, instance=request.user)
            customer_form = forms.BasicCustomerForm(request.POST, request.FILES, instance=request.user.customer)
            if user_form.is_valid() and customer_form.is_valid():
                user_form.save()
                customer_form.save()
                messages.success(request, 'Your profile has been updated😊. RiftValley Carrier Value Your Presence😎')
                return redirect(reverse('customer:profile'))

        elif request.POST.get('action') == 'update_password':
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Your password has been updated😊. RiftValley Carrier Value Your Presence😎')
                return redirect(reverse('customer:profile'))
            else:
                messages.error(request, 'Failed!☹️...Kindly Try Again Later')

    return render(request, 'customer/profile.html', {
        'user_form': user_form,
        'customer_form': customer_form,
        'messages': messages.get_messages(request),
        'password_form': password_form,
    })


@login_required(login_url="/sign_in/?next=/customer/")
def payment_method_page(request):
    current_customer = request.user.customer

    if request.method == "POST":
        stripe.PaymentMethod.detach(current_customer.stripe_payment_method_id)
        current_customer.stripe_payment_method_id = ""
        current_customer.stripe_card_last4 = ""
        current_customer.save()
        return redirect(reverse('customer:payment_method'))

    if not current_customer.stripe_customer_id:
        customer = stripe.Customer.create()
        current_customer.stripe_customer_id = customer['id']
        current_customer.save()

    stripe_payment_method = stripe.PaymentMethod.list(
        customer=current_customer.stripe_customer_id,
        type="card",
    )
    print(stripe_payment_method)

    if stripe_payment_method and len(stripe_payment_method.data) > 0:
        payment_method = stripe_payment_method.data[0]
        current_customer.stripe_payment_method_id = payment_method.id
        current_customer.stripe_card_last4 = payment_method.card.last4
        current_customer.save()
    else:
        current_customer.stripe_payment_method_id = ""
        current_customer.stripe_card_last4 = ""
        current_customer.save()

    if not current_customer.stripe_payment_method_id:
        intent = stripe.SetupIntent.create(customer=current_customer.stripe_customer_id)
        return render(request, 'customer/payment_method.html', {
            "client_secret": intent.client_secret,
            "STRIPE_API_PUBLIC_KEY": settings.STRIPE_API_PUBLIC_KEY,
        })
    else:
        return render(request, 'customer/payment_method.html')


@login_required(login_url="/sign_in/?next=/customer/")
def create_job_page(request):
    current_customer = request.user.customer

    if not current_customer.stripe_payment_method_id:
        return redirect(reverse('customer:payment_method'))

    has_current_job = Job.objects.filter(
        Customer=current_customer,
        status__in=(
            Job.PROCESSING_STATUS,
            Job.PICKING_STATUS,
            Job.DELIVERING_STATUS,
        )
    ).exists()

    if has_current_job:
        messages.warning(request, "You already have an active job.")
        return redirect(reverse('customer:current_jobs'))

    creating_job, _ = Job.objects.get_or_create(
        Customer=current_customer,
        status=Job.CREATING_STATUS,
    )

    step1_form = JobCreateStep1Form(request.POST or None, request.FILES or None, instance=creating_job)
    step2_form = JobCreateStep2Form(request.POST or None, instance=creating_job)
    step3_form = JobCreateStep3Form(request.POST or None, instance=creating_job)

    show_manual_distance = False

    if request.method == 'POST':

        # ── Step 1 — item details ────────────────────────────────────────────
        if request.POST['step'] == '1':
            if step1_form.is_valid():
                creating_job = step1_form.save(commit=False)
                creating_job.Customer = current_customer
                creating_job.save()
                return render(request, 'customer/create_job.html', {
                    "step1_form": step1_form,
                    "step2_form": step2_form,
                    "step3_form": step3_form,
                    "job": creating_job,
                    "step": 2,
                })

        # ── Step 2 — pickup location ─────────────────────────────────────────
        elif request.POST['step'] == '2':
            if step2_form.is_valid():
                job = step2_form.save(commit=False)
                job.Customer = current_customer

                lat = step2_form.cleaned_data.get('pickup_lat')
                lng = step2_form.cleaned_data.get('pickup_lng')
                if lat is not None and lng is not None:
                    job.pickup_location = Point(lng, lat, srid=4326)

                job.save()
                return render(request, 'customer/create_job.html', {
                    "step1_form": step1_form,
                    "step2_form": step2_form,
                    "step3_form": step3_form,
                    "job": creating_job,
                    "step": 3,
                })

        # ── Step 3 — delivery location + distance ────────────────────────────
        elif request.POST['step'] == '3':
            if step3_form.is_valid():
                job = step3_form.save(commit=False)
                job.Customer = current_customer

                lat = step3_form.cleaned_data.get('delivery_lat')
                lng = step3_form.cleaned_data.get('delivery_lng')
                if lat is not None and lng is not None:
                    job.delivery_location = Point(lng, lat, srid=4326)

                job.save()
                creating_job.refresh_from_db()

                manual_distance = step3_form.cleaned_data.get('manual_distance')
                distance_unit   = step3_form.cleaned_data.get('distance_unit')

                if not manual_distance:
                    # ── Use our distance engine ──────────────────────────────
                    p_lat = creating_job.pickup_lat
                    p_lng = creating_job.pickup_lng
                    d_lat = creating_job.delivery_lat
                    d_lng = creating_job.delivery_lng

                    if all([p_lat, p_lng, d_lat, d_lng]):
                        result = compute_distance(p_lat, p_lng, d_lat, d_lng)

                        # Replace the distance engine result block
                        if result['error']:
                            messages.error(
                                request,
                                "Could not calculate distance automatically. "
                                "Please enter it manually."
                            )
                            show_manual_distance = True
                            return render(request, 'customer/create_job.html', {
                                "step1_form": step1_form,
                                "step2_form": step2_form,
                                "step3_form": step3_form,
                                "job": creating_job,
                                "step": 3,
                                "show_manual_distance": show_manual_distance,
                            })

                        creating_job.distance = result['distance_miles']   # ← miles not km
                        creating_job.duration = result['duration_min']
                        creating_job.price    = result['price_usd']        # ← USD not KES
                        creating_job.save()

                        messages.info(
                            request,
                            f"Distance: {result['distance_miles']} mi via {result['method']} · "
                            f"Est. {result['duration_min']} min"
                        )
                    else:
                        messages.error(
                            request,
                            "Pickup or delivery coordinates missing. "
                            "Please re-select both locations on the map."
                        )
                        show_manual_distance = True
                        return render(request, 'customer/create_job.html', {
                            "step1_form": step1_form,
                            "step2_form": step2_form,
                            "step3_form": step3_form,
                            "job": creating_job,
                            "step": 3,
                            "show_manual_distance": show_manual_distance,
                        })
                else:
                    # Manual distance entry — convert to miles
                    if distance_unit == 'miles':
                        distance_miles = manual_distance
                    elif distance_unit == 'meters':
                        distance_miles = (manual_distance / 1000) * 0.621371
                    else:  # km
                        distance_miles = manual_distance * 0.621371

                    distance_miles = round(distance_miles, 2)
                    from Truck.distance_engine import _compute_price, _compute_duration
                    creating_job.distance = distance_miles
                    creating_job.duration = _compute_duration(distance_miles)
                    creating_job.price    = _compute_price(distance_miles)
                    creating_job.save()

                return render(request, 'customer/create_job.html', {
                    "step1_form": step1_form,
                    "step2_form": step2_form,
                    "step3_form": step3_form,
                    "job": creating_job,
                    "step": 4,
                })

        # ── Step 4 — payment ─────────────────────────────────────────────────
        elif request.POST['step'] == '4':
            if creating_job.price:
                try:
                    payment_intent = stripe.PaymentIntent.create(
                        amount=int(creating_job.price * 100),
                        currency='usd',
                        customer=current_customer.stripe_customer_id,
                        payment_method=current_customer.stripe_payment_method_id,
                        off_session=True,
                        confirm=True,
                    )
                    Transaction.objects.create(
                        stripe_payment_intent_id=payment_intent['id'],
                        job=creating_job,
                        amount=creating_job.price,
                    )
                    creating_job.status = Job.PROCESSING_STATUS
                    creating_job.save()

                    job_created_time = creating_job.created_at.strftime('%Y-%m-%d %H:%M:%S')
                    email_body = render_to_string('emails/new_job_notification.html', {
                        'full_name':        current_customer.user.get_full_name(),
                        'job':              creating_job,
                        'site_url':         'https://josephnderitu.github.io/myportfolio/',
                        'pickup_name':      creating_job.pickup_name,
                        'pickup_phone':     creating_job.pickup_phone,
                        'pickup_address':   creating_job.pickup_address,
                        'delivery_address': creating_job.delivery_address,
                        'job_image_url':    creating_job.photo.url if creating_job.photo else None,
                        'job_created_time': job_created_time,
                    })
                    email = EmailMessage(
                        'New Job Created', email_body,
                        settings.DEFAULT_FROM_EMAIL, [settings.OWNER_EMAIL],
                    )
                    email.content_subtype = 'html'
                    email.send(fail_silently=False)

                    invoice_body = render_to_string('emails/invoice.html', {
                        'customer_name':    current_customer.user.get_full_name(),
                        'job':              creating_job,
                        'job_created_time': job_created_time,
                        'current_year':     datetime.now().year,
                    })
                    invoice_email = EmailMessage(
                        f'Invoice for Job #{creating_job.id}',
                        invoice_body,
                        settings.DEFAULT_FROM_EMAIL,
                        [current_customer.user.email],
                    )
                    invoice_email.content_subtype = 'html'
                    invoice_email.send(fail_silently=False)

                except stripe.error.CardError as e:
                    messages.error(request, f"Payment failed: {e.error.message}")

    # ── GET — resume at correct step ─────────────────────────────────────────
    current_step = 1
    if creating_job.pickup_name:
        current_step = 2
    if creating_job.delivery_name:
        current_step = 3
    if creating_job.price:
        current_step = 4

    return render(request, 'customer/create_job.html', {
        "job":                creating_job,
        "step":               current_step,
        "step1_form":         step1_form,
        "step2_form":         step2_form,
        "step3_form":         step3_form,
        "show_manual_distance": show_manual_distance,
    })

@login_required(login_url="/sign_in/?next=/customer/")
def current_jobs_page(request):
    jobs = Job.objects.filter(
        Customer=request.user.customer,
        status__in=[
            Job.PROCESSING_STATUS,
            Job.PICKING_STATUS,
            Job.DELIVERING_STATUS,
        ]
    ).order_by('-created_at')

    paginator = Paginator(jobs, 2)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'customer/jobs.html', {
        "page_obj": page_obj,
        "current_jobs": True,
    })


@login_required(login_url="/sign_in/?next=/customer/")
def archived_jobs_page(request):
    jobs = Job.objects.filter(
        Customer=request.user.customer,
        status__in=[
            Job.COMPLETED_STATUS,
            Job.CANCELED_STATUS,
        ]
    ).order_by('-created_at')

    paginator = Paginator(jobs, 2)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'customer/jobs.html', {
        "page_obj": page_obj,
        "archived_jobs": True,
    })


@login_required(login_url="/sign_in/?next=/customer/")
def job_page(request, job_id):
    job = Job.objects.get(id=job_id)

    if request.method == "POST" and job.status == Job.PROCESSING_STATUS:
        job.status = Job.CANCELED_STATUS
        job.save()
        return redirect(reverse('customer:archived_jobs'))

    return render(request, 'customer/job.html', {
        "job": job,
        "GOOGLE_MAP_API_KEY": settings.GOOGLE_MAP_API_KEY,
    })