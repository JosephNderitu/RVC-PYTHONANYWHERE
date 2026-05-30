from django import forms
from django.contrib.auth.models import User
from Truck.models import Courier


class PayoutForm(forms.ModelForm):
    class Meta:
        model = Courier
        fields = ('paypal_email',)


class CourierAvatarForm(forms.ModelForm):
    """Handles profile photo upload."""
    class Meta:
        model  = Courier
        fields = ('avatar',)
        widgets = {
            'avatar': forms.FileInput(attrs={
                'accept': 'image/*',
                'id':     'avatar-file-input',
            })
        }


class CourierVehicleForm(forms.ModelForm):
    """Vehicle type selection."""
    class Meta:
        model  = Courier
        fields = ('vehicle_type',)
        widgets = {
            'vehicle_type': forms.Select(attrs={'class': 'form-control'})
        }


class CourierEmailForm(forms.Form):
    """Change account email with password confirmation."""
    new_email     = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={'placeholder': 'New email address'}),
    )
    confirm_email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={'placeholder': 'Confirm new email'}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Current password'}),
        help_text="Enter your current password to confirm the change."
    )

    def __init__(self, user=None, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        email1  = cleaned.get('new_email', '')
        email2  = cleaned.get('confirm_email', '')
        pwd     = cleaned.get('password', '')

        if email1 and email2 and email1 != email2:
            raise forms.ValidationError("The two email addresses do not match.")

        if self.user and pwd:
            if not self.user.check_password(pwd):
                raise forms.ValidationError("Incorrect password. Please try again.")

        if email1 and self.user:
            if User.objects.filter(email=email1).exclude(pk=self.user.pk).exists():
                raise forms.ValidationError("That email address is already registered.")

        return cleaned