from django import forms
from django.contrib.auth.models import User
from Truck.models import Customer,Job


class BasicUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields =('first_name','last_name')
        

class BasicCustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ('avatar','phone_number')
        
class JobCreateStep1Form(forms.ModelForm):
    class Meta:
        model = Job
        fields = ('names','description','category','size','quantity','photo')
        labels = {
            'names': 'Enter the Item\'s Name',
            'description': 'Enter the Item\'s Description',
            'category': 'Choose Item Category',
            'size': 'Choose the Item\'s Size',
            'quantity': 'Enter the Item\'s Quantity in tonnes',
            'photo': 'Upload the  Item\'s Photo',
        }
        
class JobCreateStep2Form(forms.ModelForm):
    pickup_address = forms.CharField(required=True, label='Please provide the Pickup Address')
    pickup_name = forms.CharField(required=True, label='Please provide the Pickup Contact Name')
    pickup_phone = forms.CharField(required=True, label='Please provide the Pickup Contact Phone Number')

    class Meta:
        model = Job
        fields = ('pickup_address','pickup_lat','pickup_lng','pickup_name','pickup_phone')
        
class JobCreateStep3Form(forms.ModelForm):
    delivery_address = forms.CharField(required=True, label='Enter the Delivery Address')
    delivery_name = forms.CharField(required=True, label='Enter Recipient Name')
    delivery_phone = forms.CharField(required=True, label='Enter Recipient Phone')
    manual_distance = forms.FloatField(
        required=False,
        label='Enter Distance Manually',
        help_text='If you know the exact distance, enter it manually. Otherwise, enter the address that is most likely near your place.'
    )
    distance_unit = forms.ChoiceField(
        choices=[('km', 'Kilometers'), ('miles', 'Miles'), ('meters', 'Meters')],
        required=False,
        label='Select Distance Unit'
    )
    
    class Meta:
        model = Job
        fields = ('delivery_address', 'delivery_lat', 'delivery_lng', 'delivery_name', 'delivery_phone', 'manual_distance', 'distance_unit')
