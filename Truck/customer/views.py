import requests
import math
from django.conf import settings
#email views
from django.core.mail import send_mail
from datetime import datetime
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
#end of email views
import stripe
from django.shortcuts import render,redirect
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from Truck.models import Courier, Job, Transaction
from django.core.paginator import Paginator

from Truck.customer import forms
from .forms import BasicUserForm, BasicCustomerForm, JobCreateStep1Form, JobCreateStep2Form, JobCreateStep1Form, JobCreateStep2Form, JobCreateStep3Form
from django.contrib import messages

from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash

#distance geopy calculations
from geopy.distance import geodesic
from geopy.exc import GeopyError

stripe.api_key = settings.STRIPE_API_SECRET_KEY
# Create your views here.


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
            customer_form =forms.BasicCustomerForm(request.POST, request.FILES, instance=request.user.customer )
            if user_form.is_valid() and customer_form.is_valid():
                user_form.save()
                customer_form.save()
                
                messages.success(request,'Your profile has been updated😊. RiftValley Carrier Value Your Presence😎')
                return redirect(reverse('customer:profile'))
            
        elif request.POST.get('action') == 'update_password':
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                
                messages.success(request,'Your password has been updated😊. RiftValley Carrier Value Your Presence😎')
                return redirect(reverse('customer:profile'))
            else:
                messages.error(request,'Failed!☹️...Kindly Try Again Later')
        
    
    return render(request,'customer/profile.html',{
        'user_form':user_form,
        "customer_form": customer_form,
        'messages': messages.get_messages(request),
        "password_form": password_form
        })
    

