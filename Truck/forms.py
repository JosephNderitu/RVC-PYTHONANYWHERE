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
    




