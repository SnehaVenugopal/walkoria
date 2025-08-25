from django import forms
from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _


class CustomAuthenticationForm(forms.Form):
    email = forms.EmailField(label='Email', max_length=254)
    password = forms.CharField(label='Password', widget=forms.PasswordInput)

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')

        if not email:
            raise forms.ValidationError(_('Please enter a valid email.'))
        if not password:
            raise forms.ValidationError(_('Password cannot be blank.'))

        if email and password:
            self.user_cache = authenticate(self.request, email=email, password=password)
            if self.user_cache is None:
                raise forms.ValidationError(_('Invalid email or password'))
            elif not self.user_cache.is_active:
                raise forms.ValidationError(_('This account is inactive.'))
            elif self.user_cache.status == 'Blocked':
                raise forms.ValidationError(_('This account is blocked. Please contact support.'))

        return cleaned_data

    def get_user(self):
        return self.user_cache