from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
 
class SignUpForm(UserCreationForm):
    email     = forms.EmailField(max_length=200, required=True)
    first_name = forms.CharField(max_length=30, required=False)
    last_name  = forms.CharField(max_length=30, required=False)
    telephone  = forms.CharField(
        max_length=15, required=False,
        help_text='Used for WhatsApp delivery notifications'
    )
 
    class Meta:
        model  = User
        # username is NOT listed here — view sets it from email
        fields = (
            'email', 'first_name', 'last_name',
            'telephone',                   # ← was missing before, never saved
            'password1', 'password2',
        )
 
    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email address is already in use.")
        return email
 
    def clean_telephone(self):
        """Basic E.164-ish format check."""
        phone = self.cleaned_data.get('telephone', '').strip()
        if phone and not phone.replace('+', '').replace('-', '').replace(' ', '').isdigit():
            raise ValidationError("Enter a valid phone number.")
        return phone
    

class ContactForm(forms.Form):
    name     = forms.CharField(max_length=120, label='Full name')
    email    = forms.EmailField(label='Email address')
    phone    = forms.CharField(max_length=25, required=False, label='Phone number')
    subject  = forms.CharField(max_length=250, label='Subject')
    category = forms.ChoiceField(choices=[
        ('', 'Select a category…'),
        ('delivery',  'Delivery Issue'),
        ('billing',   'Billing & Payments'),
        ('tracking',  'Tracking & GPS'),
        ('courier',   'Courier Enquiry'),
        ('technical', 'Technical Support'),
        ('general',   'General Enquiry'),
        ('feedback',  'Feedback'),
    ], label='Category')
    message   = forms.CharField(widget=forms.Textarea, label='Message')
    is_urgent = forms.BooleanField(required=False, label='Mark as urgent')
 
    def clean_category(self):
        val = self.cleaned_data.get('category', '')
        if not val:
            raise forms.ValidationError('Please select a category.')
        return val


