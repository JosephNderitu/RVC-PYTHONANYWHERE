from django import forms
from Truck.models import Courier

class PayoutForm(forms.ModelForm):
    class Meta:
        model = Courier
        fields = ('paypal_email',)