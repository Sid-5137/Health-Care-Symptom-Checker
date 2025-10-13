from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import UserProfile

class SignUpForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control rounded-pill',
            'placeholder': 'Enter your email',
        })
    )
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control rounded-pill',
            'placeholder': 'Choose a username',
            'autofocus': True,
        })
    )
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control rounded-pill',
            'placeholder': 'Create a password',
        }),
        help_text="<ul class='text-muted small ps-3'><li>At least 8 characters</li><li>At least one letter and one number</li><li>Do not use your name or username</li><li>Do not use common passwords like 'password', '123456', etc.</li></ul>"
    )
    password2 = forms.CharField(
        label="Confirm Password",
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control rounded-pill',
            'placeholder': 'Repeat your password',
        })
    )
    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

class LoginForm(AuthenticationForm):
    username = forms.CharField(
        max_length=254,
        widget=forms.TextInput(attrs={
            'autofocus': True,
            'class': 'form-control rounded-pill',
            'placeholder': 'Username',
        })
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control rounded-pill',
            'placeholder': 'Password',
        })
    )

class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["family_history"]
        widgets = {
            "family_history": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }
