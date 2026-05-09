from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.sessions.backends.db import SessionStore
from . import forms
from django.http import JsonResponse
from .models import Job, Courier
import datetime

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
            email = form.cleaned_data.get('email').lower()
            
            user = form.save(commit=False)
            user.username = email
            user.save()
            
            login(request,user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('/')
            
    
    return render(request, 'sign_up.html',{
        'form': form
    })
    

# views.py
from django.contrib.auth import logout
from django.shortcuts import redirect

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

from django.http import JsonResponse

def set_cookie_expiry(request):
    if request.method == 'GET':
        # Set session expiry to 2 hours from now
        expiry_time = datetime.datetime.now() + datetime.timedelta(hours=2)
        request.session.set_expiry(7200)
        return JsonResponse({'expiry_time': expiry_time})
def cookie_policy(request):
    return render(request, 'cookie_policy.html')