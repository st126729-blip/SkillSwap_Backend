from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

ALLOWED_EMAIL_DOMAINS = ['gmail.com', 'ait.asia']


class RegisterForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        domain = email.split('@')[-1]
        if domain not in ALLOWED_EMAIL_DOMAINS:
            raise ValidationError(
                f"Email must end with @{' or @'.join(ALLOWED_EMAIL_DOMAINS)}."
            )
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already registered.")
        return email

class LoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)

class VerifyCodeForm(forms.Form):
    code = forms.CharField(max_length=6)