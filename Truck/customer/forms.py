from django import forms
from django.contrib.auth.models import User
from Truck.models import Customer, Job


class BasicUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name')


class BasicCustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ('avatar', 'phone_number')


class JobCreateStep1Form(forms.ModelForm):
    class Meta:
        model = Job
        fields = ('names', 'description', 'category', 'size', 'quantity', 'goods_type', 'photo')
        labels = {
            'names': "Enter the Item's Name",
            'description': "Enter the Item's Description",
            'category': 'Choose Item Category',
            'size': "Choose the Item's Size",
            'quantity': "Enter the Item's Quantity in tonnes",
            'goods_type': "Choose the type of good you want to move",
            'photo': "Upload the Item's Photo",
        }


class JobCreateStep2Form(forms.ModelForm):
    # These hidden fields carry raw lat/lng values submitted by the frontend
    # (e.g. populated by a Leaflet map picker or a geocoder).
    # They are NOT model fields — the view reads them and builds a Point object.
    pickup_lat = forms.FloatField(widget=forms.HiddenInput(), required=False)
    pickup_lng = forms.FloatField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Job
        # Only real DB columns go here — pickup_location is the PointField
        fields = ('pickup_address', 'pickup_name', 'pickup_phone')
        labels = {
            'pickup_address': 'Please provide the Pickup Address',
            'pickup_name': 'Please provide the Pickup Contact Name',
            'pickup_phone': 'Please provide the Pickup Contact Phone Number',
        }


class JobCreateStep3Form(forms.ModelForm):
    delivery_lat = forms.FloatField(widget=forms.HiddenInput(), required=False)
    delivery_lng = forms.FloatField(widget=forms.HiddenInput(), required=False)

    manual_distance = forms.FloatField(
        required=False,
        label='Enter Distance Manually',
        help_text='If you know the exact distance, enter it here.',
    )
    distance_unit = forms.ChoiceField(
        choices=[('km', 'Kilometers'), ('miles', 'Miles'), ('meters', 'Meters')],
        required=False,
        label='Select Distance Unit',
    )

    class Meta:
        model = Job
        fields = ('delivery_address', 'delivery_name', 'delivery_phone')
        labels = {
            'delivery_address': 'Enter the Delivery Address',
            'delivery_name': 'Enter Recipient Name',
            'delivery_phone': 'Enter Recipient Phone',
        }