@login_required(login_url="/sign_in/?next=/customer/")
def payment_method_page(request):
    current_customer = request.user.customer
    
    #remove existing card
    if request.method == "POST":
        stripe.PaymentMethod.detach(current_customer.stripe_payment_method_id)
        current_customer.stripe_payment_method_id = ""
        current_customer.stripe_card_last4 = ""
        current_customer.save()
        return redirect(reverse('customer:payment_method'))
    
    #save Stripe customer info
    if not current_customer.stripe_customer_id:
        customer = stripe.Customer.create()
        current_customer.stripe_customer_id = customer['id']
        current_customer.save()
        
    #get stripe payment method
    stripe_payment_method = stripe.PaymentMethod.list(
        customer=current_customer.stripe_customer_id,
        type="card",
    )
    print(stripe_payment_method)
    
    if stripe_payment_method and len(stripe_payment_method.data) > 0:
        payment_method = stripe_payment_method.data[0]
        current_customer.stripe_payment_method_id = payment_method.id
        current_customer.stripe_card_last4 =  payment_method.card.last4
        current_customer.save()
    else:
        current_customer.stripe_payment_method_id = ""
        current_customer.stripe_card_last4 =  ""
        current_customer.save()
    
    if not  current_customer.stripe_payment_method_id:
        intent = stripe.SetupIntent.create(
            customer = current_customer.stripe_customer_id,
        )
        return render(request, 'customer/payment_method.html',{
            "client_secret": intent.client_secret,
            "STRIPE_API_PUBLIC_KEY": settings.STRIPE_API_PUBLIC_KEY,
        })
    else:
        return render(request,'customer/payment_method.html')

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

    creating_job, _ = Job.objects.get_or_create(Customer=current_customer, status=Job.CREATING_STATUS)

    step1_form = JobCreateStep1Form(request.POST or None, request.FILES or None, instance=creating_job)
    step2_form = JobCreateStep2Form(request.POST or None, instance=creating_job)
    step3_form = JobCreateStep3Form(request.POST or None, instance=creating_job)

    show_manual_distance = False

    def get_coordinates(address):
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={address}"
        response = requests.get(url).json()
        if response:
            return float(response[0]['lat']), float(response[0]['lon'])
        return None

    def haversine(coord1, coord2):
        R = 6371  # Radius of the Earth in kilometers
        lat1, lon1 = coord1
        lat2, lon2 = coord2
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c
        return distance

    def calculate_duration(distance_km):
        DEFAULT_DURATION_PER_KM = 2  # in minutes, adjust this value as needed
        return distance_km * DEFAULT_DURATION_PER_KM  # Duration in minutes

    if request.method == 'POST':
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
                    "step": 2
                })
        elif request.POST['step'] == '2':
            if step2_form.is_valid():
                step2_form.save()
                return render(request, 'customer/create_job.html', {
                    "step1_form": step1_form,
                    "step2_form": step2_form,
                    "step3_form": step3_form,
                    "job": creating_job,
                    "step": 3
                })
        elif request.POST['step'] == '3':
            if step3_form.is_valid():
                step3_form.save()
                manual_distance = step3_form.cleaned_data.get('manual_distance')
                distance_unit = step3_form.cleaned_data.get('distance_unit')

                if not manual_distance:
                    try:
                        pickup_coordinates = get_coordinates(creating_job.pickup_address)
                        delivery_coordinates = get_coordinates(creating_job.delivery_address)

                        print(f"Pickup Coordinates: {pickup_coordinates}")  # Debug
                        print(f"Delivery Coordinates: {delivery_coordinates}")  # Debug

                        if pickup_coordinates and delivery_coordinates:
                            distance = haversine(pickup_coordinates, delivery_coordinates)
                            print(f"Calculated Distance: {distance}")  # Debug
                            if distance:
                                creating_job.distance = round(distance, 2)
                                creating_job.duration = int(calculate_duration(distance))
                                creating_job.price = round((creating_job.distance * 1) + 20, 2)  # $1 per km
                                creating_job.save()
                            else:
                                raise Exception("Failed to calculate distance.")
                        else:
                            raise Exception("Failed to fetch coordinates from OSM.")
                    except Exception as e:
                        print(e)
                        messages.error(request, "Failed to calculate distance. Please enter the distance manually.")
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
                    if distance_unit == 'miles':
                        distance_in_km = manual_distance * 1.60934
                    elif distance_unit == 'meters':
                        distance_in_km = manual_distance / 1000
                    else:
                        distance_in_km = manual_distance

                    creating_job.distance = round(distance_in_km, 2)
                    creating_job.duration = int(calculate_duration(distance_in_km))
                    creating_job.price = round((creating_job.distance * 1) + 40, 2)  # $1 per km + $20 extra charge
                    creating_job.save()

                return render(request, 'customer/create_job.html', {
                    "step1_form": step1_form,
                    "step2_form": step2_form,
                    "step3_form": step3_form,
                    "GOOGLE_MAP_API_KEY": settings.GOOGLE_MAP_API_KEY,
                    "job": creating_job,
                    "step": 4  # Move to the next step
                })

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

                    # Send email to the owner
                    # Render the email body from an HTML template
                    email_body = render_to_string('emails/new_job_notification.html', {
                        'full_name': current_customer.user.get_full_name(),
                        'job': creating_job,
                        'site_url': 'https://josephnderitu.github.io/myportfolio/',  # replace with your actual site URL
                        'pickup_name': creating_job.pickup_name,
                        'pickup_phone': creating_job.pickup_phone,
                        'pickup_address': creating_job.pickup_address,  # Add pickup address
                        'delivery_address': creating_job.delivery_address,  # Add delivery address
                        'job_image_url': creating_job.photo.url if creating_job.photo else None,
                        'job_created_time': job_created_time,
                    })

                    # Send email to the owner
                    email = EmailMessage(
                        'New Job Created',
                        email_body,
                        settings.DEFAULT_FROM_EMAIL,
                        [settings.OWNER_EMAIL],
                    )
                    email.content_subtype = 'html'  # Specify that the email content is HTML
                    email.send(fail_silently=False)
                    
                    
                    # Send invoice email to the customer
                    invoice_body = render_to_string('emails/invoice.html', {
                        'customer_name': current_customer.user.get_full_name(),
                        'job': creating_job,
                        'job_created_time': job_created_time,
                        'current_year': datetime.now().year,
                    })
                    invoice_email = EmailMessage(
                        'Your Invoice for Job #{}'.format(creating_job.id),
                        invoice_body,
                        settings.DEFAULT_FROM_EMAIL,
                        [current_customer.user.email],
                    )
                    invoice_email.content_subtype = 'html'
                    invoice_email.send(fail_silently=False)

                except stripe.error.CardError as e:
                    error = e.error
                    print("Code is: %s" % error.code)
                    payment_intent_id = error.payment_intent['id']
                    payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

    current_step = 1 if not creating_job.pickup_name else 2
    current_step = 3 if creating_job.delivery_name else current_step
    current_step = 4 if creating_job.price else current_step

    return render(request, 'customer/create_job.html', {
        "job": creating_job,
        "step": current_step,
        "step1_form": step1_form,
        "step2_form": step2_form,
        "step3_form": step3_form,
        "GOOGLE_MAP_API_KEY": settings.GOOGLE_MAP_API_KEY,
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
    ).order_by('-created_at')  # Order by creation date descending
    
    paginator = Paginator(jobs, 2)  # Show 2 jobs per page (adjust per your preference)
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
    ).order_by('-created_at')  # Order by creation date descending
    
    paginator = Paginator(jobs, 2)  # Show 2 jobs per page (adjust per your preference)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'customer/jobs.html', {
        "page_obj": page_obj,
        "archived_jobs": True,
    })

@login_required(login_url="/sign_in/?next=/customer/")
def job_page(request, job_id):
    job = Job.objects.get(id =  job_id)
    
    if request.method == "POST" and job.status == Job.PROCESSING_STATUS:
        job.status = Job.CANCELED_STATUS
        job.save()
        return redirect(reverse('customer:archived_jobs'))
    
    
    return render(request, 'customer/job.html',{
        "job" : job,
        "GOOGLE_MAP_API_KEY": settings.GOOGLE_MAP_API_KEY,
    })
    


